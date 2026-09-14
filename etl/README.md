# ETL

Orchestration Apache Airflow : ingestion des mesures, agregations continues,
controles de qualite. Non initialise, voir le ticket dedie.

- `airflow/dags` : DAGs.
- `airflow/plugins` : operateurs et hooks maison.
- `airflow/include` : requetes SQL et ressources referencees par les DAGs.
- `airflow/tests` : tests d'integrite des DAGs.
