"""Piege : ce fichier porte le marqueur `chaine`, pas `integration` - test_the_ml_binaries...()

Il lance les vrais binaires `enervision_ml.train` et `enervision_ml.score` dans l'environnement
uv de `ml/`, que le job `integration` de `backend.yml` n'installe pas. Un marqueur distinct evite
que ce job, et `make test`, ne le selectionnent et n'echouent faute de `ml/.venv`.
"""

import math
import os
import subprocess
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any
from uuid import uuid4

import anyio
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import delete, insert, make_url

from app.api.deps import get_current_principal
from app.core.config import get_settings
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.db.session import get_session_factory
from app.models.energy import Prediction, Reading, Site

pytestmark = pytest.mark.chaine

RACINE = Path(__file__).resolve().parents[3]
ML = RACINE / "ml"
PYTHON_ML = Path(os.environ.get("ML_PYTHON", ML / ".venv" / "bin" / "python"))

HEURES_COMPLETES = 400
HEURES_INSUFFISANTES = 100


def lecteur() -> Principal:
    return Principal(
        id=uuid4(),
        email="lecteur@enervision.fr",
        role=Role.LECTEUR,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )


def url_ml() -> str:
    """Derive la chaine du pipeline de celle du backend plutot que de la recopier : les deux
    cotes visent ainsi la meme base, dans leur dialecte respectif."""
    return (
        make_url(get_settings().database_url)
        .set(drivername="postgresql+psycopg")
        .render_as_string(hide_password=False)
    )


def lance_ml(module: str, *arguments: str, journal: Path) -> subprocess.CompletedProcess[str]:
    if not PYTHON_ML.exists():
        pytest.fail(
            f"Environnement ml/ absent ({PYTHON_ML}). Lancer `cd ml && uv sync --all-groups`."
        )

    return subprocess.run(  # noqa: S603 -- argv en liste, sans shell, binaire resolu dans le depot
        [str(PYTHON_ML), "-m", module, *arguments],
        cwd=ML,
        text=True,
        capture_output=True,
        timeout=600,
        check=False,
        env={
            **os.environ,
            "ML_DATABASE_URL": url_ml(),
            "MLFLOW_TRACKING_URI": f"sqlite:///{journal}/mlflow.db",
        },
    )


async def executer(module: str, *arguments: str, journal: Path) -> subprocess.CompletedProcess[str]:
    resultat = await anyio.to_thread.run_sync(
        partial(lance_ml, module, *arguments, journal=journal)
    )
    assert resultat.returncode == 0, resultat.stderr
    return resultat


@dataclass
class Parc:
    sites: list[str] = field(default_factory=list)


def lignes_horaires(site_id: str, *, heures: int, fin: datetime) -> list[dict[str, Any]]:
    return [
        {
            "site_id": site_id,
            "timestamp": fin - timedelta(hours=decalage),
            "source": "api_history",
            "consumption_kwh": 50.0 + math.sin(decalage / 12.0) * 10.0,
            "temperature_celsius": 15.0,
            "humidity_percent": 50.0,
            "solar_irradiance_wm2": 0.0,
            "is_working_hours": True,
            "raw_data": {},
        }
        for decalage in reversed(range(heures))
    ]


@pytest.fixture
async def parc() -> AsyncIterator[Parc]:
    """Deux sites dotes d'un historique complet, un troisieme qui n'atteint pas le lag de 168 h.

    Les ecritures sont validees : les binaires ML ouvrent leur propre connexion et ne verraient
    pas une transaction en cours.
    """
    fin = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    marque = uuid4().hex[:12]
    complets = [f"TEST-{marque}-A", f"TEST-{marque}-B"]
    partiel = f"TEST-{marque}-C"
    parc = Parc(sites=[*complets, partiel])

    async with get_session_factory()() as session:
        await session.execute(
            insert(Site),
            [
                {
                    "site_id": site_id,
                    "site_name": f"Site {site_id}",
                    "site_type": "office",
                    "capacity_kw": 100.0,
                }
                for site_id in parc.sites
            ],
        )
        for site_id in complets:
            await session.execute(
                insert(Reading), lignes_horaires(site_id, heures=HEURES_COMPLETES, fin=fin)
            )
        await session.execute(
            insert(Reading), lignes_horaires(partiel, heures=HEURES_INSUFFISANTES, fin=fin)
        )
        await session.commit()

    try:
        yield parc
    finally:
        async with get_session_factory()() as session:
            await session.execute(delete(Prediction).where(Prediction.site_id.in_(parc.sites)))
            await session.execute(delete(Reading).where(Reading.site_id.in_(parc.sites)))
            await session.execute(delete(Site).where(Site.site_id.in_(parc.sites)))
            await session.commit()


@pytest.fixture
def principal_lecteur(app: FastAPI) -> Iterator[None]:
    app.dependency_overrides[get_current_principal] = lecteur
    yield
    app.dependency_overrides.pop(get_current_principal, None)


async def resume_du_site(client: AsyncClient, site_id: str) -> dict[str, Any]:
    reponse = await client.get("/api/v1/predictions")

    assert reponse.status_code == 200
    sites = reponse.json()["sites"]
    return next(site for site in sites if site["site_id"] == site_id)


async def entraine_et_score(parc: Parc, tmp_path: Path, *arguments: str) -> Path:
    modele = tmp_path / "lightgbm-consumption.txt"

    await executer(
        "enervision_ml.train",
        "--model-output",
        str(modele),
        "--mlflow-tracking-uri",
        f"sqlite:///{tmp_path}/mlflow.db",
        journal=tmp_path,
    )
    await executer("enervision_ml.score", "--model", str(modele), *arguments, journal=tmp_path)

    return modele


async def test_the_ml_binaries_produce_a_prediction_that_the_api_serves(
    parc: Parc, tmp_path: Path, client: AsyncClient, principal_lecteur: None
) -> None:
    await entraine_et_score(parc, tmp_path)

    servi = await resume_du_site(client, parc.sites[0])

    assert servi["prediction"]["status"] == "available"
    assert servi["prediction"]["predicted_value"] is not None
    assert servi["prediction"]["target_metric"] == "consumption_kwh"


async def test_the_api_exposes_the_failure_reason_of_a_site_without_enough_history(
    parc: Parc, tmp_path: Path, client: AsyncClient, principal_lecteur: None
) -> None:
    await entraine_et_score(parc, tmp_path)

    servi = await resume_du_site(client, parc.sites[-1])

    assert servi["prediction"]["status"] == "insufficient_data"
    assert servi["prediction"]["predicted_value"] is None
    assert servi["prediction"]["failure_reason"] is not None


async def test_the_api_serves_the_latest_run_when_the_score_cli_runs_twice(
    parc: Parc, tmp_path: Path, client: AsyncClient, principal_lecteur: None
) -> None:
    modele = await entraine_et_score(parc, tmp_path)
    premier = await resume_du_site(client, parc.sites[0])

    await executer("enervision_ml.score", "--model", str(modele), journal=tmp_path)

    second = await resume_du_site(client, parc.sites[0])
    assert second["prediction"]["created_at"] >= premier["prediction"]["created_at"]
    assert second["prediction"]["model_reference"] == premier["prediction"]["model_reference"]
