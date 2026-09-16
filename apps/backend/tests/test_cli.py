import json
from pathlib import Path

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


def test_build_parser_reads_the_export_openapi_arguments() -> None:
    arguments = cli.build_parser().parse_args(
        ["export-openapi", "--output", "ailleurs/contrat.json"]
    )

    assert arguments.commande == "export-openapi"
    assert arguments.output == "ailleurs/contrat.json"


def test_build_parser_defaults_the_export_to_the_versioned_contract() -> None:
    arguments = cli.build_parser().parse_args(["export-openapi"])

    assert arguments.output == str(cli.CHEMIN_CONTRAT)


def test_settings_of_the_contract_ignore_the_local_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_API_PREFIX", "/api/v9")
    monkeypatch.setenv("APP_NAME", "API du poste de Johan")

    settings = cli.settings_du_contrat()

    assert settings.api_prefix == "/api/v1"
    assert settings.name == "EnerVision API"


def test_export_openapi_writes_a_readable_schema_where_asked(tmp_path: Path) -> None:
    destination = tmp_path / "contrat.json"

    cli.export_openapi(destination)

    assert json.loads(destination.read_text(encoding="utf-8"))["openapi"].startswith("3.")


# Piège : `main()` réclamait un mot de passe avant de lire la commande. Sans le branchement,
# l'export resterait bloqué sur `getpass` et aucune CI ne pourrait le rejouer.
def test_main_exports_the_contract_without_asking_for_a_password(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    destination = tmp_path / "contrat.json"

    code = cli.main(["export-openapi", "--output", str(destination)])

    assert code == 0
    assert destination.exists()
    assert str(destination) in capsys.readouterr().out
