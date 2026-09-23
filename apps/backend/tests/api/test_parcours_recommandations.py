from collections.abc import Callable

import pytest
from httpx import AsyncClient

from app.core.roles import Role
from tests.api.conftest import JeuMetier

pytestmark = pytest.mark.integration


async def genere(client: AsyncClient, site_id: str) -> dict[str, int]:
    # Toujours borne a un site : sans `site_id`, le service examine toutes les alertes de la
    # base, y compris celles d'un autre test, et le rapport cesse d'etre deterministe.
    reponse = await client.post(f"/api/v1/recommendations/generate?site_id={site_id}")

    assert reponse.status_code == 200
    return dict(reponse.json())


async def test_generate_creates_a_recommendation_for_the_alert_of_the_requested_site(
    jeu_metier: JeuMetier, principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.ADMIN)

    rapport = await genere(client, jeu_metier.site_id)

    assert rapport["alerts_examined"] == 1
    assert rapport["recommendations_created"] >= 1
    assert rapport["already_present"] == 0


async def test_generate_creates_nothing_more_when_it_runs_twice_on_the_same_alerts(
    jeu_metier: JeuMetier, principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.ADMIN)
    premier = await genere(client, jeu_metier.site_id)

    second = await genere(client, jeu_metier.site_id)

    assert second["recommendations_created"] == 0
    assert second["already_present"] == premier["recommendations_created"]


async def test_generate_examines_no_alert_when_the_requested_site_has_none(
    jeu_metier: JeuMetier, principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.ADMIN)

    rapport = await genere(client, jeu_metier.site_voisin)

    assert rapport["alerts_examined"] == 0
    assert rapport["recommendations_created"] == 0


async def test_list_recommendations_returns_what_generate_persisted_in_another_session(
    jeu_metier: JeuMetier, principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.ADMIN)
    await genere(client, jeu_metier.site_id)

    reponse = await client.get("/api/v1/recommendations")

    assert reponse.status_code == 200
    miennes = [r for r in reponse.json() if r["alert_id"] == jeu_metier.alert_id]
    assert miennes != []
    assert all(r["rule_reference"] for r in miennes)


async def test_get_recommendation_returns_the_row_created_by_generate(
    jeu_metier: JeuMetier, principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.ADMIN)
    await genere(client, jeu_metier.site_id)
    liste = await client.get("/api/v1/recommendations")
    creee = next(r for r in liste.json() if r["alert_id"] == jeu_metier.alert_id)

    reponse = await client.get(f"/api/v1/recommendations/{creee['recommendation_id']}")

    assert reponse.status_code == 200
    assert reponse.json() == creee


async def test_get_recommendation_returns_404_when_the_identifier_is_unknown(
    principal_injecte: Callable[[Role], None], client: AsyncClient
) -> None:
    principal_injecte(Role.LECTEUR)

    reponse = await client.get("/api/v1/recommendations/9999999")

    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Recommandation introuvable"
