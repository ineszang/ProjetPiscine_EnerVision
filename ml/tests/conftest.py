"""Piege : deux fixtures d'acces a la base, jamais interchangeables - `connexion_ml` et `parc`.

`connexion_ml` ouvre une transaction annulee a la fin du test : rien ne subsiste, et rien n'est
visible hors de cette connexion. Elle sert aux fonctions qui recoivent leur connexion en
argument (`load_from_database`, `load_recent_from_database`, `write_predictions`).

`run_scoring` fabrique en revanche son propre engine depuis `ML_DATABASE_URL` : il ne verrait
pas des lignes semees dans une transaction non validee, et ses propres ecritures survivraient a
l'annulation. Les tests qui l'appellent passent donc par `parc`, qui valide ce qu'il ecrit et
nettoie lui-meme, dans l'ordre impose par les cles etrangeres `RESTRICT`.
"""

import math
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import lightgbm as lgb
import pandas as pd
import pytest
from sqlalchemy import Connection, Engine, Row, bindparam, create_engine, text
from sqlalchemy.engine import URL, make_url

from enervision_ml.features import TARGET_COLUMN, build_features, feature_columns

BASE_ATTENDUE = "enervision_test"

# Piege : `load_from_database` lit toute la table, et `enervision_test` est partagee entre un run
# local et la CI. Les tests ancrent donc leurs lectures au-dela de tout jeu de donnees reel
# (l'historique s'arrete au 31/12/2024) pour que leur borne `since` ne ramene qu'eux.
ANCRAGE = datetime(2035, 1, 1, tzinfo=UTC)

SITE_TYPE = "office"
CAPACITY_KW = 100.0

_INSERT_SITE = text(
    """
    INSERT INTO site (site_id, site_name, site_type, capacity_kw)
    VALUES (:site_id, :site_name, :site_type, :capacity_kw)
    """
)

# `source = 'api_history'` impose `dataset_id IS NULL` (ck_reading_dataset_source) : le defaut
# `dataset_id=None` evite de creer une ligne `dataset` pour la plupart des tests. `source='csv'`
# impose l'inverse, d'ou `insere_dataset()` quand un test a besoin de cette source precise.
# `raw_data` est NOT NULL, d'ou le litteral jsonb.
_INSERT_READING = text(
    """
    INSERT INTO reading (
        site_id, timestamp, source, dataset_id, consumption_kwh, temperature_celsius,
        humidity_percent, solar_irradiance_wm2, is_working_hours, raw_data
    ) VALUES (
        :site_id, :timestamp, :source, :dataset_id, :consumption_kwh, :temperature_celsius,
        :humidity_percent, :solar_irradiance_wm2, :is_working_hours, '{}'::jsonb
    )
    """
)

_INSERT_DATASET = text(
    """
    INSERT INTO dataset (dataset_name, archive_sha256, storage_uri, source_timezone, metadata)
    VALUES (:dataset_name, :archive_sha256, :storage_uri, 'UTC', '{}'::jsonb)
    RETURNING dataset_id
    """
)

_SELECT_PREDICTIONS = text(
    """
    SELECT target_at, predicted_value, status, failure_reason, model_reference
    FROM prediction
    WHERE site_id = :site_id
    ORDER BY prediction_id
    """
)

_INSERT_PREDICTION = text(
    """
    INSERT INTO prediction (
        site_id, target_at, target_metric, period_minutes,
        predicted_value, model_reference, status, failure_reason
    ) VALUES (
        :site_id, :target_at, 'consumption_kwh', 60,
        :predicted_value, :model_reference, :status, :failure_reason
    )
    """
)


# Ordre impose par les cles etrangeres `RESTRICT` : une lecture avant son site, une prediction
# avant sa lecture.
_SUPPRESSIONS = tuple(
    text(requete).bindparams(bindparam("sites", expanding=True))
    for requete in (
        "DELETE FROM prediction WHERE site_id IN :sites",
        "DELETE FROM reading WHERE site_id IN :sites",
        "DELETE FROM site WHERE site_id IN :sites",
    )
)


def insere_site(
    connexion: Connection,
    *,
    site_type: str = SITE_TYPE,
    capacity_kw: float | None = CAPACITY_KW,
) -> str:
    site_id = f"TEST-{uuid4().hex[:12]}"
    connexion.execute(
        _INSERT_SITE,
        {
            "site_id": site_id,
            "site_name": "Site de test",
            "site_type": site_type,
            "capacity_kw": capacity_kw,
        },
    )
    return site_id


def insere_dataset(connexion: Connection) -> int:
    """Ligne `dataset` minimale, requise pour inserer une lecture `source='csv'`

    (`ck_reading_dataset_source` impose `dataset_id IS NOT NULL` pour cette seule source).
    """
    marque = uuid4().hex
    return cast(
        int,
        connexion.execute(
            _INSERT_DATASET,
            {
                "dataset_name": f"jeu de test {marque}",
                "archive_sha256": marque.rjust(64, "0"),
                "storage_uri": f"file:///test/{marque}.csv",
            },
        ).scalar_one(),
    )


def insere_lectures(
    connexion: Connection,
    site_id: str,
    *,
    heures: int,
    fin: datetime,
    valeur: float = 50.0,
    source: str = "api_history",
    dataset_id: int | None = None,
    is_working_hours: bool | None = True,
) -> list[datetime]:
    """Grille horaire contigue finissant a `fin`, incluse.

    Contigue parce que les lags de `build_features` sont des `shift()` positionnels : un trou
    dans la grille decalerait le lag de 168 h sans qu'aucune erreur ne se declenche.
    """
    instants = [fin - timedelta(hours=decalage) for decalage in reversed(range(heures))]
    connexion.execute(
        _INSERT_READING,
        [
            {
                "site_id": site_id,
                "timestamp": instant,
                "source": source,
                "dataset_id": dataset_id,
                "consumption_kwh": valeur + math.sin(rang / 12.0) * 10.0,
                "temperature_celsius": 15.0,
                "humidity_percent": 50.0,
                "solar_irradiance_wm2": 0.0,
                "is_working_hours": is_working_hours,
            }
            for rang, instant in enumerate(instants)
        ],
    )
    return instants


def insere_lecture(
    connexion: Connection,
    site_id: str,
    *,
    instant: datetime,
    consumption_kwh: float | None = 50.0,
    source: str = "api_history",
    dataset_id: int | None = None,
    is_working_hours: bool | None = True,
) -> None:
    """Une lecture isolee, quand le test pilote sa valeur plutot que sa forme."""
    connexion.execute(
        _INSERT_READING,
        {
            "site_id": site_id,
            "timestamp": instant,
            "source": source,
            "dataset_id": dataset_id,
            "consumption_kwh": consumption_kwh,
            "temperature_celsius": 15.0,
            "humidity_percent": 50.0,
            "solar_irradiance_wm2": 0.0,
            "is_working_hours": is_working_hours,
        },
    )


def insere_prediction(
    connexion: Connection,
    site_id: str,
    *,
    target_at: datetime,
    predicted_value: float | None = 42.0,
    model_reference: str = "lightgbm-test000000",
    status: str = "available",
    failure_reason: str | None = None,
) -> None:
    connexion.execute(
        _INSERT_PREDICTION,
        {
            "site_id": site_id,
            "target_at": target_at,
            "predicted_value": predicted_value,
            "model_reference": model_reference,
            "status": status,
            "failure_reason": failure_reason,
        },
    )


@pytest.fixture(scope="session")
def url_ml() -> URL:
    valeur = os.environ.get("ML_DATABASE_URL")
    if not valeur:
        pytest.fail("ML_DATABASE_URL absente. Voir `make ml-test-integration`.")

    url = make_url(valeur)
    if url.database != BASE_ATTENDUE:
        pytest.fail(
            f"Ces tests ecrivent et suppriment : ML_DATABASE_URL doit viser {BASE_ATTENDUE}, "
            f"pas {url.database}."
        )
    return url


@pytest.fixture(scope="session")
def moteur_ml(url_ml: URL) -> Iterator[Engine]:
    moteur = create_engine(url_ml)
    try:
        yield moteur
    finally:
        moteur.dispose()


@pytest.fixture
def connexion_ml(moteur_ml: Engine) -> Iterator[Connection]:
    with moteur_ml.connect() as connexion:
        transaction = connexion.begin()
        try:
            yield connexion
        finally:
            transaction.rollback()


@dataclass
class Parc:
    """Semis valide en base, et son nettoyage, pour les tests qui appellent `run_scoring`.

    Chaque `site_id` porte une marque unique : la base de test est partagee entre un run local
    et la CI.
    """

    moteur: Engine
    sites: list[str] = field(default_factory=list)

    def site(self, *, site_type: str = SITE_TYPE, capacity_kw: float | None = CAPACITY_KW) -> str:
        with self.moteur.begin() as connexion:
            site_id = insere_site(connexion, site_type=site_type, capacity_kw=capacity_kw)
        self.sites.append(site_id)
        return site_id

    def lectures(self, site_id: str, **arguments: Any) -> list[datetime]:
        with self.moteur.begin() as connexion:
            return insere_lectures(connexion, site_id, **arguments)

    def lecture(self, site_id: str, **arguments: Any) -> None:
        with self.moteur.begin() as connexion:
            insere_lecture(connexion, site_id, **arguments)

    def prediction(self, site_id: str, **arguments: Any) -> None:
        with self.moteur.begin() as connexion:
            insere_prediction(connexion, site_id, **arguments)

    def predictions_ecrites(self, site_id: str) -> list[Row[Any]]:
        with self.moteur.connect() as connexion:
            return list(connexion.execute(_SELECT_PREDICTIONS, {"site_id": site_id}))

    def nettoie(self) -> None:
        if not self.sites:
            return

        with self.moteur.begin() as connexion:
            for suppression in _SUPPRESSIONS:
                connexion.execute(suppression, {"sites": self.sites})


@pytest.fixture
def parc(moteur_ml: Engine) -> Iterator[Parc]:
    semis = Parc(moteur=moteur_ml)
    try:
        yield semis
    finally:
        semis.nettoie()


def trame_synthetique(*, sites: int = 2, heures: int = 400) -> pd.DataFrame:
    """Lectures horaires deterministes, assez longues pour que le lag de 168 h existe."""
    depart = datetime(2024, 1, 1, tzinfo=UTC)
    morceaux = [
        pd.DataFrame(
            {
                "site_id": f"SITE{numero:03d}",
                "timestamp": [depart + timedelta(hours=rang) for rang in range(heures)],
                TARGET_COLUMN: [
                    50.0 + 10.0 * math.sin(rang / 12.0) + numero * 5.0 for rang in range(heures)
                ],
                "temperature_celsius": 15.0,
                "humidity_percent": 50.0,
                "solar_irradiance_wm2": 0.0,
                "is_working_hours": True,
                "site_type": SITE_TYPE,
                "capacity_kw": CAPACITY_KW,
            }
        )
        for numero in range(sites)
    ]
    return pd.concat(morceaux, ignore_index=True)


@pytest.fixture(scope="session")
def modele_jetable(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Booster reel entraine sur une trame synthetique, ecrit dans un repertoire temporaire.

    Ni `ml/models/` (ignore par git, et le polluer serait un effet de bord), ni
    `enervision_ml.train.train()` (qui journalise dans MLflow sans garde). Le typage `category`
    de `site_type` reproduit celui de l'entrainement : c'est le `pandas_categorical` enregistre
    dans le modele que `score()` devra retrouver.
    """
    features = build_features(trame_synthetique()).dropna(subset=feature_columns())
    typee = features.copy()
    typee["site_type"] = typee["site_type"].astype("category")

    donnees = lgb.Dataset(
        typee[feature_columns()],
        label=typee[TARGET_COLUMN],
        categorical_feature=["site_type"],
    )
    booster = lgb.train(
        {"objective": "regression", "num_leaves": 7, "min_data_in_leaf": 5, "verbosity": -1},
        donnees,
        num_boost_round=5,
    )

    chemin = tmp_path_factory.mktemp("modele") / "lightgbm-consumption.txt"
    booster.save_model(str(chemin))
    return chemin
