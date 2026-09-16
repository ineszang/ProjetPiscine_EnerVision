import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Site
from app.repositories.site import SiteRepository

pytestmark = pytest.mark.integration


def identifiant() -> str:
    return f"site-{uuid.uuid4().hex[:12]}"


async def creer(session: AsyncSession, **overrides: object) -> Site:
    site = Site(
        site_id=overrides.get("site_id", identifiant()),
        site_name=overrides.get("site_name", "Site de test"),
        site_type=overrides.get("site_type", "industriel"),
        location=overrides.get("location", "Toulouse"),
        capacity_kw=overrides.get("capacity_kw", 42.0),
        status=overrides.get("status", "actif"),
    )
    session.add(site)
    await session.flush()
    return site


async def test_get_by_id_returns_the_matching_site(session: AsyncSession) -> None:
    depot = SiteRepository(session)
    cree = await creer(session)

    trouve = await depot.get_by_id(cree.site_id)
    nom = trouve.site_name if trouve else None
    await session.rollback()

    assert nom == "Site de test"


async def test_get_by_id_returns_nothing_for_an_unknown_identifier(
    session: AsyncSession,
) -> None:
    trouve = await SiteRepository(session).get_by_id(identifiant())

    assert trouve is None


async def test_list_all_returns_the_sites_sorted_by_identifier(session: AsyncSession) -> None:
    depot = SiteRepository(session)
    premier, second = sorted([f"zz-{identifiant()}", f"aa-{identifiant()}"])
    await creer(session, site_id=second)
    await creer(session, site_id=premier)

    sites = await depot.list_all()
    identifiants = [site.site_id for site in sites if site.site_id in (premier, second)]
    await session.rollback()

    assert identifiants == [premier, second]
