import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.main import create_app


@pytest.fixture(autouse=True, scope="session")
def environment() -> Iterator[None]:
    os.environ.setdefault("APP_SECRET_KEY", "secret-de-test")
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://enervision:change_me@localhost:5433/enervision_test"
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# Piege : get_engine est lru_cache et pytest-asyncio ouvre une boucle par test. Sans ce
# recyclage, le 2e test touchant vraiment la base heriterait d une boucle morte.
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
