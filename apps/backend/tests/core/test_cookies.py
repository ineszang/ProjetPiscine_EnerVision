from app.core.cookies import RefreshCookie, cookie_name
from tests.factories import make_settings


def test_build_marks_the_cookie_http_only_and_scopes_it_to_the_auth_routes() -> None:
    settings = make_settings(env="local")

    cookie = RefreshCookie.build(settings, "un-secret-opaque")

    assert cookie.httponly is True
    assert cookie.samesite == "strict"
    assert cookie.path == "/api/v1/auth"
    assert cookie.max_age == settings.refresh_token_ttl_seconds


def test_build_prefixes_and_secures_the_cookie_outside_local() -> None:
    settings = make_settings(env="prod", cors_origins="https://enervision.fr")

    cookie = RefreshCookie.build(settings, "un-secret-opaque")

    assert cookie.secure is True
    assert cookie.key.startswith("__Secure-")


def test_build_leaves_the_cookie_unprefixed_in_local() -> None:
    settings = make_settings(env="local")

    cookie = RefreshCookie.build(settings, "un-secret-opaque")

    assert cookie.key == "ev_refresh"


def test_expired_reuses_the_exact_name_and_path_of_the_posted_cookie() -> None:
    settings = make_settings(env="prod", cors_origins="https://enervision.fr")

    pose = RefreshCookie.build(settings, "un-secret-opaque")
    suppression = RefreshCookie.expired(settings)

    assert suppression.key == pose.key
    assert suppression.path == pose.path
    assert suppression.secure == pose.secure
    assert suppression.samesite == pose.samesite
    assert suppression.max_age == 0
    assert suppression.value == ""


def test_as_kwargs_matches_the_starlette_set_cookie_signature() -> None:
    settings = make_settings(env="local")

    arguments = RefreshCookie.build(settings, "un-secret-opaque").as_kwargs()

    assert set(arguments) == {"key", "value", "max_age", "path", "secure", "httponly", "samesite"}


def test_cookie_name_follows_the_configured_name() -> None:
    settings = make_settings(env="local", refresh_cookie_name="autre_nom")

    assert cookie_name(settings) == "autre_nom"
