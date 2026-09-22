from datetime import UTC, datetime, timedelta

import pytest

from app.monitoring import drift as cli
from app.repositories.drift import NouveauRapportDerive
from app.services.drift import STATUT_DERIVE, STATUT_STABLE, Seuils

INSTANT = datetime(2026, 9, 22, 12, tzinfo=UTC)


def rapport(*, site_id: str | None, status: str, reason: str | None = None) -> NouveauRapportDerive:
    return NouveauRapportDerive(
        site_id=site_id,
        window_start=INSTANT - timedelta(hours=168),
        window_end=INSTANT,
        reference_start=None,
        reference_end=None,
        n_observations=48,
        mae=1.5,
        mape=12.0,
        bias=0.3,
        reference_mae=1.2,
        coverage_ratio=1.0,
        insufficient_data_ratio=0.0,
        model_references=["lightgbm-aaa"],
        status=status,
        reason=reason,
    )


def installe(monkeypatch: pytest.MonkeyPatch, rapports: list[NouveauRapportDerive]) -> None:
    async def fausse_execution(
        *, now: datetime | None, site_id: str | None, seuils: Seuils | None
    ) -> list[NouveauRapportDerive]:
        return rapports

    monkeypatch.setattr(cli, "run_drift", fausse_execution)


def test_parse_args_defaults_to_the_standard_window() -> None:
    arguments = cli.parse_args([])

    assert arguments.window_hours == 168
    assert arguments.grace_hours == 2
    assert arguments.fail_on_drift is False


def test_parse_args_reads_the_site_id() -> None:
    assert cli.parse_args(["--site-id", "SITE001"]).site_id == "SITE001"


def test_parse_args_parses_the_instant_option() -> None:
    arguments = cli.parse_args(["--now", "2026-09-22T12:00:00+00:00"])

    assert arguments.now == INSTANT


def test_parse_instant_treats_a_naive_datetime_as_utc() -> None:
    assert cli._parse_instant("2026-09-22T12:00:00") == INSTANT


def test_seuils_depuis_translates_the_hour_options_into_durations() -> None:
    seuils = cli.seuils_depuis(cli.parse_args(["--window-hours", "24", "--grace-hours", "1"]))

    assert seuils.fenetre == timedelta(hours=24)
    assert seuils.grace == timedelta(hours=1)


def test_main_prints_the_verdict_of_every_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installe(
        monkeypatch,
        [
            rapport(site_id="SITE001", status=STATUT_STABLE),
            rapport(site_id=None, status=STATUT_STABLE),
        ],
    )

    code = cli.main([])

    sortie = capsys.readouterr().out
    assert code == 0
    assert "SITE001" in sortie
    assert "TOUS SITES" in sortie


def test_main_exits_non_zero_when_drift_is_detected_and_the_flag_is_set(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installe(monkeypatch, [rapport(site_id=None, status=STATUT_DERIVE, reason="MAE doublée")])

    code = cli.main(["--fail-on-drift"])

    assert code == 1
    assert "MAE doublée" in capsys.readouterr().out


def test_main_exits_zero_when_drift_is_detected_without_the_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installe(monkeypatch, [rapport(site_id=None, status=STATUT_DERIVE, reason="MAE doublée")])

    code = cli.main([])

    assert code == 0
    assert capsys.readouterr().out != ""
