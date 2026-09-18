import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.login_attempt import LoginOutcome
from app.repositories.login_attempt import LoginAttemptRepository

pytestmark = pytest.mark.integration

IP = "203.0.113.10"
AUTRE_IP = "198.51.100.7"


def adresse() -> str:
    return f"tentative-{uuid.uuid4().hex[:12]}@enervision.fr"


async def echoue(
    depot: LoginAttemptRepository, email: str, ip: str | None, combien: int = 1
) -> None:
    for _ in range(combien):
        await depot.record(email=email, client_ip=ip, outcome=LoginOutcome.IDENTIFIANTS_INVALIDES)


async def test_count_recent_failures_separates_the_three_counters(
    session: AsyncSession,
) -> None:
    depot = LoginAttemptRepository(session)
    cible, voisin = adresse(), adresse()
    await echoue(depot, cible, IP, combien=3)
    await echoue(depot, cible, AUTRE_IP, combien=2)
    await echoue(depot, voisin, IP, combien=4)
    await session.flush()

    compteurs = await depot.count_recent_failures(email=cible, client_ip=IP, window_seconds=900)
    await session.rollback()

    assert compteurs.per_identifier_and_ip == 3
    assert compteurs.per_identifier == 5
    assert compteurs.per_ip == 7


async def test_count_recent_failures_ignores_successful_attempts(
    session: AsyncSession,
) -> None:
    depot = LoginAttemptRepository(session)
    cible = adresse()
    await echoue(depot, cible, IP, combien=2)
    await depot.record(email=cible, client_ip=IP, outcome=LoginOutcome.SUCCES)
    await session.flush()

    compteurs = await depot.count_recent_failures(email=cible, client_ip=IP, window_seconds=900)
    await session.rollback()

    assert compteurs.per_identifier_and_ip == 2


async def test_count_recent_failures_forgets_what_falls_outside_the_window(
    session: AsyncSession,
) -> None:
    depot = LoginAttemptRepository(session)
    cible = adresse()
    await echoue(depot, cible, IP, combien=2)
    await session.flush()
    await session.execute(
        text(
            "update login_attempt set occurred_at = now() - interval '2 hours' "
            "where email_tried = :e"
        ),
        {"e": cible},
    )

    compteurs = await depot.count_recent_failures(email=cible, client_ip=IP, window_seconds=900)
    await session.rollback()

    assert compteurs.per_identifier_and_ip == 0


async def test_count_recent_failures_still_counts_when_the_address_is_unknown(
    session: AsyncSession,
) -> None:
    depot = LoginAttemptRepository(session)
    inconnu = adresse()
    await echoue(depot, inconnu, IP, combien=5)
    await session.flush()

    compteurs = await depot.count_recent_failures(email=inconnu, client_ip=IP, window_seconds=900)
    await session.rollback()

    assert compteurs.per_identifier_and_ip == 5


async def test_record_normalises_the_address_before_counting(session: AsyncSession) -> None:
    depot = LoginAttemptRepository(session)
    cible = adresse()
    await echoue(depot, cible.upper(), IP, combien=2)
    await session.flush()

    compteurs = await depot.count_recent_failures(email=cible, client_ip=IP, window_seconds=900)
    await session.rollback()

    assert compteurs.per_identifier_and_ip == 2


async def test_count_recent_failures_tolerates_a_missing_client_address(
    session: AsyncSession,
) -> None:
    depot = LoginAttemptRepository(session)
    cible = adresse()
    await echoue(depot, cible, None, combien=2)
    await session.flush()

    compteurs = await depot.count_recent_failures(email=cible, client_ip=None, window_seconds=900)
    await session.rollback()

    assert compteurs.per_identifier == 2
