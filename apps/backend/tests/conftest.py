import os
from collections.abc import AsyncIterator, Callable, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_engine, get_session, get_session_factory
from app.main import create_app
from tests.factories import FakeSession


# Piège : les variables d'environnement priment sur apps/backend/.env. Celles qu'on ne
# pose pas ici, c'est le .env du poste qui les décide, et les assertions avec.
@pytest.fixture(autouse=True, scope="session")
def environment() -> Iterator[None]:
    os.environ.update(
        {
            "APP_ENV": "local",
            "APP_DEBUG": "false",
            "APP_LOG_LEVEL": "WARNING",
            "APP_CORS_ORIGINS": "",
            "APP_SECRET_KEY": "secret-de-test-assez-long-pour-le-validateur",
        }
    )
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://enervision:change_me@localhost:5433/enervision_test"
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# Piège : get_engine est lru_cache et pytest-asyncio ouvre une boucle par test. Sans ce
# recyclage, le 2e test touchant vraiment la base hériterait d'une boucle morte.
@pytest.fixture(autouse=True)
async def engine_per_test() -> AsyncIterator[None]:
    yield
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
def fake_session(app: FastAPI) -> Callable[..., None]:
    def install(result: object = None, failure: Exception | None = None) -> None:
        async def override() -> AsyncIterator[FakeSession]:
            yield FakeSession(result=result, failure=failure)

        app.dependency_overrides[get_session] = override

    return install


# Contrainte : ouvre une vraie connexion, donc réservée aux tests `integration`.
@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as async_session:
        yield async_session
