FROM python:3.14-slim
RUN pip install --no-cache-dir --only-binary :all: mlflow==3.16.1 psycopg2-binary==2.9.13
RUN useradd --create-home --uid 1000 mlflow \
    && mkdir /mlartifacts \
    && chown mlflow /mlartifacts
USER mlflow
EXPOSE 5000
