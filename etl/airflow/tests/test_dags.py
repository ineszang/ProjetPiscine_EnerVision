"""Tests d'integrite des DAGs : s'importent sans erreur, structure attendue. Pas d'execution
reelle des taches (ca reclamerait le conteneur avec `uv`/`enervision_ml`), juste la definition."""

from datetime import timedelta
from pathlib import Path

import pytest
from airflow.models.dagbag import DagBag

DAGS_FOLDER = Path(__file__).resolve().parent.parent / "dags"


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)


def test_dags_folder_has_no_import_error(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}


def test_every_expected_dag_is_discovered(dagbag: DagBag) -> None:
    assert set(dagbag.dag_ids) == {"ml_train", "ml_score"}


def test_ml_train_has_no_schedule(dagbag: DagBag) -> None:
    assert dagbag.dags["ml_train"].timetable.summary == "None"


def test_ml_score_runs_every_hour(dagbag: DagBag) -> None:
    # `@hourly` est un alias Airflow pour ce cron, c'est sous cette forme que `.summary` le rend.
    assert dagbag.dags["ml_score"].timetable.summary == "0 * * * *"


def test_ml_train_task_calls_the_training_module(dagbag: DagBag) -> None:
    tache = dagbag.dags["ml_train"].get_task("train")
    assert "enervision_ml.train" in tache.bash_command


def test_ml_score_task_calls_the_scoring_module(dagbag: DagBag) -> None:
    tache = dagbag.dags["ml_score"].get_task("score")
    assert "enervision_ml.score" in tache.bash_command


def test_ml_score_reuses_the_model_path_written_by_ml_train(dagbag: DagBag) -> None:
    entrainement = dagbag.dags["ml_train"].get_task("train").bash_command
    scoring = dagbag.dags["ml_score"].get_task("score").bash_command
    chemin_modele = "/opt/ml/state/models/lightgbm-consumption.txt"

    assert chemin_modele in entrainement
    assert chemin_modele in scoring


@pytest.mark.parametrize("dag_id", ["ml_train", "ml_score"])
def test_no_two_runs_of_a_dag_overlap(dagbag: DagBag, dag_id: str) -> None:
    # Deux entrainements ecriraient le meme fichier modele, deux scorings inseriraient en meme
    # temps dans `prediction`.
    assert dagbag.dags[dag_id].max_active_runs == 1


@pytest.mark.parametrize(("dag_id", "task_id"), [("ml_train", "train"), ("ml_score", "score")])
def test_every_task_has_an_execution_timeout(dagbag: DagBag, dag_id: str, task_id: str) -> None:
    # Sans plafond, une connexion pendue immobilise un slot du scheduler indefiniment.
    assert dagbag.dags[dag_id].get_task(task_id).execution_timeout is not None


def test_ml_score_execution_timeout_stays_below_its_hourly_step(dagbag: DagBag) -> None:
    timeout = dagbag.dags["ml_score"].get_task("score").execution_timeout
    assert timeout is not None
    assert timeout < timedelta(hours=1)


def test_ml_score_retries_after_a_transient_failure(dagbag: DagBag) -> None:
    assert dagbag.dags["ml_score"].get_task("score").retries >= 1


@pytest.mark.parametrize(("dag_id", "task_id"), [("ml_train", "train"), ("ml_score", "score")])
def test_tasks_never_resync_the_baked_environment(
    dagbag: DagBag, dag_id: str, task_id: str
) -> None:
    # Sans `--no-sync`, `uv run` reconstruit `enervision-ml` a chaque execution.
    assert "--no-sync" in dagbag.dags[dag_id].get_task(task_id).bash_command
