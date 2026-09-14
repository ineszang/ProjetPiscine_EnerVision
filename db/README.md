# Base de donnees

PostgreSQL 17 avec l'extension TimescaleDB, servie en local par le service `db` du
`docker-compose.yml` racine (image `timescale/timescaledb-ha:pg17`).

- `init` : scripts de bootstrap joues au premier demarrage du conteneur.
- `migrations` : migrations SQL versionnees.
- `seeds` : jeux de donnees de reference.

Les migrations du schema applicatif expose par l'API vivent dans
`apps/backend/alembic`, pas ici.

## `init` ne rejoue jamais

Le dossier est monte sur `/docker-entrypoint-initdb.d`, dont PostgreSQL ne joue le
contenu qu'a la toute premiere initialisation, quand `PGDATA` est vide. Modifier ou
ajouter un script ensuite reste sans effet sur une base existante :

```bash
docker compose down -v && docker compose up -d db
```

L'image joue d'abord ses propres scripts (`000_`, `001_`, `010_`), dont un
`CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit CASCADE` qui installe `timescaledb`
au passage dans `postgres`, `template1` et la base applicative. Nos fichiers sont
numerotes a partir de `100` pour passer apres, quelle que soit la locale de tri.

| Script | Role |
|---|---|
| `100-extensions.sql` | Declare explicitement les extensions attendues. |
| `110-test-database.sql` | Cree `enervision_test`, attendue par la suite de tests du backend. |

Comme un bootstrap peut toujours avoir ete saute, c'est `/api/v1/health/ready` qui fait
foi : la sonde refuse de repondre 200 si l'extension n'est pas chargee.
