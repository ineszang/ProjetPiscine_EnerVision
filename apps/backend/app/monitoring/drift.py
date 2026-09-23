# Surveillance de dérive du modèle de prévision (EC06, issue #45) : même gabarit que
# `app.detection.internal_alerts`, ordonnancé par le DAG `derive`.

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.repositories.drift import DriftRepository, NouveauRapportDerive
from app.services.drift import STATUT_DERIVE, DriftService, Seuils


async def run_drift(
    *, now: datetime | None = None, site_id: str | None = None, seuils: Seuils | None = None
) -> list[NouveauRapportDerive]:
    """Calcule les rapports de la fenêtre et les enregistre. Rend ce qui a été calculé, que la
    ligne ait été écrite ou ignorée par l'index d'idempotence."""
    async with get_session_factory()() as session:
        depot = DriftRepository(session)
        rapports = await DriftService(depot, seuils=seuils).evaluate(now=now, site_id=site_id)
        await depot.enregistre(rapports)
        await session.commit()
    return rapports


def _parse_instant(valeur: str) -> datetime:
    instant = datetime.fromisoformat(valeur)
    return instant if instant.tzinfo is not None else instant.replace(tzinfo=UTC)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    defauts = Seuils()
    parser = argparse.ArgumentParser(
        prog="python -m app.monitoring.drift",
        description="Surveillance de dérive du modèle de prévision EnerVision",
    )
    parser.add_argument("--site-id", default=None, help="Limite le calcul à un seul site.")
    parser.add_argument(
        "--now",
        type=_parse_instant,
        default=None,
        help=(
            "Instant de référence (ISO 8601, UTC si le fuseau est omis). Défaut : l'heure courante."
        ),
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=int(defauts.fenetre.total_seconds() // 3600),
        help="Durée de la fenêtre récente, et de la fenêtre de référence qui la précède.",
    )
    parser.add_argument(
        "--grace-hours",
        type=int,
        default=int(defauts.grace.total_seconds() // 3600),
        help="Délai laissé à l'ingestion avant qu'une prévision soit jugée vérifiable.",
    )
    parser.add_argument(
        "--min-observations",
        type=int,
        default=defauts.min_observations,
        help="En deçà, le verdict est `indetermine` plutôt qu'un chiffre trompeur.",
    )
    parser.add_argument(
        "--bias-threshold",
        type=float,
        default=defauts.seuil_biais,
        help=(
            "Biais absolu en kWh au-delà duquel le verdict bascule en dérive. "
            "Zéro, le défaut, laisse le biais informatif : voir l'ADR 0013."
        ),
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Sort en code non nul si une dérive est constatée, pour que la tâche rougisse.",
    )
    return parser.parse_args(argv)


def seuils_depuis(args: argparse.Namespace) -> Seuils:
    return Seuils(
        fenetre=timedelta(hours=args.window_hours),
        grace=timedelta(hours=args.grace_hours),
        min_observations=args.min_observations,
        seuil_biais=args.bias_threshold,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # Échoue tôt si `APP_SECRET_KEY`/`DATABASE_URL` manquent, avant toute requête à la base.
    get_settings()
    rapports = asyncio.run(
        run_drift(now=args.now, site_id=args.site_id, seuils=seuils_depuis(args))
    )

    for rapport in rapports:
        cible = rapport.site_id or "TOUS SITES"
        mae = f"{rapport.mae:.2f}" if rapport.mae is not None else "-"
        print(
            f"{cible} : {rapport.status}, MAE {mae} kWh sur {rapport.n_observations} prévision(s)"
            f"{' : ' + rapport.reason if rapport.reason else ''}"
        )

    derive = any(rapport.status == STATUT_DERIVE for rapport in rapports)
    return 1 if derive and args.fail_on_drift else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
