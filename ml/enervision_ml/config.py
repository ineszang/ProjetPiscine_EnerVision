"""Configuration minimale du pipeline, lue depuis l'environnement.

Pas de `BaseSettings` Pydantic ici : contrairement a `apps/backend`, ce n'est pas un service qui
tourne en continu mais un script CLI lance a la main (cf. `docs/ML-START.md`), donc pas de
surface de configuration a valider au demarrage d'un processus long.
"""

import os

# Piege : ce n'est pas `DATABASE_URL` (celui du backend applicatif, proprietaire du schema).
# `docs/ML-START.md` et l'ADR 0003 designent un role PostgreSQL dedie et restreint en lecture,
# `enervision_ml`, non encore provisionne (dette assumee). Reutiliser `DATABASE_URL` par defaut
# ferait tourner l'entrainement avec les droits d'ecriture complets de l'application, en
# silence.
ML_DATABASE_URL_ENV = "ML_DATABASE_URL"

MLFLOW_EXPERIMENT_NAME = "consumption-forecast"
MLFLOW_TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"


def database_url() -> str:
    valeur = os.environ.get(ML_DATABASE_URL_ENV)
    if not valeur:
        raise RuntimeError(
            f"{ML_DATABASE_URL_ENV} n'est pas defini. Elle doit pointer vers un role "
            "PostgreSQL en lecture seule sur `reading`/`site` (voir docs/ML-START.md)."
        )
    return valeur


def mlflow_tracking_uri() -> str | None:
    """`None` laisse MLflow choisir son magasin local par defaut.

    Piege : ce n'est plus `./mlruns` en clair depuis MLflow 3 (magasin fichier "maintenance
    mode", refuse une URI `file:` explicite sauf `MLFLOW_ALLOW_FILE_STORE=true`), mais une base
    SQLite locale (`./mlflow.db`).
    """
    return os.environ.get(MLFLOW_TRACKING_URI_ENV)
