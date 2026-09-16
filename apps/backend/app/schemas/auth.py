# Contrainte : le mot de passe est borné à 128 caractères. Sans plafond, une chaîne de dix
# mégaoctets ferait travailler Argon2 gratuitement, à la charge du serveur.

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.principal import Principal
from app.core.roles import AccountKind, Role

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class PrincipalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: Role
    kind: AccountKind
    must_change_password: bool

    @classmethod
    def from_principal(cls, principal: Principal) -> Self:
        return cls.model_validate(principal)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
    principal: PrincipalResponse
