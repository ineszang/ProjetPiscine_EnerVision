# Contrainte : le mot de passe est borné à 128 caractères. Sans plafond, une chaîne de dix
# mégaoctets ferait travailler Argon2 gratuitement, à la charge du serveur.
# Contrainte : `SPECIAL_CHARACTERS` doit rester identique à `password.validator.ts` côté
# frontend. `\w`/`\d` divergent entre Python (Unicode) et JavaScript (ASCII) : une classe
# explicite, plutôt qu'une négation, évite qu'un mot de passe soit accepté d'un côté et
# rejeté de l'autre (ex. "Sécurité1", où "é" comptait comme "spécial" pour Python seul).

import re
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.principal import Principal
from app.core.roles import AccountKind, Role

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

SPECIAL_CHARACTERS = "!@#$%^&*()-_=+[]{};:,.?"

_MAJUSCULE = re.compile(r"[A-ZÀ-ÖØ-Þ]")
_MINUSCULE = re.compile(r"[a-zà-öø-þ]")
_CHIFFRE = re.compile(r"[0-9]")
_SPECIAL = re.compile(r"[" + re.escape(SPECIAL_CHARACTERS) + r"]")


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


class ResetTokenValidationResponse(BaseModel):
    valid: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
    principal: PrincipalResponse
