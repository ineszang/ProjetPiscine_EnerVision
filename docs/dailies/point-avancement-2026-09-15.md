# Revue 1 - Cadrage (Jalon 2 - 15/09)

Présents :
- Dorian
- Johan
- Inès
- Meryem
- Valentin

**Objectif:** Valider le périmètre retenu et les choix technologiques initiaux.

## KPIs

| Indicateur | Valeur |
| --- | --- |
| Issues fermées / Issues totales | 4/4 |
| Must fermés / Must total | 4/41 |
| Jours écoulés / jours restants | 2/9 |

## Issues du jalon

| Issue | Titre | Labels | Fermée par |
| --- | --- | --- | --- |
| #58 | Préparer les tests unitaires du frontend pour permettre leur implémentation continue | frontend, test | Dorian |
| #57 | Préparer les tests unitaires du backend pour permettre leur implémentation continue | backend, test | Dorian |
| #18 | Provisionner un cluster K8s single-node (k3s) via Terraform | infra | Dorian |
| #67 | docs: fonder la documentation d'architecture du monorepo | documentation | Johan |

## Décisions prises

| Décision | Porteur | Justification |
| --- | --- | --- |
| Vitest retenu comme framework de tests unitaires frontend (PR #62) | Valentin | Standard de l'écosystème Vite ; permet scripts npm et mesure de couverture dès maintenant. |
| pytest / pytest-asyncio + coverage.py côté backend, seuil de couverture fixé à 85 % (PR #65) | Johan | Le code applicatif est encore un squelette : c'est le bon moment pour poser les conventions de test avant l'arrivée de la logique métier. |
| Cluster K8s single-node (k3s) provisionné via Terraform, version k3s figée en v1.31.5+k3s1, option `--write-kubeconfig-mode 644` retirée (PR #66) | Dorian | Reproductibilité de l'infra on-premise (infra as code) et durcissement sécurité du kubeconfig. |
| Documentation d'architecture en 5 vues Mermaid + index dans `docs/architecture/`, avec statuts Done/In Progress/Target (PR #68) | Johan | Rendu natif GitHub sans assets binaires ; corrige des affirmations obsolètes (frontend, port 4200, arborescence). |

## Actions à mener

| Action | Responsable | Échéance |
| --- | --- | --- |
| Alimenter les tests unitaires frontend au fil des features, sur le socle Vitest posé en #58/#62 | Valentin | J4 (22/09) |
| Implémenter la logique métier backend en respectant la structure de tests (`tests/api`, `tests/db`, `tests/core`, `tests/services`, `tests/repositories`) | Johan | J3 (18/09) |
| Maintenir les vues d'architecture (`docs/architecture/`) à jour à chaque PR modifiant un composant, comme prévu par la règle posée en #67/#68 | Équipe | Continu |
| Brancher `make test` / `make dev` / `make check` dans la CI | Dorian | J3 (18/09) |
