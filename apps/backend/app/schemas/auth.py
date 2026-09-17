# Contrainte : le mot de passe est borné à 128 caractères. Sans plafond, une chaîne de dix
# mégaoctets ferait travailler Argon2 gratuitement, à la charge du serveur.

import re
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.principal import Principal
from app.core.roles import AccountKind, Role

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

_MAJUSCULE = re.compile(r"[A-ZÀ-Ý]")
_MINUSCULE = re.compile(r"[a-zà-ÿ]")
_CHIFFRE = re.compile(r"\d")
_SPECIAL = re.compile(r"[^\w\s]")


def valide_complexite(mot_de_passe: str) -> str:
    manquants = [
        nom
        for nom, motif in (
            ("une majuscule", _MAJUSCULE),
            ("une minuscule", _MINUSCULE),
            ("un chiffre", _CHIFFRE),
            ("un caractère spécial", _SPECIAL),
        )
        if not motif.search(mot_de_passe)
    ]
    if manquants:
        raise ValueError(f"Le mot de passe doit contenir au moins {', '.join(manquants)}")
    return mot_de_passe


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("new_password")
    @classmethod
    def _new_password_est_complexe(cls, valeur: str) -> str:
        return valide_complexite(valeur)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("new_password")
    @classmethod
    def _new_password_est_complexe(cls, valeur: str) -> str:
        return valide_complexite(valeur)


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
