# Le premier test démontre l'atomicité de `consume()` : sur un double, deux soumissions
# concurrentes du même lien réussiraient toutes les deux.

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from app.core.security import fingerprint_refresh, generate_refresh_secret
from app.repositories.password_reset_token import PasswordResetTokenRepository
from app.repositories.user import UserRepository

pytestmark = pytest.mark.integration

DUREE = timedelta(minutes=15)


async def un_compte(session: AsyncSession) -> uuid.UUID:
    compte = await UserRepository(session).create(
        email=f"reset-{uuid.uuid4().hex[:12]}@enervision.fr",
        password_hash="$argon2id$x",
        role=Role.LECTEUR,
    )
    return compte.id


async def un_jeton(
    depot: PasswordResetTokenRepository, user_id: uuid.UUID, *, duree: timedelta = DUREE
) -> str:
    secret = generate_refresh_secret()
    await depot.create(
        user_id=user_id,
        token_hash=fingerprint_refresh(secret),
        expires_at=datetime.now(UTC) + duree,
        client_ip="203.0.113.10",
        user_agent="pytest",
    )
    return secret


async def test_consume_only_succeeds_once(session: AsyncSession) -> None:
    depot = PasswordResetTokenRepository(session)
    secret = await un_jeton(depot, await un_compte(session))

    premier = await depot.consume(fingerprint_refresh(secret))
    second = await depot.consume(fingerprint_refresh(secret))
    await session.rollback()

    assert premier is not None
    assert second is None


async def test_consume_refuses_an_expired_token(session: AsyncSession) -> None:
    depot = PasswordResetTokenRepository(session)
    secret = await un_jeton(depot, await un_compte(session), duree=-timedelta(minutes=1))

    revendique = await depot.consume(fingerprint_refresh(secret))
    await session.rollback()

    assert revendique is None


async def test_consume_returns_nothing_for_an_unknown_fingerprint(
    session: AsyncSession,
) -> None:
    revendique = await PasswordResetTokenRepository(session).consume(
        fingerprint_refresh(generate_refresh_secret())
    )

    assert revendique is None


async def test_invalidate_all_for_user_only_touches_living_tokens(
    session: AsyncSession,
) -> None:
    depot = PasswordResetTokenRepository(session)
    compte = await un_compte(session)
    await un_jeton(depot, compte)
    await un_jeton(depot, compte)

    invalides = await depot.invalidate_all_for_user(compte)
    second_passage = await depot.invalidate_all_for_user(compte)
    await session.rollback()

    assert invalides == 2
    assert second_passage == 0


async def test_exists_valid_is_true_for_a_living_token(session: AsyncSession) -> None:
    depot = PasswordResetTokenRepository(session)
    secret = await un_jeton(depot, await un_compte(session))

    assert await depot.exists_valid(fingerprint_refresh(secret)) is True


async def test_exists_valid_is_false_for_an_expired_token(session: AsyncSession) -> None:
    depot = PasswordResetTokenRepository(session)
    secret = await un_jeton(depot, await un_compte(session), duree=-timedelta(minutes=1))

    assert await depot.exists_valid(fingerprint_refresh(secret)) is False


async def test_exists_valid_is_false_once_the_token_is_consumed(session: AsyncSession) -> None:
    depot = PasswordResetTokenRepository(session)
    secret = await un_jeton(depot, await un_compte(session))
    await depot.consume(fingerprint_refresh(secret))

    assert await depot.exists_valid(fingerprint_refresh(secret)) is False


async def test_exists_valid_is_false_for_an_unknown_fingerprint(session: AsyncSession) -> None:
    depot = PasswordResetTokenRepository(session)

    assert await depot.exists_valid(fingerprint_refresh(generate_refresh_secret())) is False


async def test_the_database_refuses_two_tokens_sharing_a_fingerprint(
    session: AsyncSession,
) -> None:
    depot = PasswordResetTokenRepository(session)
    compte = await un_compte(session)
    secret = generate_refresh_secret()
    await depot.create(
        user_id=compte,
        token_hash=fingerprint_refresh(secret),
        expires_at=datetime.now(UTC) + DUREE,
        client_ip=None,
        user_agent=None,
    )

    empreinte = fingerprint_refresh(secret)
    expiration = datetime.now(UTC) + DUREE

    with pytest.raises(IntegrityError):
        await depot.create(
            user_id=compte,
            token_hash=empreinte,
            expires_at=expiration,
            client_ip=None,
            user_agent=None,
        )
    await session.rollback()
