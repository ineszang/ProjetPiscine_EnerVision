# Le premier test de ce fichier est le seul endroit où l'atomicité de la rotation se démontre :
# sur un double, deux appels concurrents réussiraient tous les deux.

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from app.core.security import fingerprint_refresh, generate_refresh_secret
from app.models.refresh_token import RevocationReason
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository

pytestmark = pytest.mark.integration

DUREE = timedelta(days=7)


async def un_compte(session: AsyncSession) -> uuid.UUID:
    compte = await UserRepository(session).create(
        email=f"jeton-{uuid.uuid4().hex[:12]}@enervision.fr",
        password_hash="$argon2id$x",
        role=Role.LECTEUR,
    )
    return compte.id


async def un_jeton(
    depot: RefreshTokenRepository,
    user_id: uuid.UUID,
    *,
    family_id: uuid.UUID | None = None,
    duree: timedelta = DUREE,
) -> tuple[str, uuid.UUID]:
    secret = generate_refresh_secret()
    jeton = await depot.create(
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        token_hash=fingerprint_refresh(secret),
        expires_at=datetime.now(UTC) + duree,
        client_ip="203.0.113.10",
        user_agent="pytest",
    )
    return secret, jeton.family_id


async def test_claim_for_rotation_only_succeeds_once(session: AsyncSession) -> None:
    depot = RefreshTokenRepository(session)
    secret, _ = await un_jeton(depot, await un_compte(session))

    premier = await depot.claim_for_rotation(fingerprint_refresh(secret))
    second = await depot.claim_for_rotation(fingerprint_refresh(secret))
    await session.rollback()

    assert premier is not None
    assert second is None


async def test_claim_for_rotation_refuses_an_expired_token(session: AsyncSession) -> None:
    depot = RefreshTokenRepository(session)
    secret, _ = await un_jeton(depot, await un_compte(session), duree=-timedelta(minutes=1))

    revendique = await depot.claim_for_rotation(fingerprint_refresh(secret))
    await session.rollback()

    assert revendique is None


async def test_claim_for_rotation_returns_nothing_for_an_unknown_fingerprint(
    session: AsyncSession,
) -> None:
    revendique = await RefreshTokenRepository(session).claim_for_rotation(
        fingerprint_refresh(generate_refresh_secret())
    )

    assert revendique is None


async def test_inspect_finds_a_token_that_rotation_already_refused(
    session: AsyncSession,
) -> None:
    depot = RefreshTokenRepository(session)
    secret, _ = await un_jeton(depot, await un_compte(session))
    await depot.claim_for_rotation(fingerprint_refresh(secret))

    ligne = await depot.inspect(fingerprint_refresh(secret))
    rotation, motif = (ligne.rotated_at, ligne.revoked_reason) if ligne else (None, None)
    await session.rollback()

    assert rotation is not None
    assert motif == RevocationReason.ROTATION.value


async def test_revoke_family_touches_every_living_token_of_that_family_only(
    session: AsyncSession,
) -> None:
    depot = RefreshTokenRepository(session)
    compte = await un_compte(session)
    famille = uuid.uuid4()
    await un_jeton(depot, compte, family_id=famille)
    await un_jeton(depot, compte, family_id=famille)
    autre_secret, _ = await un_jeton(depot, compte)

    revoquees = await depot.revoke_family(famille, RevocationReason.REUTILISATION)
    intacte = await depot.claim_for_rotation(fingerprint_refresh(autre_secret))
    await session.rollback()

    assert revoquees == 2
    assert intacte is not None


async def test_revoke_family_is_idempotent(session: AsyncSession) -> None:
    depot = RefreshTokenRepository(session)
    compte = await un_compte(session)
    famille = uuid.uuid4()
    await un_jeton(depot, compte, family_id=famille)

    premier = await depot.revoke_family(famille, RevocationReason.DECONNEXION)
    second = await depot.revoke_family(famille, RevocationReason.DECONNEXION)
    await session.rollback()

    assert premier == 1
    assert second == 0


async def test_revoke_all_for_user_closes_every_family_at_once(session: AsyncSession) -> None:
    depot = RefreshTokenRepository(session)
    compte = await un_compte(session)
    await un_jeton(depot, compte)
    await un_jeton(depot, compte)
    await un_jeton(depot, compte)

    revoquees = await depot.revoke_all_for_user(compte, RevocationReason.CHANGEMENT_MOT_DE_PASSE)
    await session.rollback()

    assert revoquees == 3


async def test_link_replacement_records_the_successor(session: AsyncSession) -> None:
    depot = RefreshTokenRepository(session)
    compte = await un_compte(session)
    ancien_secret, famille = await un_jeton(depot, compte)
    revendique = await depot.claim_for_rotation(fingerprint_refresh(ancien_secret))
    assert revendique is not None
    nouveau_secret = generate_refresh_secret()
    nouveau = await depot.create(
        user_id=compte,
        family_id=famille,
        token_hash=fingerprint_refresh(nouveau_secret),
        expires_at=revendique.expires_at,
        client_ip=None,
        user_agent=None,
    )

    await depot.link_replacement(revendique.id, nouveau.id)
    ligne = await depot.inspect(fingerprint_refresh(ancien_secret))
    successeur = ligne.replaced_by if ligne else None
    await session.rollback()

    assert successeur == nouveau.id


async def test_the_database_refuses_two_tokens_sharing_a_fingerprint(
    session: AsyncSession,
) -> None:
    depot = RefreshTokenRepository(session)
    compte = await un_compte(session)
    secret = generate_refresh_secret()
    await depot.create(
        user_id=compte,
        family_id=uuid.uuid4(),
        token_hash=fingerprint_refresh(secret),
        expires_at=datetime.now(UTC) + DUREE,
        client_ip=None,
        user_agent=None,
    )

    famille = uuid.uuid4()
    empreinte = fingerprint_refresh(secret)
    expiration = datetime.now(UTC) + DUREE

    with pytest.raises(IntegrityError):
        await depot.create(
            user_id=compte,
            family_id=famille,
            token_hash=empreinte,
            expires_at=expiration,
            client_ip=None,
            user_agent=None,
        )
    await session.rollback()
