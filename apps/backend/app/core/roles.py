from enum import StrEnum
from typing import Final


class Role(StrEnum):
    # Contrainte : ces valeurs voyagent en base, en JSON et dans les jetons. Elles restent
    # en ASCII, contrairement au libellé « opérateur » affiché à l'utilisateur.
    LECTEUR = "lecteur"
    OPERATEUR = "operateur"
    ADMIN = "admin"


class AccountKind(StrEnum):
    HUMAIN = "human"
    SERVICE = "service"


ROLE_RANK: Final[dict[Role, int]] = {
    Role.LECTEUR: 0,
    Role.OPERATEUR: 1,
    Role.ADMIN: 2,
}


def has_at_least(actual: Role, required: Role) -> bool:
    return ROLE_RANK[actual] >= ROLE_RANK[required]
