import pytest

from app import cli


def test_build_parser_reads_the_create_admin_arguments() -> None:
    arguments = cli.build_parser().parse_args(
        ["create-admin", "--email", "admin@enervision.fr", "--generate", "--force"]
    )

    assert arguments.commande == "create-admin"
    assert arguments.email == "admin@enervision.fr"
    assert arguments.generate is True
    assert arguments.force is True


def test_build_parser_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


def test_build_parser_requires_an_email() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["create-admin"])


def test_read_password_generates_a_long_secret_when_asked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    mot_de_passe = cli.read_password(generate=True)

    assert len(mot_de_passe) >= cli.LONGUEUR_MOT_DE_PASSE_GENERE
    assert mot_de_passe in capsys.readouterr().out


def test_read_password_accepts_two_matching_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    saisies = iter(["un-mot-de-passe-valide", "un-mot-de-passe-valide"])
    monkeypatch.setattr(cli, "getpass", lambda _: next(saisies))

    assert cli.read_password(generate=False) == "un-mot-de-passe-valide"


def test_read_password_refuses_a_password_below_the_minimum_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "getpass", lambda _: "court")

    with pytest.raises(SystemExit):
        cli.read_password(generate=False)


def test_read_password_refuses_two_different_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    saisies = iter(["un-mot-de-passe-valide", "un-autre-mot-de-passe"])
    monkeypatch.setattr(cli, "getpass", lambda _: next(saisies))

    with pytest.raises(SystemExit):
        cli.read_password(generate=False)
