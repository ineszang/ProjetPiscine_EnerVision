# Architecture

Les vues d'architecture d'EnerVision. Un ADR (`../adr/`) **décide** et date une décision
structurante ; une vue d'architecture **décrit** le système qui en résulte. Quand les deux se
contredisent, c'est l'ADR qui fait foi et la vue qui est en retard.

## Les documents

| Document | Ce qu'il couvre |
|---|---|
| [00-vue-ensemble.md](00-vue-ensemble.md) | Jalons du projet, contexte, conteneurs, sécurité, flux bout en bout |
| [10-infra.md](10-infra.md) | Poste de développement, cible k3s, décisions figées, ports et noms |
| [20-backend.md](20-backend.md) | Couches FastAPI, séquence de démarrage, routes, configuration |
| [30-frontend.md](30-frontend.md) | Angular, arborescence cible, flux HTTP |
| [31-contrat-authentification.md](31-contrat-authentification.md) | Ce que le frontend doit savoir pour coder la connexion |
| [40-data.md](40-data.md) | Frontières `db/` et `alembic/`, cycle de vie d'une mesure, modèle |

L'observabilité et la CI/CD n'ont pas de document propre : ce sont des sections des documents
ci-dessus, tant que `monitoring/` et `etl/airflow/` ne contiennent que des `.gitkeep`. Elles en
sortiront le jour où elles auront de la matière. Un fichier vide de plus n'aide personne.

La sécurité applicative, elle, a désormais de la matière : la vue consolidée reste dans
[00-vue-ensemble.md](00-vue-ensemble.md), le détail dans [20-backend.md](20-backend.md), la
traçabilité OWASP dans [owasp-traceabilite.md](owasp-traceabilite.md), et les décisions dans les
ADR 0002 à 0004.

## Conventions

### Mermaid, et rien d'autre

GitHub rend Mermaid nativement dans les fichiers `.md`. Un diagramme est donc du texte : il se
relit en revue, il se diffe, et il ne se périme pas dans un binaire que plus personne ne sait
rouvrir six mois plus tard. Aucune image exportée, aucun `.drawio`, aucun `.png`.

### Chaque section porte son statut

Une large part de la stack n'est pas écrite. Une vue qui mélange l'existant et la cible sans le
dire devient fausse sans prévenir.

| Statut | Sens |
|---|---|
| `Fait` | Le code existe et tourne |
| `En cours` | Commencé, incomplet |
| `Cible` | Décidé, pas encore écrit |

### Légende des diagrammes

Trait plein pour ce qui tourne, trait pointillé pour ce qui est cible.

```mermaid
flowchart LR
  A[Composant en place] --> B[Composant en place]
  B -.-> C[Composant cible]
```

## Maintenance

**Toute PR qui change un composant met à jour sa vue dans la même PR.** Une vue qu'on promet de
mettre à jour plus tard ne l'est jamais.

Une documentation fausse coûte plus cher qu'une documentation absente : on la lit, on la croit, et
on construit dessus. Si une section ne peut plus être tenue à jour, elle est supprimée plutôt que
laissée à dériver.
