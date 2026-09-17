import pytest
from pydantic import ValidationError

from app.schemas.auth import PasswordChangeRequest, valide_complexite

MOT_DE_PASSE_VALIDE = "Un-mot-de-passe1!"


def test_password_change_request_accepts_a_password_covering_the_four_classes() -> None:
    requete = PasswordChangeRequest(
        current_password="peu-importe", new_password=MOT_DE_PASSE_VALIDE
    )

    assert requete.new_password == MOT_DE_PASSE_VALIDE


@pytest.mark.parametrize(
    "new_password",
    [
        "un-mot-de-passe1!",
        "UN-MOT-DE-PASSE1!",
        "Un-mot-de-passe!",
        "Un mot de passe 1",
    ],
    ids=["sans_majuscule", "sans_minuscule", "sans_chiffre", "sans_caractere_special"],
)
def test_password_change_request_rejects_a_password_missing_a_character_class(
    new_password: str,
) -> None:
    with pytest.raises(ValidationError):
        PasswordChangeRequest(current_password="peu-importe", new_password=new_password)


def test_password_change_request_rejects_a_password_below_the_minimum_length() -> None:
    with pytest.raises(ValidationError):
        PasswordChangeRequest(current_password="peu-importe", new_password="Ab1!")


def test_valide_complexite_names_every_missing_class_in_the_error() -> None:
    with pytest.raises(ValueError, match=r"majuscule.*chiffre|chiffre.*majuscule"):
        valide_complexite("minuscules-seulement")
