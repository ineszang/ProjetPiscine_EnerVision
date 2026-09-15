from typing import Any

from app.core.config import Settings

SETTINGS_DE_TEST: dict[str, Any] = {
    "env": "local",
    "debug": False,
    "log_level": "WARNING",
    "cors_origins": "",
    "secret_key": "secret-de-test-assez-long-pour-le-validateur",
    "database_url": "postgresql+asyncpg://enervision:change_me@localhost:5433/enervision_test",
}


class FakeSession:
    """Session factice : renvoie `result`, ou leve `failure` si elle est fournie."""

    def __init__(self, result: object = None, failure: Exception | None = None) -> None:
        self._result = result
        self._failure = failure

    async def scalar(self, *_: object, **__: object) -> object:
        return self._repondre()

    async def execute(self, *_: object, **__: object) -> object:
        return self._repondre()

    def _repondre(self) -> object:
        if self._failure is not None:
            raise self._failure
        return self._result


# Piège : les arguments nommés priment sur l'environnement et sur .env, contrairement
# aux variables posées par la fixture `environment`, qui restent surchargeables.
def make_settings(**overrides: Any) -> Settings:
    return Settings(**{**SETTINGS_DE_TEST, **overrides})
