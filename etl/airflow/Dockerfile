# Image Airflow EnerVision : ajoute le projet ml/ dans son propre environnement Python 3.14,
# distinct du Python 3.12 qui fait tourner Airflow lui-meme (apache-airflow 2.10 ne supporte pas
# 3.14), pour que les DAGs puissent lancer `uv run python -m enervision_ml.train`/`.score` en
# sous-processus. Airflow ne devient jamais un consommateur direct de LightGBM/MLflow.
FROM apache/airflow:2.10.4-python3.12

# LightGBM est compile contre libgomp (OpenMP), absent de l'image de base (minimale, sans
# toolchain de compilation). Sans lui : `OSError: libgomp.so.1: cannot open shared object file`
# au premier `import lightgbm`, seulement au moment ou une tache tourne reellement.
USER root
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# Pre-cree, appartenant a `airflow` : docker-compose y monte un volume nomme partage entre
# `ml_train` et `ml_score` (le modele ecrit par l'un, lu par l'autre). Un volume nomme herite des
# permissions du repertoire qu'il recouvre a son premier montage ; sans ce chown prealable, il
# serait cree root:root et illisible par le conteneur, qui tourne en `airflow` (uid 50000).
RUN mkdir -p /opt/ml/state && chown -R airflow:root /opt/ml
USER airflow

# L'image de base embarque deja un `uv`, mais trop ancien (0.4.29) pour le format de verrou de
# `ml/uv.lock`. On le remplace par la version deja pinnee ailleurs dans le depot
# (apps/backend/Dockerfile).
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /home/airflow/.local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/ml/.venv

WORKDIR /opt/ml

COPY --chown=airflow:root ml/pyproject.toml ml/uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY --chown=airflow:root ml/enervision_ml ./enervision_ml
RUN uv sync --locked --no-dev

WORKDIR /opt/airflow
