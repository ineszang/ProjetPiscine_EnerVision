# Piège : le cookie de suppression doit reprendre exactement le nom et le `Path` du cookie
# posé, sinon le navigateur en garde une copie et la déconnexion n'est que cosmétique.
# `RefreshCookie.expired()` existe pour que les deux ne puissent pas diverger.

from dataclasses import asdict, dataclass
from typing import Any, Self

from app.core.config import SameSite, Settings

SECURE_PREFIX = "__Secure-"


@dataclass(frozen=True, slots=True)
class RefreshCookie:
    key: str
    value: str
    max_age: int
    path: str
    secure: bool
    httponly: bool
    samesite: SameSite

    @classmethod
    def build(cls, settings: Settings, value: str) -> Self:
        return cls(
            key=cookie_name(settings),
            value=value,
            max_age=settings.refresh_token_ttl_seconds,
            path=settings.cookie_path,
            secure=settings.cookies_are_secure,
            httponly=True,
            samesite=settings.cookie_samesite,
        )

    @classmethod
    def expired(cls, settings: Settings) -> Self:
        return cls(
            key=cookie_name(settings),
            value="",
            max_age=0,
            path=settings.cookie_path,
            secure=settings.cookies_are_secure,
            httponly=True,
            samesite=settings.cookie_samesite,
        )

    def as_kwargs(self) -> dict[str, Any]:
        return asdict(self)


def cookie_name(settings: Settings) -> str:
    if settings.cookies_are_secure:
        return f"{SECURE_PREFIX}{settings.refresh_cookie_name}"
    return settings.refresh_cookie_name
