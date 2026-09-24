# 0019 - Stockage objet Garage par environnement, et cycle de vie des mesures : export puis suppression

- Statut : accepté
- Date : 2026-09-24

## Contexte

Les issues #24 « Déployer MinIO » et #36 « Politique de rétention + export vers MinIO » datent du
cadrage du 14/09. Au 24/09, la hypertable `reading` grossit d'une lecture par site et par heure
sans qu'aucune politique ne la borne, et `docs/architecture/40-data.md` classe rétention et
compression parmi les cibles non faites. Aucun stockage objet ne tourne.

La PR 164 a posé une amorce : un projet Compose à part dans `garage/`, l'image `dxflrs/garage:v1.0.1`,
des secrets dans un `garage.toml` gitignoré et des tests de fumée boto3 que rien ne jouait. Rien
n'était branché sur les trois environnements de la VM ([ADR 0009](0009-deux-environnements-compose-sur-la-vm-eni.md),
[ADR 0017](0017-environnement-dev-a-la-demande.md)), ni sur la CI, ni sur la supervision.

Contrainte propre au projet : le jeu historique s'arrête au 31/12/2024 et `make demo-data` s'y
ancre. Une rétention sous vingt-et-un mois effacerait la démonstration.

## Décision

**Garage plutôt que MinIO**, en `v2.4.1`. Un binaire statique de quelques dizaines de Mo, une
API S3 suffisante pour boto3, des métriques Prometheus natives, et depuis la `v2.3.0` un mode
`--single-node --default-bucket` qui crée layout, clé et bucket au premier démarrage à partir de
trois variables d'environnement : aucun conteneur d'initialisation, aucune séquence CLI à rejouer.

**Un Garage par projet Compose.** Le service `garage` vit dans `docker-compose.yml`, comme `db`
et `mailpit`. Chaque environnement a le sien, ses volumes `garage_meta` et `garage_data`, ses
secrets et ses ports sur `127.0.0.1` : S3 `3900`, `3910`, `3920` et admin `3903`, `3913`, `3923`
pour prod, recette et dev. Le RPC n'est pas publié. Rien ne passe par le proxy.

**`infra/garage/garage.toml` est versionné sans secret.** `GARAGE_RPC_SECRET` (32 octets
hexadécimaux), `GARAGE_ADMIN_TOKEN` et `GARAGE_METRICS_TOKEN` arrivent par l'environnement, comme
les autres secrets du `.env`, générés par `scripts/provision-host.sh`. L'image est `FROM scratch`,
sans shell : la garde sur les secrets vit dans le `Makefile` (`garage-garde`, appelée par
`services-up` et `stack-up`), et le healthcheck est `garage health -q`.

**Nœud unique assumé.** `replication_factor = 1` et moteur `sqlite`, avec un instantané des
métadonnées toutes les six heures. La documentation de Garage réserve ce facteur aux
déploiements de test : ici la machine est unique, la redondance n'existe pour aucun autre service,
et le chiffrement au repos est traité à part ([ADR 0020](0020-chiffrement-au-repos-coffre-luks-et-sse-c.md)). LMDB, le moteur par défaut, se corrompt à l'arrêt brutal et rien ne le reconstruirait.

**La rétention de `reading` est un traitement du backend, ordonnancé par Airflow.** Le DAG
`retention` lance chaque nuit `app.etl.reading_retention` ([ADR 0008](0008-airflow-execute-le-code-du-backend.md)),
qui, pour chaque chunk entièrement plus vieux que `READING_RETENTION_DAYS` (1095 jours par défaut) :

1. lit ses lignes par la hypertable (`WHERE timestamp >= range_start AND timestamp < range_end`) ;
2. les sérialise en CSV gzip reproductible, les colonnes `jsonb` et `text[]` en JSON ;
3. les dépose sur Garage sous `reading/<annee>/reading_<debut>_<fin>.csv.gz`, chiffrées par SSE-C,
   avec le sha256 et le nombre de lignes en métadonnées ; un objet déjà présent avec le même sha
   n'est pas réécrit ;
4. relit l'objet et compare son sha256 ;
5. supprime ce seul chunk par `drop_chunks(older_than => range_end, newer_than => range_start)`,
   dans une transaction dédiée et courte.

`add_retention_policy` de TimescaleDB est écartée : son travail de fond supprimerait sans avoir
exporté. `db/migrations/` reste vide pour la même raison.

**Supervision.** Prometheus scrute `garage:3903/metrics` avec `GARAGE_METRICS_TOKEN` passé en
secret Compose. `CibleInjoignable` couvre son indisponibilité, aucune règle nouvelle.

**CI.** Le job « Validation des fichiers Compose et de la supervision » démarre le vrai conteneur
avec des secrets générés, attend son healthcheck et joue `tests/garage/test_smoke.py` : bucket
présent, aller-retour, suppression effective, et lecture refusée sans clé SSE-C.

## Alternatives écartées

| Écartée | Raison |
|---|---|
| MinIO | Plus lourd, licence AGPL, orientation vers l'offre commerciale ; l'équipe préfère un composant qu'elle peut lire en entier. Le titre des issues date du cadrage, la décision a changé depuis. |
| Un Garage partagé entre les trois environnements | Un troisième projet Compose et des réseaux externes à déclarer, le couplage que l'ADR 0009 évite. |
| `add_retention_policy` TimescaleDB, plus un export séparé | Deux horloges indépendantes : un export en retard d'une semaine perd les données que la politique a déjà supprimées. |
| Export Parquet | Une dépendance binaire de plus (`pyarrow`) dans l'image Airflow et le backend, pour un gain nul sur 120 000 lignes ; le CSV gzip est le format d'origine du jeu historique. |
| Commande de restauration | Hors périmètre du J6. La procédure manuelle tient en trois commandes : `get_object` avec la clé SSE-C, `gunzip`, `COPY reading FROM STDIN CSV HEADER` ; `uq_reading_source` refuse les doublons. |
| Compression TimescaleDB des chunks chauds | Autre chantier, sans lien avec l'export. |

## Conséquences

- **Premier passage en prod** (24/09/2026, borne à trois ans) : les chunks de janvier à septembre
  2023 sont archivés puis supprimés, environ quarante objets. La démonstration ancrée fin 2024
  et l'entraînement du modèle (quinze mois d'historique plus 2026) ne sont pas touchés.
- **`drop_chunks` verrouille `site` et `dataset`** en exclusif jusqu'au COMMIT : le DAG tourne à
  03h20, entre `alertes` (:15) et `derive` (05h30), et chaque suppression est une transaction
  propre.
- **Secrets.** `.env.example` gagne `GARAGE_RPC_SECRET`, `GARAGE_ADMIN_TOKEN`,
  `GARAGE_METRICS_TOKEN`, `GARAGE_ACCESS_KEY`, `GARAGE_SECRET_KEY`, `GARAGE_BUCKET`,
  `GARAGE_S3_PORT`, `GARAGE_ADMIN_PORT`, `GARAGE_SSE_KEY` et `READING_RETENTION_DAYS`.
  `provision-host.sh` les génère et réaligne les `.env` de la VM : il doit être rejoué avant le
  premier déploiement qui suit ce changement, sinon `make stack-up` s'arrête sur la garde.
- **Rotation.** `GARAGE_SECRET_KEY` ne se change pas sur un volume peuplé : Garage refuse de
  démarrer. Passer par `garage key` en CLI, ou recréer le volume d'un environnement jetable.
- **Perte de `GARAGE_SSE_KEY` = archives illisibles.** La clé est sauvegardée hors de la VM.
- **Postes de développement.** `make dev` exige désormais les clés `GARAGE_*` dans le `.env`,
  comme il exigeait déjà les clés Airflow.
- **Métriques Garage** visibles dans Prometheus ; aucun tableau Grafana dédié pour l'instant.
