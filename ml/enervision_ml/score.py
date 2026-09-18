"""Scoring du modele LightGBM : calcule et enregistre la consommation prevue du prochain pas
horaire, par site.

CLI autonome, sur le meme gabarit que `enervision_ml.train` et
`apps/backend/app/etl/historical_import.py`. Cf. `docs/ML-START.md`, section 2.

    uv run python -m enervision_ml.score --csv ../ml/data/all_sites_combined.csv
    uv run python -m enervision_ml.score  # lit ML_DATABASE_URL, ecrit dans `prediction`

Reutilise `enervision_ml.features.build_features` tel quel (jamais reecrit) : c'est la garantie
contre le train/serve skew documentee dans ce module.
"""

import argparse
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import lightgbm as lgb
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from enervision_ml import config
from enervision_ml.data import load_from_csv, load_recent_from_database
from enervision_ml.features import TARGET_COLUMN, WEATHER_COLUMNS, build_features, feature_columns

# Marge au-dessus des 168h necessaires au lag hebdomadaire, pour absorber les trous de mesure.
LOOKBACK = timedelta(days=21)

TARGET_METRIC = "consumption_kwh"
PERIOD_MINUTES = 60
LAG_168H_COLUMN = f"{TARGET_COLUMN}_lag_168h"
INSUFFICIENT_DATA_REASON = (
    "Historique insuffisant : moins de 168h de consumption_kwh disponibles pour ce site."
)


@dataclass(frozen=True, slots=True)
class ScoredSite:
    site_id: str
    target_at: datetime
    status: str
    predicted_value: float | None
    failure_reason: str | None


def model_reference(model_path: Path) -> str:
    """Identifiant stable du modele utilise, insensible au fait que `train.py` reecrive
    toujours le meme nom de fichier a chaque entrainement (pas de versioning par nom, cf.
    `ml/README.md`)."""
    empreinte = hashlib.sha256(model_path.read_bytes()).hexdigest()
    return f"lightgbm-{empreinte[:12]}"


def build_scoring_frame(recent: pd.DataFrame, *, site_id: str | None = None) -> pd.DataFrame:
    """Ajoute une ligne future (l'heure suivant la derniere lecture connue) par site, et calcule
    ses features par `build_features` -- exactement comme a l'entrainement, seule la cible de
    cette ligne est inconnue.

    Piege assume : `is_working_hours` de la ligne future est copie de la derniere lecture reelle,
    pas recalcule. Il n'existe aucune regle horaire ouvrable dans ce depot (elle vit dans le
    generateur du jeu de donnees d'origine, hors de ce code) ; l'approximation n'est fausse
    qu'aux heures de bascule (ouverture/fermeture), sur une seule feature parmi une dizaine, pour
    une prevision a un pas seulement.
    """
    travail = recent if site_id is None else recent[recent["site_id"] == site_id]
    if travail.empty:
        return build_features(travail)

    dernieres = (
        travail.sort_values("timestamp").groupby("site_id", as_index=False, sort=False).tail(1)
    ).copy()
    dernieres["timestamp"] = dernieres["timestamp"] + pd.Timedelta(hours=1)
    dernieres[TARGET_COLUMN] = float("nan")
    # Meteo future inconnue (cf. piege documente dans `enervision_ml.features.build_features`) :
    # laisser `NaN` ici n'a aucun effet sur les features utilisees, qui ne prennent la meteo que
    # decalee.
    for colonne in WEATHER_COLUMNS:
        dernieres[colonne] = float("nan")

    etendu = pd.concat([travail, dernieres], ignore_index=True)
    features = build_features(etendu)
    return features.groupby("site_id", as_index=False, sort=False).tail(1).reset_index(drop=True)


def score(booster: lgb.Booster, scoring_frame: pd.DataFrame) -> list[ScoredSite]:
    resultats: list[ScoredSite] = []

    insuffisants = scoring_frame[scoring_frame[LAG_168H_COLUMN].isna()]
    for enregistrement in _records(insuffisants):
        resultats.append(
            ScoredSite(
                site_id=enregistrement["site_id"],
                target_at=enregistrement["timestamp"].to_pydatetime(),
                status="insufficient_data",
                predicted_value=None,
                failure_reason=INSUFFICIENT_DATA_REASON,
            )
        )

    suffisants = scoring_frame[scoring_frame[LAG_168H_COLUMN].notna()]
    if not suffisants.empty:
        typee = suffisants.copy()
        typee["site_type"] = typee["site_type"].astype("category")
        predictions = booster.predict(typee[feature_columns()])
        for enregistrement, valeur in zip(_records(suffisants), predictions, strict=True):
            resultats.append(
                ScoredSite(
                    site_id=enregistrement["site_id"],
                    target_at=enregistrement["timestamp"].to_pydatetime(),
                    status="available",
                    predicted_value=float(valeur),
                    failure_reason=None,
                )
            )

    return resultats


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], frame.to_dict(orient="records"))


_INSERT_PREDICTION = text(
    """
    INSERT INTO prediction (
        site_id, target_at, target_metric, period_minutes,
        predicted_value, model_reference, status, failure_reason
    ) VALUES (
        :site_id, :target_at, :target_metric, :period_minutes,
        :predicted_value, :model_reference, :status, :failure_reason
    )
    """
)


def write_predictions(
    connection: Connection, resultats: list[ScoredSite], *, reference: str
) -> None:
    """Ecrit une ligne par site score. Insertion seule, jamais de mise a jour : `prediction`
    n'a pas de contrainte d'unicite sur `(site_id, target_at)`, chaque run garde sa propre trace
    plutot que d'ecraser la precedente -- utile plus tard pour comparer prevision et realise
    (surveillance de derive, #44/#45)."""
    if not resultats:
        return

    lignes = [
        {
            "site_id": r.site_id,
            "target_at": r.target_at,
            "target_metric": TARGET_METRIC,
            "period_minutes": PERIOD_MINUTES,
            "predicted_value": r.predicted_value,
            "model_reference": reference,
            "status": r.status,
            "failure_reason": r.failure_reason,
        }
        for r in resultats
    ]
    connection.execute(_INSERT_PREDICTION, lignes)


def _load_recent(*, csv_path: Path | None, now: datetime | None) -> tuple[pd.DataFrame, datetime]:
    if csv_path is not None:
        brute = load_from_csv(csv_path)
        instant = now or (
            brute["timestamp"].max().to_pydatetime() if not brute.empty else datetime.now(UTC)
        )
        return brute[brute["timestamp"] >= instant - LOOKBACK], instant

    instant = now or datetime.now(UTC)
    engine = create_engine(config.database_url())
    try:
        return load_recent_from_database(engine, since=instant - LOOKBACK), instant
    finally:
        engine.dispose()


def run_scoring(
    *,
    model_path: Path,
    csv_path: Path | None = None,
    site_id: str | None = None,
    now: datetime | None = None,
) -> list[ScoredSite]:
    """Score le prochain pas horaire par site et l'ecrit dans `prediction`.

    En mode `--csv`, rien n'est ecrit : c'est un instantane historique fige (l'heure "future"
    calculee n'existe dans aucune base reelle), utile pour valider le pipeline sans base
    joignable, cf. `ml/README.md`.
    """
    recent, _instant = _load_recent(csv_path=csv_path, now=now)
    if site_id is not None:
        recent = recent[recent["site_id"] == site_id]

    scoring_frame = build_scoring_frame(recent, site_id=site_id)
    if scoring_frame.empty:
        return []

    booster = lgb.Booster(model_file=str(model_path))
    resultats = score(booster, scoring_frame)

    if csv_path is None:
        reference = model_reference(model_path)
        engine = create_engine(config.database_url())
        try:
            with engine.begin() as connection:
                write_predictions(connection, resultats, reference=reference)
        finally:
            engine.dispose()

    return resultats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scoring du modele LightGBM EnerVision")

    parser.add_argument(
        "--model",
        type=Path,
        default=Path("models/lightgbm-consumption.txt"),
        help="Chemin du modele entraine. Defaut : models/lightgbm-consumption.txt.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "Instantane historique de demarrage/demo, rien n'est ecrit en base. Omis, lit "
            "ML_DATABASE_URL, se connecte a PostgreSQL et ecrit dans `prediction`."
        ),
    )
    parser.add_argument(
        "--site-id",
        default=None,
        help="Ne score que ce site. Omis, tous les sites presents dans la fenetre recente.",
    )
    parser.add_argument(
        "--now",
        type=_parse_instant,
        default=None,
        help=(
            "Instant de reference (ISO 8601), pour tester ou demontrer le scoring cote base sur "
            "des donnees anciennes (ex. le jeu de donnees historique, qui s'arrete fin 2024). "
            "Omis, horloge systeme reelle."
        ),
    )

    return parser.parse_args()


def _parse_instant(valeur: str) -> datetime:
    instant = datetime.fromisoformat(valeur)
    return instant if instant.tzinfo is not None else instant.replace(tzinfo=UTC)


def main() -> None:
    args = parse_args()
    resultats = run_scoring(
        model_path=args.model, csv_path=args.csv, site_id=args.site_id, now=args.now
    )

    if not resultats:
        print("Aucun site a scorer (aucune lecture recente dans la fenetre).")
        return

    for r in resultats:
        if r.status == "available":
            print(f"{r.site_id} @ {r.target_at} : {r.predicted_value:.2f} kWh")
        else:
            print(f"{r.site_id} @ {r.target_at} : {r.status} ({r.failure_reason})")

    if args.csv is not None:
        print("\nMode --csv : instantane historique, rien ecrit en base.")


if __name__ == "__main__":
    main()
