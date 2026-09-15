# 0001 - PostgreSQL avec l'extension TimescaleDB

- Statut : accepte
- Date : 2026-09-14

## Contexte

EnerVision collecte, stocke et restitue des series temporelles energetiques sur une machine
on-premise. La charge est dominee par des insertions horodatees en flux et par des lectures
agregees sur des fenetres de temps. Airflow produira des agregations continues, Grafana lira
les memes donnees, et l'API FastAPI les exposera.

Un SGBD relationnel generaliste sait faire, mais degrade a mesure que la table de mesures
grossit : les index se fragmentent, les balayages de fenetre deviennent couteux, et il faut
ecrire a la main le partitionnement, la retention et les agregats pre-calcules.

## Decision

PostgreSQL 17 avec l'extension TimescaleDB, servie en local par l'image
`timescale/timescaledb-ha:pg17`.

PostgreSQL reste une base relationnelle standard : un seul SGBD pour les donnees metier et
les mesures, un seul dialecte SQL, un seul pilote (`asyncpg`), et l'outillage habituel.
TimescaleDB ajoute le partitionnement automatique, les agregations continues et les
politiques de retention sans changer de moteur.

L'image `-ha` plutot que l'image alpine : elle embarque `timescaledb_toolkit`, `postgis` et
`pgvector`. Le toolkit porte les fonctions de comblement de trous et d'analyse de series dont
l'ETL aura besoin, et changer d'image plus tard imposerait une reinitialisation du volume.

PG17 plutot que PG18 : c'est la version la mieux couverte par Airflow et Grafana a ce jour.

## Frontiere entre `db/` et `apps/backend/alembic/`

C'est la regle que ce document existe surtout pour fixer.

- `db/init/` : bootstrap joue **une seule fois**, a la premiere initialisation du conteneur.
  Extensions, bases annexes. Ne rejoue jamais sur un volume existant.
- `db/migrations/` : SQL versionne qui ne decoule pas du schema applicatif, typiquement les
  politiques de retention et de compression TimescaleDB.
- `apps/backend/alembic/` : le schema expose par l'API, et lui seul. C'est `Base.metadata`
  qui fait foi.

Une hypertable relevera des deux : Alembic cree la table, et le `create_hypertable()` vit
dans la meme revision Alembic, parce que separer les deux rendrait le schema irreproductible
depuis un seul `alembic upgrade head`.

## Consequences

- Le projet se lie a une extension, donc a un hebergement qui l'autorise. C'est acquis
  puisque le deploiement est on-premise.
- `CREATE EXTENSION` demande le superutilisateur : cela reste un acte de bootstrap, pas une
  migration applicative.
- Un bootstrap saute ne se voit pas au demarrage de l'API. Deux gardes couvrent ce cas :
  `/api/v1/health/ready` repond 503 si l'extension est absente, et la premiere revision
  Alembic refuse de s'appliquer.
- L'image `-ha` pese environ 1 Go, a telecharger une fois par poste.

## Alternatives ecartees

- **PostgreSQL nu, partitionnement manuel** : faisable, mais il faudrait reecrire ce que
  TimescaleDB fournit, et le maintenir.
- **InfluxDB** : tres bon sur la serie temporelle, mais imposerait un second SGBD pour le
  relationnel, donc deux dialectes, deux sauvegardes et des jointures applicatives.
- **ClickHouse** : taille pour un volume analytique que le projet n'atteindra pas, et moins
  a l'aise sur les ecritures unitaires frequentes du flux d'ingestion.
