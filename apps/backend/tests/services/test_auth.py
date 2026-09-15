from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.security import TokenPolicy, decode_access_token
from app.models.login_attempt import LoginOutcome
from app.repositories.login_attempt import FailureCounts
from app.services.auth import (
    AuthService,
    InvalidCredentialsError,
    LoginPolicy,
    RateLimitedError,
)

POLITIQUE_JETON = TokenPolicy(
    secret="un-secret-de-test-de-plus-de-trente-deux-caracteres",
    issuer="enervision-api",
    audience="enervision-web",
    access_ttl=timedelta(minutes=15),
)
POLITIQUE_CONNEXION = LoginPolicy(
    window_seconds=900,
    max_failures_per_identifier_and_ip=5,
    max_failures_per_ip=20,
    max_failures_per_identifier=50,
)


@dataclass
class FauxCompte:
    id: UUID = field(default_factory=uuid4)
    email: str = "operateur@enervision.fr"
    password_hash: str = "$argon2id$factice"
    role: str = "operateur"
    kind: str = "human"
    is_active: bool = True
    must_change_password: bool = False
    credentials_changed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FauxDepotComptes:
    def __init__(self, compte: FauxCompte | None) -> None:
        self.compte = compte
        self.rehachages = 0
        self.connexions_datees = 0

    async def get_by_email(self, email: str) -> FauxCompte | None:
        return self.compte

    async def rehash_password(self, user_id: UUID, password_hash: str) -> None:
        self.rehachages += 1

    async def touch_last_login(self, user_id: UUID) -> None:
        self.connexions_datees += 1


class FauxDepotTentatives:
    def __init__(self, compteurs: FailureCounts | None = None) -> None:
        self.compteurs = compteurs or FailureCounts(0, 0, 0)
        self.enregistrees: list[str] = []

    async def count_recent_failures(self, **_: object) -> FailureCounts:
        return self.compteurs

    async def record(self, *, outcome: object, **_: object) -> None:
        self.enregistrees.append(str(outcome))


class FauxDepotAudit:
    def __init__(self) -> None:
        self.lignes: list[tuple[str, Mapping[str, Any] | None]] = []

    async def record(self, *, action: object, detail: Any = None, **_: object) -> None:
        self.lignes.append((str(action), detail))


class FauxHacheur:
    def __init__(self, *, accepte: bool = True, rehachage_requis: bool = False) -> None:
        self.verifications = 0
        self.hachages = 0
        self._accepte = accepte
        self._rehachage_requis = rehachage_requis

    async def hash(self, password: str) -> str:
        self.hachages += 1
        return "$argon2id$nouvelle"

    async def verify(self, stored: str, password: str) -> bool:
        self.verifications += 1
        return self._accepte

    async def verify_dummy(self) -> None:
        self.verifications += 1

    def needs_rehash(self, stored: str) -> bool:
        return self._rehachage_requis


class FausseTransaction:
    def __init__(self) -> None:
        self.validations = 0

    async def commit(self) -> None:
        self.validations += 1


def fabrique_service(
    *,
    compte: FauxCompte | None = None,
    compteurs: FailureCounts | None = None,
    hacheur: FauxHacheur | None = None,
) -> tuple[AuthService, FauxDepotComptes, FauxDepotTentatives, FauxDepotAudit, FauxHacheur]:
    comptes = FauxDepotComptes(compte)
    tentatives = FauxDepotTentatives(compteurs)
    audit = FauxDepotAudit()
    hacheur = hacheur or FauxHacheur()
    service = AuthService(
        users=comptes,  # type: ignore[arg-type]
        attempts=tentatives,  # type: ignore[arg-type]
        audit=audit,  # type: ignore[arg-type]
        hasher=hacheur,  # type: ignore[arg-type]
        transaction=FausseTransaction(),
        token_policy=POLITIQUE_JETON,
        login_policy=POLITIQUE_CONNEXION,
    )
    return service, comptes, tentatives, audit, hacheur


async def connecte(service: AuthService, mot_de_passe: str = "un-mot-de-passe-valide") -> object:
    return await service.authenticate(
        email="operateur@enervision.fr",
        password=mot_de_passe,
        client_ip="203.0.113.10",
        user_agent="pytest",
    )


async def test_authenticate_returns_a_readable_access_token_when_credentials_match() -> None:
    compte = FauxCompte()
    service, comptes, tentatives, _, _ = fabrique_service(compte=compte)

    session = await connecte(service)

    claims = decode_access_token(POLITIQUE_JETON, session.access_token)  # type: ignore[attr-defined]
    assert claims.subject == compte.id
    assert claims.role == "operateur"
    assert tentatives.enregistrees == [LoginOutcome.SUCCES.value]
    assert comptes.connexions_datees == 1


async def test_authenticate_verifies_a_decoy_digest_when_the_email_is_unknown() -> None:
    service, _, tentatives, _, hacheur = fabrique_service(compte=None)

    with pytest.raises(InvalidCredentialsError):
        await connecte(service)

    assert hacheur.verifications == 1
    assert tentatives.enregistrees == [LoginOutcome.IDENTIFIANTS_INVALIDES.value]


async def test_authenticate_skips_hashing_entirely_when_the_rate_limit_is_reached() -> None:
    compteurs = FailureCounts(per_identifier_and_ip=5, per_ip=5, per_identifier=5)
    service, _, tentatives, audit, hacheur = fabrique_service(
        compte=FauxCompte(), compteurs=compteurs
    )

    with pytest.raises(RateLimitedError):
        await connecte(service)

    assert hacheur.verifications == 0
    assert hacheur.hachages == 0
    assert tentatives.enregistrees == [LoginOutcome.LIMITE.value]
    assert audit.lignes == []


async def test_authenticate_audits_when_the_identifier_threshold_alone_is_reached() -> None:
    compteurs = FailureCounts(per_identifier_and_ip=0, per_ip=0, per_identifier=50)
    service, _, _, audit, _ = fabrique_service(compte=FauxCompte(), compteurs=compteurs)

    with pytest.raises(RateLimitedError):
        await connecte(service)

    assert len(audit.lignes) == 1
    assert "identifier_throttled" in audit.lignes[0][0]


async def test_authenticate_rejects_a_wrong_password_with_the_generic_error() -> None:
    service, _, tentatives, _, _ = fabrique_service(
        compte=FauxCompte(), hacheur=FauxHacheur(accepte=False)
    )

    with pytest.raises(InvalidCredentialsError):
        await connecte(service)

    assert tentatives.enregistrees == [LoginOutcome.IDENTIFIANTS_INVALIDES.value]


@pytest.mark.parametrize(
    "compte",
    [FauxCompte(is_active=False), FauxCompte(kind="service")],
    ids=["compte_desactive", "compte_de_service"],
)
async def test_authenticate_rejects_unavailable_accounts_after_checking_the_password(
    compte: FauxCompte,
) -> None:
    service, _, tentatives, _, hacheur = fabrique_service(compte=compte)

    with pytest.raises(InvalidCredentialsError):
        await connecte(service)

    assert hacheur.verifications == 1
    assert tentatives.enregistrees == [LoginOutcome.COMPTE_INDISPONIBLE.value]


async def test_authenticate_rehashes_the_password_when_the_parameters_changed() -> None:
    service, comptes, _, _, _ = fabrique_service(
        compte=FauxCompte(), hacheur=FauxHacheur(rehachage_requis=True)
    )

    await connecte(service)

    assert comptes.rehachages == 1


async def test_authenticate_leaves_the_digest_alone_when_the_parameters_match() -> None:
    service, comptes, _, _, _ = fabrique_service(compte=FauxCompte())

    await connecte(service)

    assert comptes.rehachages == 0
