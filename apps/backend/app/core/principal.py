# Pourquoi : tout le code métier dépend de `Principal` et jamais du modèle ORM ni des claims
# du jeton. C'est ce qui garde la bascule vers un fournisseur OIDC locale à
# `get_current_principal()` et à `AuthService.authenticate()`, au lieu de la répandre dans
# chaque endpoint.

from dataclasses import dataclass
from uuid import UUID

from app.core.roles import AccountKind, Role


@dataclass(frozen=True, slots=True)
class Principal:
    id: UUID
    email: str
    role: Role
    kind: AccountKind
    must_change_password: bool
