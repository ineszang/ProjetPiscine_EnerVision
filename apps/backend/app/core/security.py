# Piège : `decode_access_token()` porte trois barrières indépendantes, et retirer l'une
# d'elles ne casse aucun test évident. L'algorithme est épinglé, sinon un jeton forgé en
# `alg: none` passerait. L'audience et l'émetteur sont vérifiés, sinon un jeton émis pour
# un autre service serait accepté. Le claim `typ` est comparé, sinon un jeton de
# rafraîchissement servirait de jeton d'accès, ce qui transformerait une fenêtre de
# 15 minutes en fenêtre de 7 jours.
# Contrainte : ce module ne lit jamais `get_settings()`, qui est mis en cache par
# `lru_cache` et se contaminerait entre tests. Tout paramètre arrive par `TokenPolicy`.

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

import jwt

ACCESS_TOKEN_TYPE: Final = "access"  # noqa: S105
REFRESH_SECRET_BYTES: Final = 32

_ALGORITHME: Final = "HS256"
_CLAIMS_REQUIS: Final = ["iss", "aud", "sub", "iat", "exp", "jti", "typ", "role", "kind"]


class TokenInvalidError(Exception):
    pass


class TokenExpiredError(TokenInvalidError):
    pass


@dataclass(frozen=True, slots=True)
class TokenPolicy:
    secret: str
    issuer: str
    audience: str
    access_ttl: timedelta


@dataclass(frozen=True, slots=True)
class AccessClaims:
    subject: UUID
    role: str
    kind: str
    token_id: UUID
    issued_at: datetime


def encode_access_token(
    policy: TokenPolicy,
    *,
    subject: UUID,
    role: str,
    kind: str,
    now: datetime | None = None,
) -> str:
    emis_a = now or datetime.now(UTC)
    return jwt.encode(
        {
            "iss": policy.issuer,
            "aud": policy.audience,
            "sub": str(subject),
            "iat": emis_a,
            "exp": emis_a + policy.access_ttl,
            "jti": str(uuid4()),
            "typ": ACCESS_TOKEN_TYPE,
            "role": role,
            "kind": kind,
        },
        policy.secret,
        algorithm=_ALGORITHME,
    )


def decode_access_token(policy: TokenPolicy, token: str) -> AccessClaims:
    try:
        charge = jwt.decode(
            token,
            policy.secret,
            algorithms=[_ALGORITHME],
            audience=policy.audience,
            issuer=policy.issuer,
            options={"require": _CLAIMS_REQUIS},
        )
    except jwt.ExpiredSignatureError as erreur:
        raise TokenExpiredError("Jeton expiré") from erreur
    except jwt.InvalidTokenError as erreur:
        raise TokenInvalidError("Jeton invalide") from erreur

    if charge["typ"] != ACCESS_TOKEN_TYPE:
        raise TokenInvalidError("Type de jeton inattendu")

    try:
        sujet = UUID(charge["sub"])
        identifiant = UUID(charge["jti"])
    except (AttributeError, TypeError, ValueError) as erreur:
        raise TokenInvalidError("Identifiants du jeton illisibles") from erreur

    return AccessClaims(
        subject=sujet,
        role=str(charge["role"]),
        kind=str(charge["kind"]),
        token_id=identifiant,
        issued_at=datetime.fromtimestamp(charge["iat"], tz=UTC),
    )


def generate_refresh_secret() -> str:
    return secrets.token_urlsafe(REFRESH_SECRET_BYTES)


# SHA-256 nu, pas Argon2id : 256 bits de CSPRNG n'ont ni dictionnaire ni préimage atteignable,
# et une KDF lente coûterait 17 ms à chaque rafraîchissement pour aucun gain.
def fingerprint_refresh(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()
