# Base de donnees

PostgreSQL avec l'extension TimescaleDB. Non initialise, voir le ticket dedie.

- `init` : scripts de bootstrap joues au premier demarrage du conteneur.
- `migrations` : migrations SQL versionnees.
- `seeds` : jeux de donnees de reference.

Les migrations du schema applicatif expose par l'API vivent dans
`apps/backend/alembic`, pas ici.
