# Les trois refus ci-dessous sont la preuve que l'ajout seul est une propriété de la base et
# non une convention de code Python. Ce sont eux qu'il faut montrer, pas la classe du dépôt.

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.models.audit_log import AuditAction, AuditOutcome
from app.repositories.audit_log import (
    CLES_DE_DETAIL_AUTORISEES,
    AuditLogRepository,
    assemble_detail,
)

pytestmark = pytest.mark.integration

ACTEUR = Principal(
    id=uuid.uuid4(),
    email="admin@enervision.fr",
    role=Role.ADMIN,
    kind=AccountKind.HUMAIN,
    must_change_password=False,
)


async def une_ligne(session: AsyncSession) -> None:
    await AuditLogRepository(session).record(
        action=AuditAction.COMPTE_CREE, actor=ACTEUR, target_type="app_user", target_id="x"
    )
    await session.flush()


@pytest.mark.parametrize(
    "instruction",
    [
        "update audit_log set action = 'falsifie'",
        "delete from audit_log",
        "truncate audit_log",
    ],
    ids=["modification", "suppression", "vidage"],
)
async def test_the_database_refuses_to_mutate_the_audit_log(
    session: AsyncSession, instruction: str
) -> None:
    await une_ligne(session)

    with pytest.raises(DBAPIError, match="ajout seul"):
        await session.execute(text(instruction))
    await session.rollback()


async def test_record_keeps_a_snapshot_of_the_actor(session: AsyncSession) -> None:
    depot = AuditLogRepository(session)

    await depot.record(action=AuditAction.COMPTE_DESACTIVE, actor=ACTEUR)
    await session.flush()
    ligne = (
        await session.execute(
            text("select actor_id, actor_email, actor_role, outcome from audit_log")
        )
    ).one()
    await session.rollback()

    assert ligne.actor_id == ACTEUR.id
    assert ligne.actor_email == ACTEUR.email
    assert ligne.actor_role == Role.ADMIN.value
    assert ligne.outcome == AuditOutcome.SUCCES.value


async def test_record_accepts_a_label_when_there_is_no_authenticated_actor(
    session: AsyncSession,
) -> None:
    depot = AuditLogRepository(session)

    await depot.record(action=AuditAction.ADMIN_AMORCE, actor_label="cli")
    await session.flush()
    ligne = (await session.execute(text("select actor_id, actor_email from audit_log"))).one()
    await session.rollback()

    assert ligne.actor_id is None
    assert ligne.actor_email == "cli"


async def test_record_drops_the_detail_keys_outside_the_allow_list(
    session: AsyncSession,
) -> None:
    depot = AuditLogRepository(session)

    await depot.record(
        action=AuditAction.COMPTE_ROLE_CHANGE,
        actor=ACTEUR,
        detail={"role_avant": "lecteur", "mot_de_passe": "ne-doit-pas-passer"},
    )
    await session.flush()
    detail = (await session.execute(text("select detail from audit_log"))).scalar_one()
    await session.rollback()

    assert detail == {"role_avant": "lecteur"}


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        (None, {}),
        ({}, {}),
        ({"motif": "reutilisation"}, {"motif": "reutilisation"}),
        ({"password": "x"}, {}),
    ],
    ids=["absent", "vide", "cle_autorisee", "cle_refusee"],
)
def test_assemble_detail_only_keeps_the_allowed_keys(
    brut: dict[str, str] | None, attendu: dict[str, str]
) -> None:
    assert assemble_detail(brut) == attendu


def test_the_allow_list_never_mentions_a_secret() -> None:
    suspects = {"password", "mot_de_passe", "token", "jeton", "secret", "hash"}

    assert CLES_DE_DETAIL_AUTORISEES & suspects == set()
