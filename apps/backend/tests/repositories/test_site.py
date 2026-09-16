import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Site
from app.repositories.site import SiteRepository

pytestmark = pytest.mark.integration


def identifiant() -> str:
    return f"SITE-{uuid.uuid4().hex[:8]}"


async def test_list_all_returns_every_site_sorted_by_id(session: AsyncSession) -> None:
    premier, second = sorted([identifiant(), identifiant()])
    session.add_all(
        [
            Site(site_id=second, site_name="B", site_type="bureau", capacity_kw=100),
            Site(site_id=premier, site_name="A", site_type="bureau", capacity_kw=50),
        ]
    )
    await session.flush()
    depot = SiteRepository(session)

    sites = await depot.list_all()
    identifiants = [site.site_id for site in sites if site.site_id in (premier, second)]
    await session.rollback()

    assert identifiants == [premier, second]
