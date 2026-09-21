# Détection d'alertes internes EnerVision (issue #104) : script lancé à la main pour l'instant,
# comme `enervision_ml.score` côté ML, sans automatisation Airflow pour l'ordonnancer.

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.repositories.alert import AlertRepository
from app.repositories.prediction import PredictionRepository
from app.repositories.reading import ReadingRepository
from app.repositories.site import SiteRepository
from app.services.alert import AlertService


async def run_detection(*, now: datetime | None = None, site_id: str | None = None) -> int:
    """Exécute les cinq règles de détection et enregistre les nouvelles alertes. Rend le nombre de
    lignes effectivement insérées (les doublons de `source_alert_id` sont silencieusement
    ignorés)."""
    async with get_session_factory()() as session:
        service = AlertService(
            alerts=AlertRepository(session),
            readings=ReadingRepository(session),
            predictions=PredictionRepository(session),
            sites=SiteRepository(session),
        )
        nouvelles = await service.detect(now=now, site_id=site_id)
        await session.commit()
    return len(nouvelles)


def _parse_instant(valeur: str) -> datetime:
    instant = datetime.fromisoformat(valeur)
    return instant if instant.tzinfo is not None else instant.replace(tzinfo=UTC)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.detection.internal_alerts",
        description="Détection d'alertes internes EnerVision",
    )
    parser.add_argument("--site-id", default=None, help="Limite la détection à un seul site.")
    parser.add_argument(
        "--now",
        type=_parse_instant,
        default=None,
        help=(
            "Instant de référence (ISO 8601, UTC si le fuseau est omis). Défaut : l'heure courante."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # Échoue tôt si `APP_SECRET_KEY`/`DATABASE_URL` manquent, avant toute requête à la base.
    get_settings()
    nombre = asyncio.run(run_detection(now=args.now, site_id=args.site_id))
    print(f"{nombre} nouvelle(s) alerte(s) enregistrée(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
