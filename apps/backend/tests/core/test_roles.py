import pytest

from app.core.roles import Role, has_at_least


@pytest.mark.parametrize(
    ("actual", "required", "expected"),
    [
        (Role.LECTEUR, Role.LECTEUR, True),
        (Role.LECTEUR, Role.OPERATEUR, False),
        (Role.LECTEUR, Role.ADMIN, False),
        (Role.OPERATEUR, Role.LECTEUR, True),
        (Role.OPERATEUR, Role.OPERATEUR, True),
        (Role.OPERATEUR, Role.ADMIN, False),
        (Role.ADMIN, Role.LECTEUR, True),
        (Role.ADMIN, Role.OPERATEUR, True),
        (Role.ADMIN, Role.ADMIN, True),
    ],
    ids=[
        "lecteur_sur_lecteur",
        "lecteur_sur_operateur",
        "lecteur_sur_admin",
        "operateur_sur_lecteur",
        "operateur_sur_operateur",
        "operateur_sur_admin",
        "admin_sur_lecteur",
        "admin_sur_operateur",
        "admin_sur_admin",
    ],
)
def test_has_at_least_orders_the_three_roles(actual: Role, required: Role, expected: bool) -> None:
    accorde = has_at_least(actual, required)

    assert accorde is expected


def test_role_values_stay_ascii_for_the_wire_format() -> None:
    valeurs = [role.value for role in Role]

    assert all(valeur.isascii() for valeur in valeurs)
