"""Tests d'integrite des DAGs : s'importent sans erreur, structure attendue. Pas d'execution
reelle des taches (ca reclamerait le conteneur avec `uv`/`enervision_ml`), juste la definition."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from airflow.dag_processing.dagbag import DagBag
from airflow.sdk import BaseOperator
from airflow.timetables.trigger import CronTriggerTimetable

DAGS_FOLDER = Path(__file__).resolve().parent.parent / "dags"

DAG_IDS = [
    "ml_train",
    "ml_score",
    "alertes",
    "historical_import",
    "mock_api_import",
    "derive",
]
TACHES = [
    ("ml_train", "train"),
    ("ml_score", "score"),
    ("alertes", "detection"),
    ("alertes", "recommandations"),
    ("historical_import", "import_historical"),
    ("mock_api_import", "import_mock_api"),
    ("derive", "derive"),
]


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAGS_FOLDER))


def test_dags_folder_has_no_import_error(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}


def test_every_expected_dag_is_discovered(dagbag: DagBag) -> None:
    assert set(dagbag.dag_ids) == set(DAG_IDS)


def test_ml_train_has_no_schedule(dagbag: DagBag) -> None:
    assert dagbag.dags["ml_train"].schedule is None


def test_ml_score_runs_every_hour(dagbag: DagBag) -> None:
    # `@hourly` est un alias Airflow pour ce cron, c'est sous cette forme que la timetable le rend.
    assert dagbag.dags["ml_score"].timetable.expression == "0 * * * *"


def test_alertes_runs_after_the_hourly_scoring(dagbag: DagBag) -> None:
    # Le decalage n'est pas cosmetique : la regle `anomaly` compare une lecture a la `prediction`
    # du meme instant, que `ml_score` ecrit a l'heure pile.
    assert dagbag.dags["alertes"].timetable.expression == "15 * * * *"


def test_historical_import_has_no_schedule(dagbag: DagBag) -> None:
    assert dagbag.dags["historical_import"].schedule is None


def test_mock_api_import_uses_an_explicit_hourly_interval(dagbag: DagBag) -> None:
    timetable = dagbag.dags["mock_api_import"].timetable

    assert isinstance(timetable, CronTriggerTimetable)
    assert timetable.serialize()["expression"] == "45 * * * *"

    manual_interval = timetable.infer_manual_data_interval(
        run_after=datetime.fromisoformat("2026-09-22T12:30:00+00:00"),
    )

    assert manual_interval.end - manual_interval.start == timedelta(hours=1)


def test_ml_train_task_calls_the_training_module(dagbag: DagBag) -> None:
    tache = dagbag.dags["ml_train"].get_task("train")
    assert "enervision_ml.train" in tache.bash_command


def test_ml_score_task_calls_the_scoring_module(dagbag: DagBag) -> None:
    tache = dagbag.dags["ml_score"].get_task("score")
    assert "enervision_ml.score" in tache.bash_command


def test_alertes_detection_task_calls_the_backend_detection(dagbag: DagBag) -> None:
    tache = dagbag.dags["alertes"].get_task("detection")
    assert "app.detection.internal_alerts" in tache.bash_command


def test_alertes_recommendation_task_calls_the_backend_cli(dagbag: DagBag) -> None:
    tache = dagbag.dags["alertes"].get_task("recommandations")
    assert "app.cli generate-recommendations" in tache.bash_command


def test_historical_import_calls_the_existing_backend_module(dagbag: DagBag) -> None:
    tache = dagbag.dags["historical_import"].get_task("import_historical")
    assert "app.etl.historical_import" in tache.bash_command


def test_historical_import_uses_the_expected_source_files(dagbag: DagBag) -> None:
    commande = dagbag.dags["historical_import"].get_task("import_historical").bash_command

    assert "--csv /opt/data/raw/all_sites_combined.csv" in commande
    assert "--metadata /opt/data/raw/dataset_metadata.json" in commande


def test_mock_api_import_calls_the_existing_backend_module(dagbag: DagBag) -> None:
    commande = dagbag.dags["mock_api_import"].get_task("import_mock_api").bash_command

    assert "app.etl.mock_api_import" in commande


def test_mock_api_import_uses_the_airflow_data_interval(dagbag: DagBag) -> None:
    commande = dagbag.dags["mock_api_import"].get_task("import_mock_api").bash_command

    assert "--start-time \"{{ data_interval_start.strftime('%Y-%m-%dT%H:%M:%S') }}\"" in commande
    assert "--end-time \"{{ data_interval_end.strftime('%Y-%m-%dT%H:%M:%S') }}\"" in commande
    assert "--limit 1000" in commande


@pytest.mark.parametrize("task_id", ["detection", "recommandations"])
def test_alertes_tasks_run_in_the_backend_environment(dagbag: DagBag, task_id: str) -> None:
    # Le backend a son propre venv dans l'image, distinct de celui de ml/ (ADR 0008).
    assert "/opt/backend" in dagbag.dags["alertes"].get_task(task_id).bash_command


def test_historical_import_runs_in_the_backend_environment(dagbag: DagBag) -> None:
    commande = dagbag.dags["historical_import"].get_task("import_historical").bash_command
    assert "/opt/backend" in commande


def test_mock_api_import_runs_in_the_backend_environment(dagbag: DagBag) -> None:
    commande = dagbag.dags["mock_api_import"].get_task("import_mock_api").bash_command

    assert "/opt/backend" in commande


def test_alertes_generates_recommendations_after_detecting(dagbag: DagBag) -> None:
    # `recommendation.alert_id` est une cle etrangere `NOT NULL` : la generation n'a rien a lire
    # tant que la detection n'a pas ecrit.
    assert dagbag.dags["alertes"].get_task("detection").downstream_task_ids == {"recommandations"}


def test_ml_score_reuses_the_model_path_written_by_ml_train(dagbag: DagBag) -> None:
    entrainement = dagbag.dags["ml_train"].get_task("train").bash_command
    scoring = dagbag.dags["ml_score"].get_task("score").bash_command
    chemin_modele = "/opt/ml/state/models/lightgbm-consumption.txt"

    assert chemin_modele in entrainement
    assert chemin_modele in scoring


@pytest.mark.parametrize("dag_id", DAG_IDS)
def test_no_two_runs_of_a_dag_overlap(dagbag: DagBag, dag_id: str) -> None:
    # Deux entrainements ecriraient le meme fichier modele, deux scorings inseriraient en meme
    # temps dans `prediction`, deux detections analyseraient la meme fenetre.
    assert dagbag.dags[dag_id].max_active_runs == 1


@pytest.mark.parametrize(("dag_id", "task_id"), TACHES)
def test_every_task_has_an_execution_timeout(dagbag: DagBag, dag_id: str, task_id: str) -> None:
    # Sans plafond, une connexion pendue immobilise un slot du scheduler indefiniment.
    assert dagbag.dags[dag_id].get_task(task_id).execution_timeout is not None


def test_ml_score_execution_timeout_stays_below_its_hourly_step(dagbag: DagBag) -> None:
    timeout = dagbag.dags["ml_score"].get_task("score").execution_timeout
    assert timeout is not None
    assert timeout < timedelta(hours=1)


def duree_au_pire(tache: BaseOperator) -> timedelta:
    # `execution_timeout` plafonne une tentative, pas la tache : deux reprises occupent trois
    # plafonds et deux delais d'attente.
    assert tache.execution_timeout is not None
    return (tache.retries + 1) * tache.execution_timeout + tache.retries * tache.retry_delay


def test_mock_api_import_worst_case_stays_below_its_hourly_step(
    dagbag: DagBag,
) -> None:
    tache = dagbag.dags["mock_api_import"].get_task("import_mock_api")

    assert duree_au_pire(tache) < timedelta(hours=1)


def test_alertes_worst_case_stays_below_its_hourly_step(dagbag: DagBag) -> None:
    # Les deux taches s'enchainent : c'est leur somme, reprises comprises, qui doit tenir dans le
    # pas horaire, sinon `max_active_runs=1` fait attendre l'execution suivante.
    taches = [
        dagbag.dags["alertes"].get_task(task_id) for task_id in ("detection", "recommandations")
    ]
    assert sum((duree_au_pire(tache) for tache in taches), timedelta()) < timedelta(hours=1)


def test_ml_score_retries_after_a_transient_failure(dagbag: DagBag) -> None:
    assert dagbag.dags["ml_score"].get_task("score").retries >= 1


@pytest.mark.parametrize("task_id", ["detection", "recommandations"])
def test_alertes_retries_after_a_transient_failure(dagbag: DagBag, task_id: str) -> None:
    # Les deux commandes sont idempotentes en base, une reprise ne duplique rien.
    assert dagbag.dags["alertes"].get_task(task_id).retries >= 1


def test_historical_import_retries_after_a_transient_failure(dagbag: DagBag) -> None:
    assert dagbag.dags["historical_import"].get_task("import_historical").retries >= 1


def test_mock_api_import_retries_after_a_transient_failure(dagbag: DagBag) -> None:
    assert dagbag.dags["mock_api_import"].get_task("import_mock_api").retries >= 1


def test_derive_runs_once_a_day(dagbag: DagBag) -> None:
    assert dagbag.dags["derive"].timetable.expression == "30 5 * * *"


def test_derive_calls_the_backend_drift_module(dagbag: DagBag) -> None:
    assert "app.monitoring.drift" in dagbag.dags["derive"].get_task("derive").bash_command


def test_derive_never_retries_a_detected_drift(dagbag: DagBag) -> None:
    # Une derive n'est pas une panne passagere : la rejouer la redeclarerait a l'identique.
    assert dagbag.dags["derive"].get_task("derive").retries == 0


@pytest.mark.parametrize(("dag_id", "task_id"), TACHES)
def test_tasks_never_resync_the_baked_environment(
    dagbag: DagBag, dag_id: str, task_id: str
) -> None:
    # Sans `--no-sync`, `uv run` reconstruit le projet a chaque execution.
    assert "--no-sync" in dagbag.dags[dag_id].get_task(task_id).bash_command
