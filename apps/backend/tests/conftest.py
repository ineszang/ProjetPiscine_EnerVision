import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True, scope="session")
def environment() -> Iterator[None]:
    os.environ.setdefault("APP_SECRET_KEY", "secret-de-test")
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://enervision:enervision@localhost:5432/enervision_test"
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
