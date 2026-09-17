from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks

from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.core.security import (
    TokenPolicy,
    decode_access_token,
    fingerprint_refresh,
)
from app.models.login_attempt import LoginOutcome
from app.models.refresh_token import RevocationReason
from app.repositories.login_attempt import FailureCounts
from app.repositories.password_reset_attempt import ResetRequestCounts
from app.repositories.password_reset_token import ConsumedResetToken
from app.repositories.refresh_token import ClaimedToken
from app.services.auth import (
    AuthService,
    InvalidCredentialsError,
    InvalidOrExpiredResetTokenError,
    LoginPolicy,
    PasswordResetPolicy,
    RateLimitedError,
    SessionRejectedError,
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
POLITIQUE_RESET = PasswordResetPolicy(
    window_seconds=900,
    max_requests_per_identifier=3,
    max_requests_per_ip=10,
    token_ttl=timedelta(minutes=15),
    frontend_reset_url="http://localhost:4200/reset-password",
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
        self.mots_de_passe_changes = 0

    async def get_by_email(self, email: str) -> FauxCompte | None:
        return self.compte

    async def get_by_id(self, user_id: UUID) -> FauxCompte | None:
        return self.compte

    async def rehash_password(self, user_id: UUID, password_hash: str) -> None:
        self.rehachages += 1

    async def update_password(self, user_id: UUID, password_hash: str, **_: object) -> None:
        self.mots_de_passe_changes += 1

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


@dataclass
class FauxJeton:
    id: UUID = field(default_factory=uuid4)
    family_id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(days=7))
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None


class FauxDepotJetons:
    def __init__(
        self, revendique: ClaimedToken | None = None, connu: FauxJeton | None = None
    ) -> None:
        self.revendique = revendique
        self.connu = connu
        self.crees: list[UUID] = []
        self.familles_revoquees: list[tuple[UUID, str]] = []
        self.revocations_par_compte: list[tuple[UUID, str]] = []
        self.liaisons: list[tuple[UUID, UUID]] = []

    async def create(self, *, user_id: UUID, family_id: UUID, **_: object) -> FauxJeton:
        jeton = FauxJeton(user_id=user_id, family_id=family_id)
        self.crees.append(jeton.id)
        return jeton

    async def claim_for_rotation(self, token_hash: bytes) -> ClaimedToken | None:
        return self.revendique

    async def inspect(self, token_hash: bytes) -> FauxJeton | None:
        return self.connu

    async def link_replacement(self, ancien_id: UUID, nouveau_id: UUID) -> None:
        self.liaisons.append((ancien_id, nouveau_id))

    async def revoke_family(self, family_id: UUID, reason: RevocationReason) -> int:
        self.familles_revoquees.append((family_id, reason.value))
        return 2

    async def revoke_all_for_user(self, user_id: UUID, reason: RevocationReason) -> int:
        self.revocations_par_compte.append((user_id, reason.value))
        return 3


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


class FauxDepotJetonsReset:
    def __init__(self, revendique: ConsumedResetToken | None = None) -> None:
        self.revendique = revendique
        self.crees: list[UUID] = []
        self.invalidations: list[UUID] = []

    async def create(self, *, user_id: UUID, **_: object) -> None:
        self.crees.append(user_id)

    async def consume(self, token_hash: bytes) -> ConsumedResetToken | None:
        return self.revendique

    async def invalidate_all_for_user(self, user_id: UUID) -> int:
        self.invalidations.append(user_id)
        return len(self.invalidations)


class FauxDepotTentativesReset:
    def __init__(self, compteurs: ResetRequestCounts | None = None) -> None:
        self.compteurs = compteurs or ResetRequestCounts(0, 0)
        self.enregistrees: list[str] = []

    async def count_recent(self, **_: object) -> ResetRequestCounts:
        return self.compteurs

    async def record(self, *, email: str, **_: object) -> None:
        self.enregistrees.append(email)


class FauxMailer:
    def __init__(self) -> None:
        self.envois: list[tuple[str, str]] = []

    async def send_password_reset_email(self, *, to: str, reset_url: str) -> None:
        self.envois.append((to, reset_url))


@dataclass
class Attirail:
    service: AuthService
    comptes: FauxDepotComptes
    tentatives: FauxDepotTentatives
    jetons: FauxDepotJetons
    audit: FauxDepotAudit
    hacheur: FauxHacheur
    jetons_reset: FauxDepotJetonsReset
    tentatives_reset: FauxDepotTentativesReset
    mailer: FauxMailer


def fabrique_service(
    *,
    compte: FauxCompte | None = None,
    compteurs: FailureCounts | None = None,
    hacheur: FauxHacheur | None = None,
    jetons: FauxDepotJetons | None = None,
    jetons_reset: FauxDepotJetonsReset | None = None,
    compteurs_reset: ResetRequestCounts | None = None,
) -> Attirail:
    comptes = FauxDepotComptes(compte)
    tentatives = FauxDepotTentatives(compteurs)
    depot_jetons = jetons or FauxDepotJetons()
    audit = FauxDepotAudit()
    hacheur = hacheur or FauxHacheur()
    depot_jetons_reset = jetons_reset or FauxDepotJetonsReset()
    tentatives_reset = FauxDepotTentativesReset(compteurs_reset)
    mailer = FauxMailer()
    service = AuthService(
        users=comptes,  # type: ignore[arg-type]
        attempts=tentatives,  # type: ignore[arg-type]
        refresh_tokens=depot_jetons,  # type: ignore[arg-type]
        audit=audit,  # type: ignore[arg-type]
        hasher=hacheur,  # type: ignore[arg-type]
        transaction=FausseTransaction(),
        token_policy=POLITIQUE_JETON,
        login_policy=POLITIQUE_CONNEXION,
        refresh_ttl=timedelta(days=7),
        reset_tokens=depot_jetons_reset,  # type: ignore[arg-type]
        reset_attempts=tentatives_reset,  # type: ignore[arg-type]
        reset_policy=POLITIQUE_RESET,
        mailer=mailer,  # type: ignore[arg-type]
    )
    return Attirail(
        service,
        comptes,
        tentatives,
        depot_jetons,
        audit,
        hacheur,
        depot_jetons_reset,
        tentatives_reset,
        mailer,
    )


async def connecte(service: AuthService, mot_de_passe: str = "un-mot-de-passe-valide") -> object:
    return await service.authenticate(
        email="operateur@enervision.fr",
        password=mot_de_passe,
        client_ip="203.0.113.10",
        user_agent="pytest",
    )


async def rafraichit(service: AuthService, secret: str = "un-secret-opaque") -> object:
    return await service.refresh(secret=secret, client_ip="203.0.113.10", user_agent="pytest")


async def test_authenticate_returns_a_readable_access_token_when_credentials_match() -> None:
    compte = FauxCompte()
    attirail = fabrique_service(compte=compte)

    session = await connecte(attirail.service)

    claims = decode_access_token(POLITIQUE_JETON, session.access_token)  # type: ignore[attr-defined]
    assert claims.subject == compte.id
    assert claims.role == "operateur"
    assert attirail.tentatives.enregistrees == [LoginOutcome.SUCCES.value]
    assert attirail.comptes.connexions_datees == 1


async def test_authenticate_opens_one_refresh_family_per_login() -> None:
    attirail = fabrique_service(compte=FauxCompte())

    session = await connecte(attirail.service)

    assert len(attirail.jetons.crees) == 1
    assert session.refresh_secret  # type: ignore[attr-defined]


async def test_authenticate_verifies_a_decoy_digest_when_the_email_is_unknown() -> None:
    attirail = fabrique_service(compte=None)

    with pytest.raises(InvalidCredentialsError):
        await connecte(attirail.service)

    assert attirail.hacheur.verifications == 1
    assert attirail.tentatives.enregistrees == [LoginOutcome.IDENTIFIANTS_INVALIDES.value]


async def test_authenticate_skips_hashing_entirely_when_the_rate_limit_is_reached() -> None:
    compteurs = FailureCounts(per_identifier_and_ip=5, per_ip=5, per_identifier=5)
    attirail = fabrique_service(compte=FauxCompte(), compteurs=compteurs)

    with pytest.raises(RateLimitedError):
        await connecte(attirail.service)

    assert attirail.hacheur.verifications == 0
    assert attirail.hacheur.hachages == 0
    assert attirail.tentatives.enregistrees == [LoginOutcome.LIMITE.value]
    assert attirail.audit.lignes == []


async def test_authenticate_audits_when_the_identifier_threshold_alone_is_reached() -> None:
    compteurs = FailureCounts(per_identifier_and_ip=0, per_ip=0, per_identifier=50)
    attirail = fabrique_service(compte=FauxCompte(), compteurs=compteurs)

    with pytest.raises(RateLimitedError):
        await connecte(attirail.service)

    assert len(attirail.audit.lignes) == 1
    assert "identifier_throttled" in attirail.audit.lignes[0][0]


async def test_authenticate_rejects_a_wrong_password_with_the_generic_error() -> None:
    attirail = fabrique_service(compte=FauxCompte(), hacheur=FauxHacheur(accepte=False))

    with pytest.raises(InvalidCredentialsError):
        await connecte(attirail.service)

    assert attirail.tentatives.enregistrees == [LoginOutcome.IDENTIFIANTS_INVALIDES.value]


@pytest.mark.parametrize(
    "compte",
    [FauxCompte(is_active=False), FauxCompte(kind="service")],
    ids=["compte_desactive", "compte_de_service"],
)
async def test_authenticate_rejects_unavailable_accounts_after_checking_the_password(
    compte: FauxCompte,
) -> None:
    attirail = fabrique_service(compte=compte)

    with pytest.raises(InvalidCredentialsError):
        await connecte(attirail.service)

    assert attirail.hacheur.verifications == 1
    assert attirail.tentatives.enregistrees == [LoginOutcome.COMPTE_INDISPONIBLE.value]


async def test_authenticate_rehashes_the_password_when_the_parameters_changed() -> None:
    attirail = fabrique_service(compte=FauxCompte(), hacheur=FauxHacheur(rehachage_requis=True))

    await connecte(attirail.service)

    assert attirail.comptes.rehachages == 1


async def test_authenticate_leaves_the_digest_alone_when_the_parameters_match() -> None:
    attirail = fabrique_service(compte=FauxCompte())

    await connecte(attirail.service)

    assert attirail.comptes.rehachages == 0


async def test_refresh_rotates_the_token_and_keeps_the_family() -> None:
    compte = FauxCompte()
    revendique = ClaimedToken(
        id=uuid4(),
        family_id=uuid4(),
        user_id=compte.id,
        expires_at=datetime.now(UTC) + timedelta(days=5),
    )
    attirail = fabrique_service(compte=compte, jetons=FauxDepotJetons(revendique=revendique))

    session = await rafraichit(attirail.service)

    assert session.refresh_secret  # type: ignore[attr-defined]
    assert len(attirail.jetons.crees) == 1
    assert attirail.jetons.liaisons == [(revendique.id, attirail.jetons.crees[0])]
    assert attirail.jetons.familles_revoquees == []


async def test_refresh_inherits_the_absolute_expiry_of_its_predecessor() -> None:
    compte = FauxCompte()
    echeance = datetime.now(UTC) + timedelta(days=2)
    revendique = ClaimedToken(id=uuid4(), family_id=uuid4(), user_id=compte.id, expires_at=echeance)
    attirail = fabrique_service(compte=compte, jetons=FauxDepotJetons(revendique=revendique))

    await rafraichit(attirail.service)

    assert revendique.expires_at == echeance


async def test_refresh_rejects_an_unknown_secret_without_touching_any_family() -> None:
    attirail = fabrique_service(compte=FauxCompte(), jetons=FauxDepotJetons())

    with pytest.raises(SessionRejectedError):
        await rafraichit(attirail.service)

    assert attirail.jetons.familles_revoquees == []
    assert attirail.audit.lignes == []


async def test_refresh_rejects_an_expired_token_without_revoking_its_family() -> None:
    perime = FauxJeton(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    attirail = fabrique_service(compte=FauxCompte(), jetons=FauxDepotJetons(connu=perime))

    with pytest.raises(SessionRejectedError):
        await rafraichit(attirail.service)

    assert attirail.jetons.familles_revoquees == []
    assert attirail.audit.lignes == []


async def test_refresh_revokes_the_whole_family_when_a_rotated_token_comes_back() -> None:
    rejoue = FauxJeton(rotated_at=datetime.now(UTC), revoked_at=datetime.now(UTC))
    attirail = fabrique_service(compte=FauxCompte(), jetons=FauxDepotJetons(connu=rejoue))

    with pytest.raises(SessionRejectedError):
        await rafraichit(attirail.service)

    assert attirail.jetons.familles_revoquees == [
        (rejoue.family_id, RevocationReason.REUTILISATION.value)
    ]
    assert "refresh_reuse_detected" in attirail.audit.lignes[0][0]


async def test_refresh_revokes_the_family_when_the_account_was_disabled_meanwhile() -> None:
    compte = FauxCompte(is_active=False)
    revendique = ClaimedToken(
        id=uuid4(),
        family_id=uuid4(),
        user_id=compte.id,
        expires_at=datetime.now(UTC) + timedelta(days=5),
    )
    attirail = fabrique_service(compte=compte, jetons=FauxDepotJetons(revendique=revendique))

    with pytest.raises(SessionRejectedError):
        await rafraichit(attirail.service)

    assert attirail.jetons.familles_revoquees == [
        (revendique.family_id, RevocationReason.ADMINISTRATION.value)
    ]


async def test_logout_revokes_only_the_presented_family() -> None:
    connu = FauxJeton()
    attirail = fabrique_service(compte=FauxCompte(), jetons=FauxDepotJetons(connu=connu))

    await attirail.service.logout(secret="un-secret-opaque")

    assert attirail.jetons.familles_revoquees == [
        (connu.family_id, RevocationReason.DECONNEXION.value)
    ]
    assert attirail.jetons.revocations_par_compte == []


async def test_logout_stays_silent_when_the_cookie_points_at_nothing() -> None:
    attirail = fabrique_service(compte=FauxCompte(), jetons=FauxDepotJetons())

    await attirail.service.logout(secret="un-secret-inconnu")

    assert attirail.jetons.familles_revoquees == []


async def test_logout_all_revokes_every_session_and_leaves_an_audit_trail() -> None:
    compte = FauxCompte()
    attirail = fabrique_service(compte=compte)
    acteur = Principal(
        id=compte.id,
        email=compte.email,
        role=Role.OPERATEUR,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )

    revoquees = await attirail.service.logout_all(acteur)

    assert revoquees == 3
    assert attirail.jetons.revocations_par_compte == [
        (compte.id, RevocationReason.DECONNEXION.value)
    ]
    assert "all_sessions_revoked" in attirail.audit.lignes[0][0]


def test_fingerprint_is_what_the_service_stores_not_the_secret_itself() -> None:
    secret = "un-secret-opaque"

    empreinte = fingerprint_refresh(secret)

    assert secret.encode() not in empreinte


async def test_change_password_revokes_every_session_then_reopens_the_current_one() -> None:
    compte = FauxCompte()
    attirail = fabrique_service(compte=compte)
    acteur = Principal(
        id=compte.id,
        email=compte.email,
        role=Role.OPERATEUR,
        kind=AccountKind.HUMAIN,
        must_change_password=True,
    )

    session = await attirail.service.change_password(
        principal=acteur,
        current_password="l-ancien-mot-de-passe",
        new_password="le-nouveau-mot-de-passe",
        client_ip="203.0.113.10",
        user_agent="pytest",
    )

    assert attirail.jetons.revocations_par_compte == [
        (compte.id, RevocationReason.CHANGEMENT_MOT_DE_PASSE.value)
    ]
    assert len(attirail.jetons.crees) == 1, "l'appareil courant doit repartir avec une session"
    assert session.refresh_secret
    assert "password_changed" in attirail.audit.lignes[0][0]


async def test_change_password_refuses_a_wrong_current_password() -> None:
    compte = FauxCompte()
    attirail = fabrique_service(compte=compte, hacheur=FauxHacheur(accepte=False))
    acteur = Principal(
        id=compte.id,
        email=compte.email,
        role=Role.OPERATEUR,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )

    with pytest.raises(InvalidCredentialsError):
        await attirail.service.change_password(
            principal=acteur,
            current_password="mauvais",
            new_password="le-nouveau-mot-de-passe",
            client_ip=None,
            user_agent=None,
        )

    assert attirail.jetons.revocations_par_compte == []
    assert attirail.jetons.crees == []


async def test_request_password_reset_emails_a_link_when_the_account_exists() -> None:
    compte = FauxCompte()
    attirail = fabrique_service(compte=compte)
    taches = BackgroundTasks()

    await attirail.service.request_password_reset(
        email=compte.email, client_ip="203.0.113.10", user_agent="pytest", background_tasks=taches
    )

    assert attirail.jetons_reset.invalidations == [compte.id]
    assert attirail.jetons_reset.crees == [compte.id]
    assert attirail.mailer.envois == [], "l'envoi doit être différé, pas fait dans la réponse"
    await taches()
    assert len(attirail.mailer.envois) == 1
    assert attirail.mailer.envois[0][0] == compte.email
    assert "auth.password_reset_requested" in attirail.audit.lignes[0][0]


async def test_request_password_reset_stays_silent_when_the_account_is_unknown() -> None:
    attirail = fabrique_service(compte=None)
    taches = BackgroundTasks()

    await attirail.service.request_password_reset(
        email="inconnu@enervision.fr",
        client_ip="203.0.113.10",
        user_agent="pytest",
        background_tasks=taches,
    )
    await taches()

    assert attirail.jetons_reset.crees == []
    assert attirail.mailer.envois == []
    assert attirail.hacheur.verifications == 1, "le hachage factice doit tout de même tourner"


async def test_request_password_reset_stays_silent_when_the_account_is_inactive() -> None:
    compte = FauxCompte(is_active=False)
    attirail = fabrique_service(compte=compte)
    taches = BackgroundTasks()

    await attirail.service.request_password_reset(
        email=compte.email, client_ip="203.0.113.10", user_agent="pytest", background_tasks=taches
    )
    await taches()

    assert attirail.jetons_reset.crees == []
    assert attirail.mailer.envois == []


async def test_request_password_reset_raises_when_the_rate_limit_is_reached() -> None:
    attirail = fabrique_service(compteurs_reset=ResetRequestCounts(per_identifier=3, per_ip=0))
    taches = BackgroundTasks()

    with pytest.raises(RateLimitedError):
        await attirail.service.request_password_reset(
            email="operateur@enervision.fr",
            client_ip="203.0.113.10",
            user_agent="pytest",
            background_tasks=taches,
        )

    await taches()
    assert attirail.mailer.envois == []


async def test_request_password_reset_logs_instead_of_raising_when_the_mailer_fails() -> None:
    compte = FauxCompte()
    attirail = fabrique_service(compte=compte)
    taches = BackgroundTasks()

    async def echoue(*, to: str, reset_url: str) -> None:
        raise RuntimeError("relais SMTP indisponible")

    attirail.mailer.send_password_reset_email = echoue  # type: ignore[method-assign]

    await attirail.service.request_password_reset(
        email=compte.email, client_ip="203.0.113.10", user_agent="pytest", background_tasks=taches
    )

    await taches()


async def test_confirm_password_reset_revokes_every_session_then_reopens_the_current_one() -> None:
    compte = FauxCompte()
    jetons_reset = FauxDepotJetonsReset(
        revendique=ConsumedResetToken(id=uuid4(), user_id=compte.id)
    )
    attirail = fabrique_service(compte=compte, jetons_reset=jetons_reset)

    session = await attirail.service.confirm_password_reset(
        token="un-secret-opaque",
        new_password="Un-nouveau-mot-de-passe1!",
        client_ip="203.0.113.10",
        user_agent="pytest",
    )

    assert attirail.jetons.revocations_par_compte == [
        (compte.id, RevocationReason.CHANGEMENT_MOT_DE_PASSE.value)
    ]
    assert len(attirail.jetons.crees) == 1
    assert session.refresh_secret
    assert "auth.password_reset_self_service" in attirail.audit.lignes[0][0]


async def test_confirm_password_reset_rejects_a_token_for_an_account_disabled_since() -> None:
    compte = FauxCompte(is_active=False)
    jetons_reset = FauxDepotJetonsReset(
        revendique=ConsumedResetToken(id=uuid4(), user_id=compte.id)
    )
    attirail = fabrique_service(compte=compte, jetons_reset=jetons_reset)

    with pytest.raises(InvalidOrExpiredResetTokenError):
        await attirail.service.confirm_password_reset(
            token="un-secret-opaque",
            new_password="Un-nouveau-mot-de-passe1!",
            client_ip="203.0.113.10",
            user_agent="pytest",
        )

    assert attirail.comptes.mots_de_passe_changes == 0
    assert attirail.jetons.revocations_par_compte == []


async def test_confirm_password_reset_rejects_an_invalid_or_expired_token() -> None:
    attirail = fabrique_service(jetons_reset=FauxDepotJetonsReset(revendique=None))

    with pytest.raises(InvalidOrExpiredResetTokenError):
        await attirail.service.confirm_password_reset(
            token="un-secret-invalide",
            new_password="Un-nouveau-mot-de-passe1!",
            client_ip=None,
            user_agent=None,
        )

    assert attirail.jetons.revocations_par_compte == []
