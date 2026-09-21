import pytest
from pydantic import ValidationError

from tests.factories import make_settings

SECRET_VALIDE = "un-secret-de-test-de-plus-de-trente-deux-caracteres"


@pytest.mark.parametrize(
    "surcharges",
    [
        {"secret_key": "trop-court"},
        {"secret_key": "change_me"},
        {"env": "prod", "debug": True, "cors_origins": "https://enervision.fr"},
        {"cors_origins": "*"},
        {"env": "prod", "cors_origins": ""},
        {"cookie_samesite": "none", "cookie_secure": False},
    ],
    ids=[
        "secret_trop_court",
        "secret_sentinelle",
        "debug_en_production",
        "joker_dans_les_origines",
        "origines_vides_hors_local",
        "samesite_none_sans_secure",
    ],
)
def test_settings_refuses_to_build_when_the_configuration_is_unsafe(
    surcharges: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        make_settings(**surcharges)


def test_settings_accepts_debug_in_local_environment() -> None:
    settings = make_settings(env="local", debug=True)

    assert settings.debug is True


@pytest.mark.parametrize(
    ("env", "attendu"),
    [("local", False), ("dev", True), ("staging", True), ("prod", True)],
    ids=["local", "dev", "staging", "production"],
)
def test_cookies_are_secure_follows_the_environment(env: str, attendu: bool) -> None:
    settings = make_settings(env=env, cors_origins="https://enervision.fr")

    assert settings.cookies_are_secure is attendu


def test_cookies_are_secure_honours_an_explicit_override() -> None:
    settings = make_settings(env="prod", cors_origins="https://enervision.fr", cookie_secure=False)

    assert settings.cookies_are_secure is False


@pytest.mark.parametrize(
    ("env", "attendu"),
    [("local", True), ("dev", True), ("staging", False), ("prod", False)],
    ids=["local", "dev", "staging", "production"],
)
def test_api_docs_are_exposed_closes_staging_and_production(env: str, attendu: bool) -> None:
    settings = make_settings(env=env, cors_origins="https://enervision.fr")

    assert settings.api_docs_are_exposed is attendu


def test_api_docs_are_exposed_honours_an_explicit_override() -> None:
    settings = make_settings(env="prod", cors_origins="https://enervision.fr", expose_api_docs=True)

    assert settings.api_docs_are_exposed is True


def test_allowed_origins_splits_and_trims_the_list() -> None:
    settings = make_settings(cors_origins=" http://localhost:4200 , https://enervision.fr ")

    assert settings.allowed_origins == ["http://localhost:4200", "https://enervision.fr"]
