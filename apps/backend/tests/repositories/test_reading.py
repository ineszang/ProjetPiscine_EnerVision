import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Reading, Site
from app.repositories.reading import ReadingRepository

pytestmark = pytest.mark.integration


def identifiant() -> str:
    return f"SITE-{uuid.uuid4().hex[:8]}"


def lecture(site_id: str, *, timestamp: datetime, consumption_kw: float) -> Reading:
    return Reading(
        site_id=site_id,
        timestamp=timestamp,
        source="api_current",
        consumption_kw=consumption_kw,
        data_quality="good",
        raw_data={},
    )


async def test_latest_by_site_keeps_only_the_most_recent_reading(session: AsyncSession) -> None:
    site_id = identifiant()
    maintenant = datetime.now(UTC)
    session.add(Site(site_id=site_id, site_name="Site", site_type="bureau", capacity_kw=100))
    await session.flush()
    session.add_all(
        [
            lecture(site_id, timestamp=maintenant - timedelta(hours=1), consumption_kw=10),
            lecture(site_id, timestamp=maintenant, consumption_kw=42),
        ]
    )
    await session.flush()
    depot = ReadingRepository(session)

    resultats = await depot.latest_by_site()
    consommations = [r.consumption_kw for r in resultats if r.site_id == site_id]
    await session.rollback()

    assert consommations == [42]


async def test_latest_by_site_returns_one_row_per_site(session: AsyncSession) -> None:
    premier, second = identifiant(), identifiant()
    maintenant = datetime.now(UTC)
    session.add_all(
        [
            Site(site_id=premier, site_name="A", site_type="bureau", capacity_kw=100),
            Site(site_id=second, site_name="B", site_type="bureau", capacity_kw=200),
        ]
    )
    await session.flush()
    session.add_all(
        [
            lecture(premier, timestamp=maintenant, consumption_kw=10),
            lecture(second, timestamp=maintenant, consumption_kw=20),
        ]
    )
    await session.flush()
    depot = ReadingRepository(session)

    resultats = await depot.latest_by_site()
    identifiants = {r.site_id for r in resultats if r.site_id in (premier, second)}
    await session.rollback()

    assert identifiants == {premier, second}
