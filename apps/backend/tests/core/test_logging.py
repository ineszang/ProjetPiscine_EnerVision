import logging

import pytest

from app.core.logging import CAVIARDAGE, RedactingFilter, redact


@pytest.mark.parametrize(
    "message",
    [
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.charge-utile-assez-longue.signature",
        "jeton brut eyJhbGciOiJIUzI1NiJ9abcdefghijklmnopqrstuvwxyz",
        "INSERT ... ('$argon2id$v=19$m=19456,t=2,p=1$sel-en-clair$empreinte-en-clair')",
        '{"password": "le-mot-de-passe-du-client"}',
        "current_password=le-mot-de-passe",
        "Cookie: ev_refresh=abcdefghijklmnopqrstuvwxyz0123456789",
    ],
    ids=[
        "en_tete_bearer",
        "jeton_jwt_nu",
        "empreinte_argon2",
        "mot_de_passe_json",
        "mot_de_passe_en_paire",
        "cookie_de_rafraichissement",
    ],
)
def test_redact_removes_every_known_secret_shape(message: str) -> None:
    expurge = redact(message)

    assert CAVIARDAGE in expurge
    for suspect in ("le-mot-de-passe", "empreinte-en-clair", "abcdefghijklmnopqrstuvwxyz"):
        assert suspect not in expurge


def test_redact_leaves_an_innocent_message_untouched() -> None:
    message = "auth.login.success user_id=3f2a ip=203.0.113.10"

    assert redact(message) == message


def test_the_filter_rewrites_the_record_before_it_reaches_the_handler() -> None:
    enregistrement = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='requete {"password": "%s"}',
        args=("secret-du-client",),
        exc_info=None,
    )

    conserve = RedactingFilter().filter(enregistrement)

    assert conserve is True
    assert "secret-du-client" not in enregistrement.getMessage()


def test_the_filter_keeps_a_record_that_holds_no_secret() -> None:
    enregistrement = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="requete %s",
        args=("/api/v1/health/live",),
        exc_info=None,
    )

    conserve = RedactingFilter().filter(enregistrement)

    assert conserve is True
    assert enregistrement.getMessage() == "requete /api/v1/health/live"
