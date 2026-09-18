# Piège : `PasswordHasher.verify()` bloque 17 ms. Appelé tel quel dans un `async def`, il fige
# la boucle d'événements et gèle toutes les requêtes en cours, pas seulement la connexion.
# `Argon2Hasher` le pousse donc dans un fil, sous un `CapacityLimiter` : le pool par défaut
# d'anyio accepte 40 fils, soit 40 x 19 Mio dans le pire cas sur une machine qui héberge aussi
# PostgreSQL, Prometheus et Grafana.
# Piège : `verify_dummy()` doit être appelé quand l'utilisateur est introuvable. Sans lui,
# l'écart entre 2 ms et 17 ms est un oracle d'existence de compte, mesurable à distance.

import secrets

import anyio
import anyio.to_thread
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError, VerificationError

_ERREURS_DE_VERIFICATION = (VerificationError, InvalidHashError, Argon2Error)


class Argon2Hasher:
    def __init__(self, hasher: PasswordHasher, *, max_concurrency: int) -> None:
        self._hasher = hasher
        self._limiter = anyio.CapacityLimiter(max_concurrency)
        self._leurre = hasher.hash(secrets.token_urlsafe(32))

    async def hash(self, password: str) -> str:
        return await anyio.to_thread.run_sync(self._hasher.hash, password, limiter=self._limiter)

    async def verify(self, stored: str, password: str) -> bool:
        return await anyio.to_thread.run_sync(self._verify, stored, password, limiter=self._limiter)

    async def verify_dummy(self) -> None:
        await self.verify(self._leurre, "")

    def needs_rehash(self, stored: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(stored)
        except _ERREURS_DE_VERIFICATION:
            return True

    def _verify(self, stored: str, password: str) -> bool:
        try:
            return self._hasher.verify(stored, password)
        except _ERREURS_DE_VERIFICATION:
            return False


def build_hasher(
    *,
    time_cost: int,
    memory_cost_kib: int,
    parallelism: int,
    max_concurrency: int,
) -> Argon2Hasher:
    return Argon2Hasher(
        PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost_kib,
            parallelism=parallelism,
            hash_len=32,
            salt_len=16,
        ),
        max_concurrency=max_concurrency,
    )
