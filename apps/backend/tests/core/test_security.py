import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.security import (
    AccessClaims,
    TokenExpiredError,
    TokenInvalidError,
    TokenPolicy,
    decode_access_token,
    encode_access_token,
    fingerprint_refresh,
    generate_refresh_secret,
)

POLITIQUE = TokenPolicy(
    secret="un-secret-de-test-de-plus-de-trente-deux-caracteres",
    issuer="enervision-api",
    audience="enervision-web",
    access_ttl=timedelta(minutes=15),
)


def emets(**surcharges: object) -> str:
    charge = {
        "iss": POLITIQUE.issuer,
        "aud": POLITIQUE.audience,
        "sub": str(uuid4()),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
        "jti": str(uuid4()),
        "typ": "access",
        "role": "lecteur",
        "kind": "human",
    }
    charge.update(surcharges)
    return jwt.encode(charge, POLITIQUE.secret, algorithm="HS256")


def test_decode_access_token_returns_the_claims_when_the_token_is_valid() -> None:
    sujet = uuid4()

    jeton = encode_access_token(POLITIQUE, subject=sujet, role="operateur", kind="human")
    claims = decode_access_token(POLITIQUE, jeton)

    assert isinstance(claims, AccessClaims)
    assert claims.subject == sujet
    assert claims.role == "operateur"
    assert claims.kind == "human"


def test_decode_access_token_raises_expired_when_the_lifetime_has_passed() -> None:
    passe = datetime.now(UTC) - timedelta(hours=2)

    jeton = encode_access_token(POLITIQUE, subject=uuid4(), role="lecteur", kind="human", now=passe)

    with pytest.raises(TokenExpiredError):
        decode_access_token(POLITIQUE, jeton)


def test_decode_access_token_raises_invalid_when_the_signature_was_forged() -> None:
    autre = TokenPolicy(
        secret="un-autre-secret-tout-aussi-long-que-le-premier",
        issuer=POLITIQUE.issuer,
        audience=POLITIQUE.audience,
        access_ttl=POLITIQUE.access_ttl,
    )

    jeton = encode_access_token(autre, subject=uuid4(), role="lecteur", kind="human")

    with pytest.raises(TokenInvalidError):
        decode_access_token(POLITIQUE, jeton)


@pytest.mark.parametrize(
    "surcharges",
    [
        {"aud": "un-autre-public"},
        {"iss": "un-autre-emetteur"},
        {"typ": "refresh"},
    ],
    ids=["audience_invalide", "emetteur_invalide", "jeton_de_rafraichissement"],
)
def test_decode_access_token_raises_invalid_when_a_claim_is_wrong(
    surcharges: dict[str, object],
) -> None:
    jeton = emets(**surcharges)

    with pytest.raises(TokenInvalidError):
        decode_access_token(POLITIQUE, jeton)


@pytest.mark.parametrize(
    "claim",
    ["jti", "typ", "role", "kind"],
    ids=["identifiant", "type", "role", "nature_du_compte"],
)
def test_decode_access_token_raises_invalid_when_a_required_claim_is_missing(claim: str) -> None:
    charge = {
        "iss": POLITIQUE.issuer,
        "aud": POLITIQUE.audience,
        "sub": str(uuid4()),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
        "jti": str(uuid4()),
        "typ": "access",
        "role": "lecteur",
        "kind": "human",
    }
    del charge[claim]

    jeton = jwt.encode(charge, POLITIQUE.secret, algorithm="HS256")

    with pytest.raises(TokenInvalidError):
        decode_access_token(POLITIQUE, jeton)


def test_decode_access_token_rejects_a_token_forged_with_the_none_algorithm() -> None:
    def encode(donnees: dict[str, object]) -> str:
        brut = json.dumps(donnees, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(brut).rstrip(b"=").decode()

    entete = encode({"alg": "none", "typ": "JWT"})
    charge = encode(
        {
            "iss": POLITIQUE.issuer,
            "aud": POLITIQUE.audience,
            "sub": str(uuid4()),
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
            "jti": str(uuid4()),
            "typ": "access",
            "role": "admin",
            "kind": "human",
        }
    )

    with pytest.raises(TokenInvalidError):
        decode_access_token(POLITIQUE, f"{entete}.{charge}.")


def test_decode_access_token_rejects_a_token_signed_with_another_algorithm() -> None:
    charge = {
        "iss": POLITIQUE.issuer,
        "aud": POLITIQUE.audience,
        "sub": str(uuid4()),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
        "jti": str(uuid4()),
        "typ": "access",
        "role": "admin",
        "kind": "human",
    }

    jeton = jwt.encode(charge, POLITIQUE.secret * 2, algorithm="HS512")

    with pytest.raises(TokenInvalidError):
        decode_access_token(POLITIQUE, jeton)


@pytest.mark.parametrize(
    "surcharges",
    [{"sub": "pas-un-uuid"}, {"jti": "pas-un-uuid"}],
    ids=["sujet_illisible", "identifiant_illisible"],
)
def test_decode_access_token_raises_invalid_when_an_identifier_is_not_a_uuid(
    surcharges: dict[str, object],
) -> None:
    jeton = emets(**surcharges)

    with pytest.raises(TokenInvalidError):
        decode_access_token(POLITIQUE, jeton)


def test_generate_refresh_secret_returns_distinct_url_safe_values() -> None:
    secrets_generes = {generate_refresh_secret() for _ in range(100)}

    assert len(secrets_generes) == 100
    assert all(len(valeur) >= 43 for valeur in secrets_generes)


def test_fingerprint_refresh_is_stable_and_distinguishes_two_secrets() -> None:
    premier = generate_refresh_secret()
    second = generate_refresh_secret()

    empreinte = fingerprint_refresh(premier)

    assert len(empreinte) == 32
    assert empreinte == fingerprint_refresh(premier)
    assert empreinte != fingerprint_refresh(second)
