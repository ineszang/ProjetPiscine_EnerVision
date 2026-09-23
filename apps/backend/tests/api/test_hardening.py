import pytest
from httpx import ASGITransport, AsyncClient
from httpx import Response as HttpResponse

from app.main import create_app
from tests.factories import make_settings

ORIGINE = "https://enervision.fr"


async def interroge(
    settings_overrides: dict[str, object], chemin: str, **kwargs: object
) -> HttpResponse:
    application = create_app(make_settings(**settings_overrides))
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(chemin, **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("entete", "valeur"),
    [
        ("x-content-type-options", "nosniff"),
        ("x-frame-options", "DENY"),
        ("referrer-policy", "no-referrer"),
        ("cross-origin-resource-policy", "same-origin"),
    ],
    ids=["nosniff", "anti_iframe", "referrer", "corp"],
)
async def test_every_response_carries_the_security_headers(
    client: AsyncClient, entete: str, valeur: str
) -> None:
    response = await client.get("/api/v1/health/live")

    assert response.headers[entete] == valeur


async def test_the_application_never_sets_hsts_itself(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live")

    assert "strict-transport-security" not in response.headers


@pytest.mark.parametrize(
    "env",
    ["staging", "prod"],
    ids=["preproduction", "production"],
)
async def test_the_documentation_disappears_outside_development(env: str) -> None:
    surcharges = {"env": env, "cors_origins": ORIGINE}

    for chemin in ("/docs", "/openapi.json"):
        assert (await interroge(surcharges, chemin)).status_code == 404


@pytest.mark.parametrize("env", ["local", "dev"], ids=["local", "developpement"])
async def test_the_documentation_stays_available_while_developing(env: str) -> None:
    surcharges = {"env": env, "cors_origins": ORIGINE}

    assert (await interroge(surcharges, "/openapi.json")).status_code == 200


async def test_an_explicit_override_can_reopen_the_documentation() -> None:
    surcharges = {"env": "prod", "cors_origins": ORIGINE, "expose_api_docs": True}

    assert (await interroge(surcharges, "/openapi.json")).status_code == 200


async def test_metrics_stay_open_when_no_token_is_configured(client: AsyncClient) -> None:
    response = await client.get("/metrics")

    assert response.status_code == 200


async def test_an_empty_metrics_token_means_no_token() -> None:
    assert (await interroge({"metrics_token": ""}, "/metrics")).status_code == 200


async def test_metrics_ignore_health_probes_but_count_business_routes(client: AsyncClient) -> None:
    await client.get("/api/v1/health/live")
    await client.get("/api/v1/sites")

    exposition = (await client.get("/metrics")).text

    assert 'handler="/api/v1/health/live"' not in exposition
    assert 'handler="/api/v1/sites"' in exposition


async def test_metrics_demand_the_token_once_one_is_configured() -> None:
    surcharges = {"metrics_token": "un-jeton-de-supervision-assez-long"}

    assert (await interroge(surcharges, "/metrics")).status_code == 401


async def test_metrics_answer_to_the_right_token() -> None:
    surcharges = {"metrics_token": "un-jeton-de-supervision-assez-long"}
    entetes = {"Authorization": "Bearer un-jeton-de-supervision-assez-long"}

    response = await interroge(surcharges, "/metrics", headers=entetes)

    assert response.status_code == 200


async def test_metrics_refuse_a_token_that_is_almost_right() -> None:
    surcharges = {"metrics_token": "un-jeton-de-supervision-assez-long"}
    entetes = {"Authorization": "Bearer un-jeton-de-supervision-assez-lon"}

    response = await interroge(surcharges, "/metrics", headers=entetes)

    assert response.status_code == 401


async def test_an_unhandled_error_returns_a_correlation_id_and_no_traceback() -> None:
    application = create_app(make_settings())

    @application.get("/api/v1/essai-panne")
    async def _casse() -> None:
        raise RuntimeError("secret interne de la pile")

    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/essai-panne")

    assert response.status_code == 500
    assert "secret interne de la pile" not in response.text
    assert response.json()["correlation"]
