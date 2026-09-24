# Garage

Stockage objet S3 de la stack, un conteneur par projet Compose (ADR 0019). Il ne sert qu'au DAG
`retention`, qui y archive les chunks de `reading` avant de les supprimer.

- `garage.toml` : configuration versionnée, sans secret, montée en lecture seule. Les secrets
  arrivent par l'environnement : `GARAGE_RPC_SECRET`, `GARAGE_ADMIN_TOKEN`, `GARAGE_METRICS_TOKEN`.
- Démarrage `--single-node --default-bucket` : le premier démarrage crée le layout, la clé
  `GARAGE_ACCESS_KEY` et le bucket `GARAGE_BUCKET`. Rejouable tant que les volumes `garage_meta`
  et `garage_data` sont conservés. Changer `GARAGE_SECRET_KEY` ensuite fait refuser le démarrage.
- Ports, sur `127.0.0.1` seulement : `GARAGE_S3_PORT` (3900) pour l'API S3, `GARAGE_ADMIN_PORT`
  (3903) pour `/health` (sans jeton) et `/metrics` (jeton `GARAGE_METRICS_TOKEN`, scruté par
  Prometheus). Le RPC 3901 n'est pas publié.
- Nœud unique, `replication_factor = 1`, moteur sqlite : aucune redondance, le coffre LUKS de la
  VM (ADR 0020) et l'instantané des métadonnées toutes les six heures sont les seules protections.

```bash
docker compose exec garage /garage status
docker compose exec garage /garage bucket info enervision-archives
docker compose exec garage /garage key info --show-secret "$GARAGE_ACCESS_KEY"
```

Tests de fumée : `tests/garage/test_smoke.py`, joués par la CI contre le vrai conteneur (job
« Validation des fichiers Compose et de la supervision »). En local, stack démarrée et `.env` chargé :
`uvx --with boto3 pytest tests/garage`.
