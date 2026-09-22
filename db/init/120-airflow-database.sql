-- Base de metadonnees Airflow (api-server + scheduler + dag-processor, LocalExecutor). Separee de la base
-- applicative : les tables internes d'Airflow (dag_run, task_instance, ...) n'ont rien a faire
-- dans le schema metier. Meme conteneur Postgres que `enervision`/`enervision_test` plutot qu'un
-- service dedie, pour ne pas ajouter un conteneur de plus (issue #115).
CREATE DATABASE airflow;
