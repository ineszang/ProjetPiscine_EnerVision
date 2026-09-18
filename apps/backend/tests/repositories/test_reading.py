import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Reading, Site
from app.repositories.reading import ReadingRepository
from tests.repositories.test_site import creer as creer_site
from tests.repositories.test_site import identifiant as identifiant_site

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


async def creer_lecture(session: AsyncSession, *, site_id: str, **overrides: object) -> Reading:
    reading = Reading(
        site_id=site_id,
        timestamp=overrides.get("timestamp", datetime(2026, 9, 16, tzinfo=UTC)),
        source=overrides.get("source", "api_current"),
        consumption_kw=overrides.get("consumption_kw", 10.0),
        data_quality=overrides.get("data_quality", "good"),
        raw_data=overrides.get("raw_data", {}),
    )
    session.add(reading)
    await session.flush()
    return reading


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


async def test_latest_for_site_returns_the_most_recent_reading(session: AsyncSession) -> None:
    site = await creer_site(session)
    depot = ReadingRepository(session)
    await creer_lecture(session, site_id=site.site_id, timestamp=datetime(2026, 9, 1, tzinfo=UTC))
    recente = await creer_lecture(
        session, site_id=site.site_id, timestamp=datetime(2026, 9, 15, tzinfo=UTC)
    )

    trouvee = await depot.latest_for_site(site.site_id)
    reading_id = trouvee.reading_id if trouvee else None
    await session.rollback()

    assert reading_id == recente.reading_id


async def test_latest_for_site_breaks_a_timestamp_tie_on_the_last_written_reading(
    session: AsyncSession,
) -> None:
    site = await creer_site(session)
    depot = ReadingRepository(session)
    horodatage = datetime(2026, 9, 15, tzinfo=UTC)
    await creer_lecture(session, site_id=site.site_id, timestamp=horodatage, source="api_history")
    derniere = await creer_lecture(
        session, site_id=site.site_id, timestamp=horodatage, source="api_current"
    )

    trouvee = await depot.latest_for_site(site.site_id)
    reading_id = trouvee.reading_id if trouvee else None
    await session.rollback()

    assert reading_id == derniere.reading_id


async def test_latest_for_site_ignores_the_readings_of_the_other_sites(
    session: AsyncSession,
) -> None:
    sans_lecture = await creer_site(session)
    autre = await creer_site(session)
    depot = ReadingRepository(session)
    await creer_lecture(session, site_id=autre.site_id)

    trouvee = await depot.latest_for_site(sans_lecture.site_id)
    await session.rollback()

    assert trouvee is None


async def test_list_history_orders_the_readings_by_timestamp_descending(
    session: AsyncSession,
) -> None:
    site = await creer_site(session)
    depot = ReadingRepository(session)
    ancienne = await creer_lecture(
        session, site_id=site.site_id, timestamp=datetime(2026, 9, 1, tzinfo=UTC)
    )
    recente = await creer_lecture(
        session, site_id=site.site_id, timestamp=datetime(2026, 9, 15, tzinfo=UTC)
    )

    resultats = await depot.list_history(
        start=datetime(2026, 8, 1, tzinfo=UTC),
        end=datetime(2026, 10, 1, tzinfo=UTC),
        limit=100,
        offset=0,
    )
    identifiants = [
        r.reading_id for r in resultats if r.reading_id in (ancienne.reading_id, recente.reading_id)
    ]
    await session.rollback()

    assert identifiants == [recente.reading_id, ancienne.reading_id]


async def test_list_history_filters_by_site_id(session: AsyncSession) -> None:
    premier = await creer_site(session)
    second = await creer_site(session)
    depot = ReadingRepository(session)
    voulue = await creer_lecture(session, site_id=premier.site_id)
    await creer_lecture(session, site_id=second.site_id)

    resultats = await depot.list_history(
        site_id=premier.site_id,
        start=datetime(2026, 8, 1, tzinfo=UTC),
        end=datetime(2026, 10, 1, tzinfo=UTC),
        limit=100,
        offset=0,
    )
    identifiants = [r.reading_id for r in resultats]
    await session.rollback()

    assert identifiants == [voulue.reading_id]


async def test_list_history_excludes_readings_outside_the_window(session: AsyncSession) -> None:
    site = await creer_site(session)
    depot = ReadingRepository(session)
    dedans = await creer_lecture(
        session, site_id=site.site_id, timestamp=datetime(2026, 9, 10, tzinfo=UTC)
    )
    await creer_lecture(session, site_id=site.site_id, timestamp=datetime(2026, 8, 1, tzinfo=UTC))
    await creer_lecture(session, site_id=site.site_id, timestamp=datetime(2026, 10, 1, tzinfo=UTC))

    resultats = await depot.list_history(
        site_id=site.site_id,
        start=datetime(2026, 9, 1, tzinfo=UTC),
        end=datetime(2026, 9, 30, tzinfo=UTC),
        limit=100,
        offset=0,
    )
    identifiants = [r.reading_id for r in resultats]
    await session.rollback()

    assert identifiants == [dedans.reading_id]


async def test_list_history_respects_limit_and_offset(session: AsyncSession) -> None:
    site = await creer_site(session)
    depot = ReadingRepository(session)
    lectures = [
        await creer_lecture(
            session, site_id=site.site_id, timestamp=datetime(2026, 9, jour, tzinfo=UTC)
        )
        for jour in (1, 2, 3)
    ]

    resultats = await depot.list_history(
        site_id=site.site_id,
        start=datetime(2026, 8, 1, tzinfo=UTC),
        end=datetime(2026, 10, 1, tzinfo=UTC),
        limit=1,
        offset=1,
    )
    identifiants = [r.reading_id for r in resultats]
    await session.rollback()

    assert identifiants == [lectures[1].reading_id]


async def test_list_history_returns_an_empty_list_when_there_is_nothing(
    session: AsyncSession,
) -> None:
    depot = ReadingRepository(session)

    resultats = await depot.list_history(
        site_id=identifiant_site(),
        start=datetime(2026, 8, 1, tzinfo=UTC),
        end=datetime(2026, 10, 1, tzinfo=UTC),
        limit=100,
        offset=0,
    )

    assert list(resultats) == []
