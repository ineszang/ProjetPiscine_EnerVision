from collections.abc import Callable

import pytest
from httpx import AsyncClient

from app.core.roles import Role
from app.db.session import get_session_factory
from tests.api.conftest import JeuMetier
from tests.repositories.test_reading import creer_lecture

pytestmark = pytest.mark.integration


async def test_list_sites_returns_the_seeded_site_with_its_stored_attributes(
    jeu_metier: JeuMetier, principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.LECTEUR)

    reponse = await client.get("/api/v1/sites")

    assert reponse.status_code == 200
    mien = next(site for site in reponse.json() if site["site_id"] == jeu_metier.site_id)
    assert mien["capacity_kw"] == 100.0
    assert mien["site_name"] == "Site de test"


async def test_get_site_returns_404_when_the_identifier_is_absent_from_the_database(
    principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.LECTEUR)

    reponse = await client.get("/api/v1/sites/SITE-JAMAIS-INSERE")

    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Site introuvable"


async def test_get_current_returns_the_most_recent_reading_when_several_hours_are_stored(
    jeu_metier: JeuMetier, principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.LECTEUR)

    reponse = await client.get(f"/api/v1/sites/{jeu_metier.site_id}/current")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["consumption_kw"] == 10.0
    assert corps["timestamp"].startswith("2026-09-16T12:00")


async def test_get_current_keeps_the_highest_reading_id_when_two_sources_share_the_timestamp(
    jeu_metier: JeuMetier, principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.LECTEUR)
    async with get_session_factory()() as session:
        await creer_lecture(
            session,
            site_id=jeu_metier.site_id,
            timestamp=jeu_metier.instant,
            source="api_history",
            consumption_kw=999.0,
        )
        await session.commit()

    reponse = await client.get(f"/api/v1/sites/{jeu_metier.site_id}/current")

    assert reponse.json()["consumption_kw"] == 999.0


async def test_get_current_reports_a_critical_quality_when_the_site_has_no_reading(
    site_nu: str, principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.LECTEUR)

    reponse = await client.get(f"/api/v1/sites/{site_nu}/current")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["timestamp"] is None
    assert corps["data_quality"] == "critical"
