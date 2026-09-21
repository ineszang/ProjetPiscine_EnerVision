"""Tests d'integrite des DAGs : s'importent sans erreur, structure attendue. Pas d'execution
reelle des taches (ca reclamerait le conteneur avec `uv`/`enervision_ml`), juste la definition."""

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


def test_ml_train_has_no_schedule() -> None:
    dagbag = DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)
    assert dagbag.dags["ml_train"].timetable.summary == "None"


def test_ml_score_runs_every_hour() -> None:
    # `@hourly` est un alias Airflow pour ce cron, c'est sous cette forme que `.summary` le rend.
    dagbag = DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)
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
