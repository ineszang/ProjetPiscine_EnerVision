"""Piège : ces fixtures valident leurs écritures, contrairement à celles de tests/repositories.

Un endpoint ouvre sa propre session par `get_session` : il ne verrait pas une ligne semée dans
une transaction en cours. Lui passer la session de la fixture par `dependency_overrides`
supprimerait justement ce que ces tests prouvent, et `RecommendationService.generate` valide de
toute façon lui-même. L'isolation vient donc de la marque portée par chaque `site_id`, et le
nettoyage est explicite, dans l'ordre imposé par les clés étrangères `RESTRICT`.

Contrainte : toutes ces fixtures sont à portée fonction. `engine_per_test` vide le cache du
moteur après chaque test ; une fixture de module verrait un moteur déjà fermé à son démontage,
et ses lignes resteraient en base.
"""

from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_principal
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.db.session import get_session_factory
from app.models.energy import Alert, Prediction, Reading, Recommendation, Site
from tests.repositories.test_alert import creer_alerte
from tests.repositories.test_prediction import creer_prediction
from tests.repositories.test_reading import creer_lecture
from tests.repositories.test_site import creer as creer_site

INSTANT = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class JeuMetier:
    """Identifiants seuls, jamais d'instance ORM : un attribut relu sur une session fermée
    déclenche un `MissingGreenlet`."""

    site_id: str
    site_voisin: str
    alert_id: int
    prediction_id: int
    instant: datetime


async def _supprime(session: AsyncSession, sites: list[str]) -> None:
    # La suppression des recommandations est inconditionnelle : `POST /generate` en cree hors du
    # controle de la fixture, et `alert` les retient par une cle etrangere `RESTRICT`.
    alertes = select(Alert.alert_id).where(Alert.site_id.in_(sites))
    await session.execute(delete(Recommendation).where(Recommendation.alert_id.in_(alertes)))
    await session.execute(delete(Alert).where(Alert.site_id.in_(sites)))
    await session.execute(delete(Prediction).where(Prediction.site_id.in_(sites)))
    await session.execute(delete(Reading).where(Reading.site_id.in_(sites)))
    await session.execute(delete(Site).where(Site.site_id.in_(sites)))
    await session.commit()


@pytest.fixture
def marque() -> str:
    return uuid4().hex[:12]


@pytest.fixture
async def jeu_metier(marque: str) -> AsyncIterator[JeuMetier]:
    """Un site instrumenté, un site voisin, trois lectures horaires, une prédiction, une alerte.

    Le voisin existe pour que les tests de filtre prouvent qu'ils écartent quelque chose.
    """
    site_id = f"SITE-{marque}"
    voisin = f"SITE-{marque}-VOISIN"

    async with get_session_factory()() as session:
        await creer_site(session, site_id=site_id, capacity_kw=100.0)
        await creer_site(session, site_id=voisin, capacity_kw=100.0)
        for decalage in range(3):
            await creer_lecture(
                session,
                site_id=site_id,
                timestamp=INSTANT - timedelta(hours=decalage),
                consumption_kw=10.0 + decalage,
            )
        prediction = await creer_prediction(session, site_id=site_id, target_at=INSTANT)
        alerte = await creer_alerte(session, site_id=site_id, timestamp=INSTANT)
        jeu = JeuMetier(
            site_id=site_id,
            site_voisin=voisin,
            alert_id=alerte.alert_id,
            prediction_id=prediction.prediction_id,
            instant=INSTANT,
        )
        await session.commit()

    try:
        yield jeu
    finally:
        async with get_session_factory()() as session:
            await _supprime(session, [site_id, voisin])


@pytest.fixture
async def site_nu(marque: str) -> AsyncIterator[str]:
    """Un site sans lecture ni prédiction : le cas que seul un vrai `LEFT JOIN` distingue."""
    site_id = f"SITE-{marque}-NU"

    async with get_session_factory()() as session:
        await creer_site(session, site_id=site_id, capacity_kw=100.0)
        await session.commit()

    try:
        yield site_id
    finally:
        async with get_session_factory()() as session:
            await _supprime(session, [site_id])


@pytest.fixture
def principal_injecte(app: FastAPI) -> Iterator[Callable[[Role], None]]:
    def installe(role: Role = Role.LECTEUR) -> None:
        app.dependency_overrides[get_current_principal] = lambda: Principal(
            id=uuid4(),
            email="parcours@enervision.fr",
            role=role,
            kind=AccountKind.HUMAIN,
            must_change_password=False,
        )

    yield installe
    app.dependency_overrides.pop(get_current_principal, None)
