"""Isole Airflow d'un `~/airflow` reel : `AIRFLOW_HOME` doit etre pose avant le premier `import
airflow`, donc ici plutot que dans une fixture (les fixtures s'executent trop tard, apres que les
modules de test aient deja importe `airflow`)."""

import os
from pathlib import Path

_AIRFLOW_HOME = Path(__file__).resolve().parent / ".airflow_home"
_AIRFLOW_HOME.mkdir(exist_ok=True)

os.environ.setdefault("AIRFLOW_HOME", str(_AIRFLOW_HOME))
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")
os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
os.environ.setdefault(
    "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", f"sqlite:///{_AIRFLOW_HOME / 'airflow.db'}"
)
