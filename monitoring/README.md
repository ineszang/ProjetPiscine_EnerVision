# Supervision

Prometheus, Alertmanager, Grafana et trois exporteurs, sous le profil Compose `monitoring`.
Issue #26, décisions dans l'ADR 0016, vue d'architecture dans
`docs/architecture/60-observabilite.md`.

| Service | Image | Rôle | Accès |
|---|---|---|---|
| `prometheus` | `prom/prometheus` | Collecte toutes les 15 s, évalue les règles, garde 15 jours (1 Go au plus) | `127.0.0.1:${PROMETHEUS_PORT:-9090}` |
| `alertmanager` | `prom/alertmanager` | Groupe les alertes et les envoie par courriel à Mailpit | `127.0.0.1:${ALERTMANAGER_PORT:-9093}` |
| `grafana` | `grafana/grafana` | Trois tableaux de bord provisionnés, dossier « EnerVision » | `127.0.0.1:${GRAFANA_PORT:-3001}` |
| `postgres-exporter` | `prometheuscommunity/postgres-exporter` | Connexions, transactions, taille des bases | réseau interne |
| `node-exporter` | `prom/node-exporter` | Processeur, mémoire et disque de l'hôte | réseau interne |
| `cadvisor` | `gcr.io/cadvisor/cadvisor` | Mémoire et processeur par conteneur | réseau interne |

Les interfaces n'écoutent que sur `127.0.0.1`. Depuis un poste, on passe par un tunnel SSH,
comme pour Airflow :

```bash
ssh -L 3001:127.0.0.1:3001 -L 9090:127.0.0.1:9090 enervision@10.101.200.37
```

## Démarrer

- **Prod.** `COMPOSE_PROFILES=monitoring` dans le `.env` : `make stack-up`, donc chaque
  déploiement, démarre la supervision et pose le rôle `supervision` après les migrations.
- **Recette et poste.** À la demande, sur une stack déjà démarrée : `make monitoring-up`. Les
  services partent en `--no-deps`, sans toucher aux autres.

Trois secrets sont requis, et `make stack-up` comme `make monitoring-up` refusent de démarrer
s'il en manque un. `scripts/provision-host.sh` les génère pour un nouvel environnement.

| Variable | Rôle |
|---|---|
| `APP_METRICS_TOKEN` | Jeton que Prometheus présente sur `/metrics`, et que l'API exige dès qu'il est posé |
| `GRAFANA_ADMIN_PASSWORD` | Compte `admin` de Grafana. Sans lui, le conteneur refuse de démarrer |
| `SUPERVISION_DB_PASSWORD` | Rôle PostgreSQL `supervision`, en lecture seule (`db/roles/supervision.sql`) |

L'API doit tourner en conteneur (`make stack-up`, ou `docker compose up -d backend`) :
Prometheus la joint en `backend:8000`, sur le réseau du projet. Une API lancée par `make dev`
sur l'hôte reste hors de sa portée, et l'alerte `ApiIndisponible` le signale.

## Tableaux de bord

| Tableau | Source | Contenu |
|---|---|---|
| EnerVision · API | Prometheus | Débit, erreurs 5xx, latences p50/p95/p99, globales et par route. C'est lui qu'on regarde pendant un tir k6 |
| EnerVision · Données et modèle | TimescaleDB | Fraîcheur des relevés par site, relevés ingérés, alertes par sévérité, dérive du modèle (`drift_report`) |
| EnerVision · Infrastructure | Prometheus | Hôte, mémoire et processeur par conteneur (recette et prod comprises), PostgreSQL |

Les fichiers JSON de `grafana/dashboards` sont la source : Grafana les recharge et refuse de
les modifier depuis l'interface. Pour changer un tableau, l'exporter en JSON depuis Grafana et
remplacer le fichier.

## Alertes

`prometheus/rules/enervision.yml` définit les règles, et `prometheus/tests/enervision.test.yml`
porte un cas par règle, joué par `promtool test rules`.

| Alerte | Condition | Sévérité |
|---|---|---|
| `ApiIndisponible` | `/metrics` injoignable pendant 2 min | critical |
| `ApiErreursServeur` | Plus de 5 % de 5xx sur 5 min | critical |
| `ApiLatenceElevee` | p95 au-delà d'une seconde pendant 10 min | warning |
| `BaseIndisponible` | Exportateur sans connexion pendant 2 min | critical |
| `BaseConnexionsSaturees` | Plus de 80 % de `max_connections` | warning |
| `HoteMemoireSaturee` | Mémoire au-delà de 90 % pendant 10 min | warning |
| `HoteDisquePlein` | Moins de 10 % libres sur `/` | critical |
| `HoteCpuSature` | Processeur au-delà de 90 % pendant 15 min | warning |
| `CibleInjoignable` | Un exporteur muet pendant 5 min | warning |

Alertmanager envoie les courriels à `supervision@enervision.fr` via Mailpit, qui les capture :
ils se lisent dans son interface. Un `critical` masque le `warning` de la même cible.

## Vérifier la configuration

```bash
make monitoring-check   # promtool check config et test rules, amtool check-config, JSON des tableaux
```

La CI joue les mêmes commandes (job « Validation des fichiers Compose et de la supervision »)
dès que `monitoring/` ou un fichier Compose change.
