# Documentation

- `adr` : décisions d'architecture, une par fichier, numérotées et immuables.
- `architecture` : les vues du système. Point d'entrée : [architecture/README.md](architecture/README.md).

## Décisions en vigueur

| ADR | Sujet |
|---|---|
| [0001](adr/0001-postgresql-timescaledb.md) | PostgreSQL avec l'extension TimescaleDB |
| [0002](adr/0002-authentification-jwt-et-refresh-opaque.md) | Authentification par JWT d'accès et jeton de rafraîchissement opaque |
| [0003](adr/0003-autorisation-rbac-a-trois-roles.md) | Autorisation RBAC à trois rôles, relecture du compte à chaque requête |
| [0004](adr/0004-journal-d-audit-en-ajout-seul.md) | Journal d'audit en ajout seul, garanti par PostgreSQL |
| [0005](adr/0005-modele-prediction-lightgbm.md) | LightGBM pour la prédiction de consommation, un modèle global |
| [0006](adr/0006-moteur-de-regles-dans-le-backend.md) | Le moteur de règles de recommandation vit dans le backend, pas dans `ml/` |
| [0007](adr/0007-terminaison-tls-et-reverse-proxy-nginx.md) | Terminaison TLS par un reverse proxy Nginx, en Docker Compose |
| [0008](adr/0008-airflow-execute-le-code-du-backend.md) | Airflow exécute le code du backend en sous-processus, dans son propre environnement |
| [0009](adr/0009-deux-environnements-compose-sur-la-vm-eni.md) | Deux environnements sur la VM ENI, un projet Compose chacun, déployés par un runner auto-hébergé |
| [0010](adr/0010-terraform-provisionne-github-actions-deploie.md) | Terraform provisionne la machine, GitHub Actions déploie l'application |
