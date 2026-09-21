"""Tests d'integrite des DAGs : s'importent sans erreur et ont la structure attendue.

Les tests ne lancent pas reellement les traitements : ils valident uniquement la definition
des DAGs et leurs commandes.
"""

from datetime import timedelta
from pathlib import Path

import pytest
from airflow.models.baseoperator import BaseOperator
from airflow.models.dagbag import DagBag

DAGS_FOLDER = Path(__file__).resolve().parent.parent / "dags"

DAG_IDS = ["ml_train", "ml_score", "alertes", "historical_import"]

TACHES = [
    ("ml_train", "train"),
    ("ml_score", "score"),
    ("alertes", "detection"),
    ("alertes", "recommandations"),
    ("historical_import", "import_historical"),
]


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)


def test_dags_folder_has_no_import_error(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}


def test_every_expected_dag_is_discovered(dagbag: DagBag) -> None:
    assert set(dagbag.dag_ids) == set(DAG_IDS)


def test_ml_train_has_no_schedule(dagbag: DagBag) -> None:
    assert dagbag.dags["ml_train"].timetable.summary == "None"


def test_ml_score_runs_every_hour(dagbag: DagBag) -> None:
    assert dagbag.dags["ml_score"].timetable.summary == "0 * * * *"


def test_alertes_runs_after_the_hourly_scoring(dagbag: DagBag) -> None:
    assert dagbag.dags["alertes"].timetable.summary == "15 * * * *"


def test_historical_import_has_no_schedule(dagbag: DagBag) -> None:
    assert dagbag.dags["historical_import"].timetable.summary == "None"


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


@pytest.mark.parametrize("task_id", ["detection", "recommandations"])
def test_alertes_tasks_run_in_the_backend_environment(dagbag: DagBag, task_id: str) -> None:
    assert "/opt/backend" in dagbag.dags["alertes"].get_task(task_id).bash_command


def test_historical_import_runs_in_the_backend_environment(dagbag: DagBag) -> None:
    commande = dagbag.dags["historical_import"].get_task("import_historical").bash_command
    assert "/opt/backend" in commande


def test_alertes_generates_recommendations_after_detecting(dagbag: DagBag) -> None:
    assert dagbag.dags["alertes"].get_task("detection").downstream_task_ids == {"recommandations"}


def test_ml_score_reuses_the_model_path_written_by_ml_train(dagbag: DagBag) -> None:
    entrainement = dagbag.dags["ml_train"].get_task("train").bash_command
    scoring = dagbag.dags["ml_score"].get_task("score").bash_command
    chemin_modele = "/opt/ml/state/models/lightgbm-consumption.txt"

    assert chemin_modele in entrainement
    assert chemin_modele in scoring


@pytest.mark.parametrize("dag_id", DAG_IDS)
def test_no_two_runs_of_a_dag_overlap(dagbag: DagBag, dag_id: str) -> None:
    assert dagbag.dags[dag_id].max_active_runs == 1


@pytest.mark.parametrize(("dag_id", "task_id"), TACHES)
def test_every_task_has_an_execution_timeout(dagbag: DagBag, dag_id: str, task_id: str) -> None:
    assert dagbag.dags[dag_id].get_task(task_id).execution_timeout is not None


def test_ml_score_execution_timeout_stays_below_its_hourly_step(dagbag: DagBag) -> None:
    timeout = dagbag.dags["ml_score"].get_task("score").execution_timeout
    assert timeout is not None
    assert timeout < timedelta(hours=1)


def duree_au_pire(tache: BaseOperator) -> timedelta:
    assert tache.execution_timeout is not None
    return (tache.retries + 1) * tache.execution_timeout + tache.retries * tache.retry_delay


def test_alertes_worst_case_stays_below_its_hourly_step(dagbag: DagBag) -> None:
    taches = [
        dagbag.dags["alertes"].get_task(task_id) for task_id in ("detection", "recommandations")
    ]
    assert sum((duree_au_pire(tache) for tache in taches), timedelta()) < timedelta(hours=1)


def test_ml_score_retries_after_a_transient_failure(dagbag: DagBag) -> None:
    assert dagbag.dags["ml_score"].get_task("score").retries >= 1


@pytest.mark.parametrize("task_id", ["detection", "recommandations"])
def test_alertes_retries_after_a_transient_failure(dagbag: DagBag, task_id: str) -> None:
    assert dagbag.dags["alertes"].get_task(task_id).retries >= 1


def test_historical_import_retries_after_a_transient_failure(dagbag: DagBag) -> None:
    assert dagbag.dags["historical_import"].get_task("import_historical").retries >= 1


@pytest.mark.parametrize(("dag_id", "task_id"), TACHES)
def test_tasks_never_resync_the_baked_environment(
    dagbag: DagBag, dag_id: str, task_id: str
) -> None:
    assert "--no-sync" in dagbag.dags[dag_id].get_task(task_id).bash_command
