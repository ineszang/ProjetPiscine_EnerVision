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
