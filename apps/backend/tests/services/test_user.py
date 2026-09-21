from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.models.refresh_token import RevocationReason
from app.services.user import (
    EmailAlreadyUsedError,
    LastAdminError,
    UserNotFoundError,
    UserService,
)

ADMIN = Principal(
    id=uuid4(),
    email="admin@enervision.fr",
    role=Role.ADMIN,
    kind=AccountKind.HUMAIN,
    must_change_password=False,
)


@dataclass
class FauxCompte:
    id: UUID = field(default_factory=uuid4)
    email: str = "lecteur@enervision.fr"
    password_hash: str = "$argon2id$factice"
    role: str = "lecteur"
    kind: str = "human"
    is_active: bool = True
    must_change_password: bool = False
    full_name: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FauxDepotComptes:
    def __init__(
        self, compte: FauxCompte | None = None, *, admins_actifs: int = 2, existe: bool = False
    ) -> None:
        self.compte = compte
        self.admins_actifs = admins_actifs
        self.existe = existe
        self.crees: list[str] = []
        self.roles_poses: list[tuple[UUID, str]] = []
        self.activations: list[tuple[UUID, bool]] = []
        self.mots_de_passe: list[UUID] = []

    async def get_by_email(self, email: str) -> FauxCompte | None:
        return self.compte if self.existe else None

    async def get_by_id(self, user_id: UUID) -> FauxCompte | None:
        return self.compte

    async def count_active_admins(self) -> int:
        return self.admins_actifs

    async def create(self, *, email: str, **_: object) -> FauxCompte:
        self.crees.append(email)
        return FauxCompte(email=email)

    async def set_role(self, user_id: UUID, role: Role) -> None:
        self.roles_poses.append((user_id, role.value))

    async def set_active(self, user_id: UUID, *, is_active: bool) -> None:
        self.activations.append((user_id, is_active))

    async def update_password(self, user_id: UUID, password_hash: str, **_: object) -> None:
        self.mots_de_passe.append(user_id)


class FauxDepotJetons:
    def __init__(self) -> None:
        self.revocations: list[tuple[UUID, str]] = []

    async def revoke_all_for_user(self, user_id: UUID, reason: RevocationReason) -> int:
        self.revocations.append((user_id, reason.value))
        return 2


class FauxDepotAudit:
    def __init__(self) -> None:
        self.lignes: list[tuple[str, Any]] = []

    async def record(self, *, action: object, detail: Any = None, **_: object) -> None:
        self.lignes.append((str(action), detail))


class FauxHacheur:
    async def hash(self, password: str) -> str:
        return "$argon2id$nouvelle"


class FausseTransaction:
    async def commit(self) -> None:
        return None


@dataclass
class Attirail:
    service: UserService
    comptes: FauxDepotComptes
    jetons: FauxDepotJetons
    audit: FauxDepotAudit


def fabrique(
    compte: FauxCompte | None = None, *, admins_actifs: int = 2, existe: bool = False
) -> Attirail:
    comptes = FauxDepotComptes(compte, admins_actifs=admins_actifs, existe=existe)
    jetons = FauxDepotJetons()
    audit = FauxDepotAudit()
    service = UserService(
        users=comptes,  # type: ignore[arg-type]
        refresh_tokens=jetons,  # type: ignore[arg-type]
        audit=audit,  # type: ignore[arg-type]
        hasher=FauxHacheur(),  # type: ignore[arg-type]
        transaction=FausseTransaction(),
    )
    return Attirail(service, comptes, jetons, audit)


async def test_create_returns_a_temporary_password_shown_once() -> None:
    attirail = fabrique()

    cree = await attirail.service.create(
        actor=ADMIN, email="nouveau@enervision.fr", role=Role.LECTEUR, full_name=None
    )

    assert len(cree.temporary_password) >= 18
    assert attirail.comptes.crees == ["nouveau@enervision.fr"]
    assert "user.created" in attirail.audit.lignes[0][0]


async def test_create_refuses_an_address_already_taken() -> None:
    attirail = fabrique(FauxCompte(), existe=True)

    with pytest.raises(EmailAlreadyUsedError):
        await attirail.service.create(
            actor=ADMIN, email="lecteur@enervision.fr", role=Role.LECTEUR, full_name=None
        )


async def test_change_role_revokes_every_session_of_the_target() -> None:
    cible = FauxCompte()
    attirail = fabrique(cible)

    await attirail.service.change_role(actor=ADMIN, user_id=cible.id, role=Role.OPERATEUR)

    assert attirail.comptes.roles_poses == [(cible.id, "operateur")]
    assert attirail.jetons.revocations == [(cible.id, RevocationReason.ADMINISTRATION.value)]


async def test_change_role_does_nothing_when_the_role_is_already_the_right_one() -> None:
    cible = FauxCompte(role="operateur")
    attirail = fabrique(cible)

    await attirail.service.change_role(actor=ADMIN, user_id=cible.id, role=Role.OPERATEUR)

    assert attirail.comptes.roles_poses == []
    assert attirail.jetons.revocations == []


async def test_change_role_refuses_to_demote_the_last_active_administrator() -> None:
    dernier = FauxCompte(role="admin")
    attirail = fabrique(dernier, admins_actifs=1)

    with pytest.raises(LastAdminError):
        await attirail.service.change_role(actor=ADMIN, user_id=dernier.id, role=Role.LECTEUR)


async def test_change_role_accepts_a_demotion_when_another_administrator_remains() -> None:
    admin = FauxCompte(role="admin")
    attirail = fabrique(admin, admins_actifs=2)

    await attirail.service.change_role(actor=ADMIN, user_id=admin.id, role=Role.LECTEUR)

    assert attirail.comptes.roles_poses == [(admin.id, "lecteur")]


async def test_set_active_refuses_to_disable_the_last_active_administrator() -> None:
    dernier = FauxCompte(role="admin")
    attirail = fabrique(dernier, admins_actifs=1)

    with pytest.raises(LastAdminError):
        await attirail.service.set_active(actor=ADMIN, user_id=dernier.id, is_active=False)


async def test_set_active_revokes_the_sessions_when_disabling() -> None:
    cible = FauxCompte()
    attirail = fabrique(cible)

    await attirail.service.set_active(actor=ADMIN, user_id=cible.id, is_active=False)

    assert attirail.comptes.activations == [(cible.id, False)]
    assert attirail.jetons.revocations == [(cible.id, RevocationReason.ADMINISTRATION.value)]


async def test_set_active_leaves_the_sessions_alone_when_enabling() -> None:
    cible = FauxCompte(is_active=False)
    attirail = fabrique(cible)

    await attirail.service.set_active(actor=ADMIN, user_id=cible.id, is_active=True)

    assert attirail.jetons.revocations == []


async def test_reset_password_closes_every_session_and_forces_a_change() -> None:
    cible = FauxCompte()
    attirail = fabrique(cible)

    reinitialise = await attirail.service.reset_password(actor=ADMIN, user_id=cible.id)

    assert len(reinitialise.temporary_password) >= 18
    assert attirail.comptes.mots_de_passe == [cible.id]
    assert attirail.jetons.revocations == [
        (cible.id, RevocationReason.CHANGEMENT_MOT_DE_PASSE.value)
    ]


@pytest.mark.parametrize(
    "action",
    ["change_role", "set_active", "reset_password"],
    ids=["changement_de_role", "activation", "reinitialisation"],
)
async def test_every_operation_refuses_an_unknown_account(action: str) -> None:
    attirail = fabrique(None)
    arguments: dict[str, Any] = {"actor": ADMIN, "user_id": uuid4()}
    if action == "change_role":
        arguments["role"] = Role.ADMIN
    if action == "set_active":
        arguments["is_active"] = False

    methode = getattr(attirail.service, action)

    with pytest.raises(UserNotFoundError):
        await methode(**arguments)
