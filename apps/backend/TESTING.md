# Conventions de tests unitaires : Backend

## Outil

pytest, avec pytest-asyncio en mode `auto` : un `async def test_*` est collecte sans
decorateur. Les appels HTTP passent par httpx sur `ASGITransport`, qui parle a
l'application en memoire, sans serveur ni port ouvert.

## Ou ecrire les tests

`tests/` est le miroir de `app/` : un test de `app/services/consumption.py` va dans
`tests/services/test_consumption.py`. Les paquets `core`, `db`, `services` et
`repositories` existent deja, vides, pour cette raison.

## Nommage

- Fonctions en anglais : `test_<sujet>_<comportement>_when_<condition>`.
- `ids=` de `parametrize` en francais : `ids=["erreur_sqlalchemy", "erreur_reseau"]`.
- Pas de docstring : le nom porte l'intention.

## Structure attendue (Arrange / Act / Assert)

Une ligne vide separe les trois temps, sans commentaire pour les annoncer.

```python
async def test_readiness_returns_503_when_the_extension_is_missing(
    fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=None)

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Extension TimescaleDB absente"
```

## Ce qui doit etre teste en priorite

Le sens de dependance du backend est `endpoints -> services -> repositories -> models`.

| Couche | Ce qu'on teste |
|---|---|
| `services/` | La logique metier, cas nominal et cas d'erreur. C'est la priorite. |
| `repositories/` | Chaque branche de decision, sous le marqueur `integration`. |
| `endpoints/` | Le code de statut et la forme de la reponse, pas la logique metier. |
| `schemas/` | Rien, sauf si le schema porte une validation ecrite a la main. |

## Doubles

On remplace une dependance FastAPI par `app.dependency_overrides`, jamais par
`unittest.mock`. `tests/factories.py` fournit le necessaire.

- `fake_session(result=...)` : la session repond `result`.
- `fake_session(failure=...)` : la session leve l'exception.
- `make_settings(**overrides)` : fabrique une `Settings`, dont les valeurs priment sur
  l'environnement et sur `.env`. C'est le moyen de tester `create_app` en `prod`.

## Gabarit : un endpoint

```python
from collections.abc import Callable

from httpx import AsyncClient


async def test_endpoint_returns_the_expected_payload(
    fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=42)

    response = await client.get("/api/v1/...")

    assert response.status_code == 200
    assert response.json() == {"valeur": 42}
```

## Gabarit : un service avec repository factice

Un service ne connait que son repository : on lui en passe un faux, sans base ni session.

```python
from app.services.consumption import ConsumptionService


class FakeRepository:
    async def total_for(self, site_id: int) -> float:
        return 12.5


async def test_service_converts_the_total_to_kilowatt_hours() -> None:
    service = ConsumptionService(FakeRepository())

    total = await service.total_kwh(site_id=1)

    assert total == 12.5
```

## Gabarit : un repository sur la vraie base

Un repository parle du SQL : le tester sur un double ne prouve rien. Il porte donc le
marqueur `integration`, ecarte par defaut.

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
async def test_repository_reads_back_what_it_wrote(session: AsyncSession) -> None:
    ...
```

## Marqueurs

`integration` designe tout test exigeant une base joignable. `pytest` les ecarte par
defaut, ce qui garde `make check` jouable sans Docker. Tout autre marqueur doit etre
declare dans `pyproject.toml` : `--strict-markers` refuse les marqueurs inconnus.

## Couverture

Les branches sont mesurees, pas seulement les lignes. Le seuil de 85 % ne s'applique
qu'aux cibles qui jouent toute la suite, `make test` et `make test-cov` : un fichier
joue seul affiche sa couverture sans jamais echouer dessus. Le detail se lit dans
`htmlcov/index.html` apres `make test-cov`.

## Lancer les tests

```bash
make test                          # suite unitaire, sans base
make test-cov                      # idem, plus les rapports HTML, XML et JUnit
make db-up && make test-integration # tests exigeant une base, demande Docker
make check                         # lint + typage + suite unitaire

uv run pytest tests/api/test_health.py           # un seul fichier
uv run pytest -k readiness                       # par motif de nom
```
