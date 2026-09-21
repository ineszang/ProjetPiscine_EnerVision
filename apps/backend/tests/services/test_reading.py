from datetime import UTC, datetime, timedelta

import pytest

from app.models.energy import Reading
from app.services.reading import (
    FENETRE_MAXIMALE,
    FENETRE_PAR_DEFAUT,
    FenetreInverseeError,
    FenetreTropLargeError,
    ReadingService,
)


def reading(reading_id: int = 1, site_id: str = "site-1") -> Reading:
    return Reading(
        reading_id=reading_id,
        site_id=site_id,
        timestamp=datetime(2026, 9, 16, tzinfo=UTC),
        source="api_current",
        consumption_kw=10.0,
        data_quality="good",
        raw_data={},
    )


class FakeRepository:
    def __init__(self, readings: list[Reading]) -> None:
        self._readings = readings
        self.appels: list[tuple[str | None, datetime, datetime, int, int]] = []

    async def list_history(
        self,
        *,
        start: datetime,
        end: datetime,
        site_id: str | None = None,
        limit: int,
        offset: int,
    ) -> list[Reading]:
        self.appels.append((site_id, start, end, limit, offset))
        return self._readings


async def test_list_history_returns_the_repository_readings() -> None:
    service = ReadingService(readings=FakeRepository([reading(1), reading(2)]))

    lectures = await service.list_history(limit=500, offset=0)

    assert [r.reading_id for r in lectures] == [1, 2]


async def test_list_history_relays_the_site_id_limit_and_offset() -> None:
    depot = FakeRepository([])
    service = ReadingService(readings=depot)
    debut = datetime(2026, 9, 1, tzinfo=UTC)
    fin = datetime(2026, 9, 2, tzinfo=UTC)

    await service.list_history(site_id="site-1", start=debut, end=fin, limit=50, offset=10)

    assert depot.appels == [("site-1", debut, fin, 50, 10)]


async def test_list_history_defaults_to_the_last_24_hours_when_no_window_is_given() -> None:
    depot = FakeRepository([])
    service = ReadingService(readings=depot)
    avant = datetime.now(UTC)

    await service.list_history(limit=500, offset=0)

    apres = datetime.now(UTC)
    _, debut, fin, _, _ = depot.appels[0]
    assert avant <= fin <= apres
    assert fin - debut == FENETRE_PAR_DEFAUT


async def test_list_history_defaults_end_to_now_when_only_start_is_given() -> None:
    depot = FakeRepository([])
    service = ReadingService(readings=depot)
    debut = datetime.now(UTC) - timedelta(hours=1)
    avant = datetime.now(UTC)

    await service.list_history(start=debut, limit=500, offset=0)

    apres = datetime.now(UTC)
    _, debut_transmis, fin, _, _ = depot.appels[0]
    assert debut_transmis == debut
    assert avant <= fin <= apres


async def test_list_history_defaults_start_to_24_hours_before_end_when_only_end_is_given() -> None:
    depot = FakeRepository([])
    service = ReadingService(readings=depot)
    fin = datetime(2026, 9, 16, tzinfo=UTC)

    await service.list_history(end=fin, limit=500, offset=0)

    _, debut, fin_transmise, _, _ = depot.appels[0]
    assert fin_transmise == fin
    assert debut == fin - FENETRE_PAR_DEFAUT


async def test_list_history_normalizes_naive_datetimes_to_utc() -> None:
    depot = FakeRepository([])
    service = ReadingService(readings=depot)

    await service.list_history(
        start=datetime(2026, 9, 1), end=datetime(2026, 9, 2), limit=500, offset=0
    )

    _, debut, fin, _, _ = depot.appels[0]
    assert debut == datetime(2026, 9, 1, tzinfo=UTC)
    assert fin == datetime(2026, 9, 2, tzinfo=UTC)


async def test_list_history_raises_when_start_is_after_end() -> None:
    service = ReadingService(readings=FakeRepository([]))

    debut = datetime(2026, 9, 2, tzinfo=UTC)
    fin = datetime(2026, 9, 1, tzinfo=UTC)

    with pytest.raises(FenetreInverseeError):
        await service.list_history(start=debut, end=fin, limit=500, offset=0)


async def test_list_history_raises_when_start_equals_end() -> None:
    service = ReadingService(readings=FakeRepository([]))
    instant = datetime(2026, 9, 1, tzinfo=UTC)

    with pytest.raises(FenetreInverseeError):
        await service.list_history(start=instant, end=instant, limit=500, offset=0)


async def test_list_history_raises_when_the_window_exceeds_the_maximum_span() -> None:
    service = ReadingService(readings=FakeRepository([]))
    debut = datetime(2026, 1, 1, tzinfo=UTC)
    fin = debut + FENETRE_MAXIMALE + timedelta(seconds=1)

    with pytest.raises(FenetreTropLargeError):
        await service.list_history(start=debut, end=fin, limit=500, offset=0)


async def test_list_history_accepts_a_window_exactly_at_the_maximum_span() -> None:
    depot = FakeRepository([])
    service = ReadingService(readings=depot)
    debut = datetime(2026, 1, 1, tzinfo=UTC)
    fin = debut + FENETRE_MAXIMALE

    await service.list_history(start=debut, end=fin, limit=500, offset=0)

    assert depot.appels == [(None, debut, fin, 500, 0)]
