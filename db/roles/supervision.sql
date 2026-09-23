-- Contrainte : rôle en lecture seule de la supervision (Grafana, postgres-exporter) -
-- supervision.sql. Ses droits ne portent que sur les tables métier : jamais `app_user`, les
-- jetons ni le journal d'audit. `pg_monitor` donne à l'exportateur les vues de statistiques.
-- Rejoué par `make db-ensure-supervision`, qui passe `mot_de_passe` et `base` en variables psql :
-- crée le rôle au besoin, puis réaligne à chaque passage mot de passe et droits.
-- Piège : les tables doivent exister, d'où l'appel après `alembic upgrade head` dans `stack-up`.

SELECT 'CREATE ROLE supervision LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supervision') \gexec

ALTER ROLE supervision WITH LOGIN PASSWORD :'mot_de_passe';
GRANT pg_monitor TO supervision;
GRANT CONNECT ON DATABASE :"base" TO supervision;
GRANT USAGE ON SCHEMA public TO supervision;
GRANT SELECT ON site, reading, alert, prediction, recommendation, drift_report TO supervision;
