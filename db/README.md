# Base de donnees

PostgreSQL 17 avec l'extension TimescaleDB, servie en local par le service `db` du
`docker-compose.yml` racine (image `timescale/timescaledb-ha:pg17`).

- `init` : scripts de bootstrap joues au premier demarrage du conteneur.
- `migrations` : migrations SQL versionnees.
- `seeds` : jeux de donnees de reference. `demo.sql` seme trois sites `demo-*`, 72 heures de
  releves, des alertes et des rapports de derive pour la CI, l'e2e et les tirs de charge. Base
  jetable seulement.
- `roles` : roles PostgreSQL hors schema applicatif. `supervision.sql` pose le role en lecture
  seule de Grafana et de postgres-exporter, rejoue par `make db-ensure-supervision` (et par
  `make stack-up` quand la supervision est active) plutot que par `init`, qui ne rejoue jamais.

Les migrations du schema applicatif expose par l'API vivent dans
`apps/backend/alembic`, pas ici.

## `init` ne rejoue jamais

Ces scripts sont montes sur `/docker-entrypoint-initdb.d`, dont PostgreSQL ne joue le
contenu qu'a la toute premiere initialisation, quand `PGDATA` est vide. Modifier ou
ajouter un script ensuite reste sans effet sur une base existante : il faut detruire
le volume, ce que fait `make db-reset`.

L'image apporte ses propres scripts dans ce dossier, et ils comptent :

| Script | Origine | Role |
|---|---|---|
| `000_install_timescaledb.sh` | image | Cree l'extension dans `postgres`, `template1` et la base applicative, et fixe `timescaledb.telemetry_level`. |
| `001_timescaledb_tune.sh` | image | Lance `timescaledb-tune` sur la memoire et les CPU vus par le conteneur. |
| `010_install_timescaledb_toolkit.sh` | image | Ajoute `timescaledb_toolkit`. |
| `100-extensions.sql` | ce depot | Declare explicitement les extensions attendues. |
| `110-test-database.sql` | ce depot | Cree `enervision_test`, attendue par la suite de tests du backend. |

D'ou deux contraintes dans `docker-compose.yml`. Nos fichiers sont **montes un par un**,
et non par leur dossier : un montage de `./db/init` sur `/docker-entrypoint-initdb.d`
remplacerait le dossier de l'image au lieu de s'y ajouter, et ferait disparaitre les trois
scripts ci-dessus sans le moindre message. Ajouter un fichier ici impose donc d'ajouter
une ligne la-bas. Et leur numerotation commence a `100` pour passer apres `010`, y compris
en locale C ou un prefixe a deux chiffres se trierait avant.

Comme un bootstrap peut toujours avoir ete saute, deux gardes le rattrapent :
`/api/v1/health/ready` repond 503 si l'extension n'est pas chargee, et la premiere
revision Alembic refuse de s'appliquer.
