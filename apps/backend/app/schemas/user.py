# Contrainte : les schémas de lecture et d'écriture sont séparés. Un modèle unique laisserait
# passer `role` ou `is_active` depuis un corps de requête, et renverrait `password_hash` en
# réponse. C'est l'attribution de masse, API3 du top 10 API.

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.roles import AccountKind, Role


class UserCreateRequest(BaseModel):
    email: EmailStr
    role: Role
    full_name: str | None = Field(default=None, max_length=200)


class UserUpdateRequest(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: Role
    kind: AccountKind
    is_active: bool
    must_change_password: bool
    full_name: str | None
    last_login_at: datetime | None
    created_at: datetime


class TemporaryPasswordResponse(BaseModel):
    # Affiché une seule fois : l'empreinte seule est conservée côté serveur.
    user: UserResponse
    temporary_password: str
