import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import AccountKind, Role
from app.repositories.user import UserRepository

pytestmark = pytest.mark.integration


def adresse() -> str:
    return f"compte-{uuid.uuid4().hex[:12]}@enervision.fr"


async def test_create_normalises_the_email_to_lower_case(session: AsyncSession) -> None:
    depot = UserRepository(session)
    saisie = adresse().upper()

    compte = await depot.create(email=saisie, password_hash="$argon2id$x", role=Role.LECTEUR)
    enregistre = compte.email
    await session.rollback()

    assert enregistre == saisie.lower()


async def test_the_database_refuses_an_email_written_in_upper_case(
    session: AsyncSession,
) -> None:
    saisie = adresse().upper()

    requete = text(
        "insert into app_user (email, password_hash, role) values (:e, '$argon2id$x', 'lecteur')"
    )

    with pytest.raises(IntegrityError):
        await session.execute(requete, {"e": saisie})
    await session.rollback()


async def test_the_database_refuses_two_accounts_sharing_an_email(
    session: AsyncSession,
) -> None:
    depot = UserRepository(session)
    saisie = adresse()

    await depot.create(email=saisie, password_hash="$argon2id$x", role=Role.LECTEUR)

    with pytest.raises(IntegrityError):
        await depot.create(email=saisie, password_hash="$argon2id$y", role=Role.ADMIN)
    await session.rollback()


async def test_get_by_email_is_case_insensitive(session: AsyncSession) -> None:
    depot = UserRepository(session)
    saisie = adresse()
    await depot.create(email=saisie, password_hash="$argon2id$x", role=Role.OPERATEUR)

    trouve = await depot.get_by_email(saisie.upper())
    role = trouve.role if trouve else None
    await session.rollback()

    assert role == Role.OPERATEUR.value


async def test_get_by_email_returns_nothing_for_an_unknown_address(
    session: AsyncSession,
) -> None:
    trouve = await UserRepository(session).get_by_email(adresse())

    assert trouve is None


async def test_set_role_moves_the_credentials_marker_forward(session: AsyncSession) -> None:
    depot = UserRepository(session)
    compte = await depot.create(email=adresse(), password_hash="$argon2id$x", role=Role.LECTEUR)
    avant = compte.credentials_changed_at

    await depot.set_role(compte.id, Role.ADMIN)
    await session.refresh(compte)
    apres, role = compte.credentials_changed_at, compte.role
    await session.rollback()

    assert role == Role.ADMIN.value
    assert apres > avant


async def test_set_active_moves_the_credentials_marker_forward(session: AsyncSession) -> None:
    depot = UserRepository(session)
    compte = await depot.create(email=adresse(), password_hash="$argon2id$x", role=Role.LECTEUR)
    avant = compte.credentials_changed_at

    await depot.set_active(compte.id, is_active=False)
    await session.refresh(compte)
    apres, actif = compte.credentials_changed_at, compte.is_active
    await session.rollback()

    assert actif is False
    assert apres > avant


async def test_rehash_password_leaves_the_credentials_marker_untouched(
    session: AsyncSession,
) -> None:
    depot = UserRepository(session)
    compte = await depot.create(email=adresse(), password_hash="$argon2id$x", role=Role.LECTEUR)
    avant = compte.credentials_changed_at

    await depot.rehash_password(compte.id, "$argon2id$plus-recent")
    await session.refresh(compte)
    apres, empreinte = compte.credentials_changed_at, compte.password_hash
    await session.rollback()

    assert empreinte == "$argon2id$plus-recent"
    assert apres == avant


async def test_update_password_moves_the_credentials_marker_forward(
    session: AsyncSession,
) -> None:
    depot = UserRepository(session)
    compte = await depot.create(email=adresse(), password_hash="$argon2id$x", role=Role.LECTEUR)
    avant = compte.credentials_changed_at

    await depot.update_password(compte.id, "$argon2id$neuf", must_change_password=False)
    await session.refresh(compte)
    apres = compte.credentials_changed_at
    await session.rollback()

    assert apres > avant


async def test_touch_last_login_records_the_connection_date(session: AsyncSession) -> None:
    depot = UserRepository(session)
    compte = await depot.create(email=adresse(), password_hash="$argon2id$x", role=Role.LECTEUR)

    await depot.touch_last_login(compte.id)
    await session.refresh(compte)
    date = compte.last_login_at
    await session.rollback()

    assert date is not None


async def test_count_active_admins_only_counts_enabled_administrators(
    session: AsyncSession,
) -> None:
    depot = UserRepository(session)
    depart = await depot.count_active_admins()

    await depot.create(email=adresse(), password_hash="$argon2id$x", role=Role.ADMIN)
    desactive = await depot.create(email=adresse(), password_hash="$argon2id$x", role=Role.ADMIN)
    await depot.set_active(desactive.id, is_active=False)
    total = await depot.count_active_admins()
    await session.rollback()

    assert total == depart + 1


async def test_create_accepts_a_service_account(session: AsyncSession) -> None:
    depot = UserRepository(session)

    compte = await depot.create(
        email=adresse(),
        password_hash="$argon2id$x",
        role=Role.OPERATEUR,
        kind=AccountKind.SERVICE,
    )
    nature = compte.kind
    await session.rollback()

    assert nature == AccountKind.SERVICE.value


async def test_list_all_returns_the_accounts_sorted_by_email(session: AsyncSession) -> None:
    depot = UserRepository(session)
    await depot.create(email=f"zz-{adresse()}", password_hash="$argon2id$x", role=Role.LECTEUR)
    await depot.create(email=f"aa-{adresse()}", password_hash="$argon2id$x", role=Role.LECTEUR)

    comptes = await depot.list_all()
    emails = [compte.email for compte in comptes]
    await session.rollback()

    assert emails == sorted(emails)


async def test_get_by_id_returns_nothing_for_an_unknown_identifier(
    session: AsyncSession,
) -> None:
    trouve = await UserRepository(session).get_by_id(uuid.uuid4())

    assert trouve is None
