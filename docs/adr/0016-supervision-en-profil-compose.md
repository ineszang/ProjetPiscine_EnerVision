# 0016 - La supervision vit dans un profil Compose, active en prod

- Statut : accepté
- Date : 2026-09-23

## Contexte

L'API expose `/metrics` au format Prometheus depuis le début, et `monitoring/` ne contenait que
des `.gitkeep` : aucun collecteur, aucun tableau de bord, aucune alerte (issue #26). La VM ENI
porte la recette et la prod, deux piles complètes, sur 8 Go de mémoire (ADR 0009).

## Décision

**Prometheus, Alertmanager, Grafana et trois exporteurs** sont des services de
`docker-compose.yml` sous le profil `monitoring` : postgres-exporter, node-exporter et cAdvisor.

- **En prod**, `COMPOSE_PROFILES=monitoring` dans le `.env` : `make stack-up`, donc chaque
  déploiement, les démarre avec le reste.
- **En recette et sur le poste**, ils se lancent à la demande (`make monitoring-up`, en
  `--no-deps`). La recette ne paie rien tant qu'on ne les lance pas.
- **Mémoire.** Chaque service a un `mem_limit`, pour environ 700 Mo au total.
- **Accès.** Les interfaces n'écoutent que sur `127.0.0.1` et se consultent par tunnel SSH,
  comme Airflow. Rien ne passe par le proxy : Grafana derrière nginx exigerait sa propre
  authentification forte, et rendrait `/metrics` joignable à un routage près (ADR 0007).
- **Sécurité.**
  - **Jeton.** Prometheus présente sur `/metrics` le jeton `APP_METRICS_TOKEN`, passé en
    secret Compose. Il est exigé dès que la supervision tourne.
  - **Lecture de la base.** Grafana et l'exportateur lisent la base par un rôle `supervision`
    en lecture seule, limité aux tables métier (`db/roles/supervision.sql`). Ils n'ont
    jamais accès à `app_user`, aux jetons ni à l'audit.
- **Alertes.**
  - Neuf règles couvrent l'API, la base, l'hôte et les cibles, chacune avec un cas de test
    joué par `promtool test rules` en CI.
  - Alertmanager les envoie par courriel à Mailpit, le seul SMTP de la stack.
- **Dérive du modèle.** Elle s'affiche dans Grafana par une lecture SQL de `drift_report`.
  L'ADR 0013 a écarté une jauge Prometheus calculée par un traitement par lot, pas la lecture
  de sa table.

## Alternatives écartées

| Écartée | Raison |
|---|---|
| Supervision démarrée dans les deux environnements | Double la mémoire consommée sur une VM déjà serrée, pour des tableaux de recette que personne ne regarde. |
| Une pile de supervision partagée, troisième projet Compose | Elle devrait rejoindre les réseaux des deux projets, par des réseaux externes à déclarer sur la VM : plus de pièces, et un couplage entre environnements que l'ADR 0009 évite. |
| Publier Grafana derrière le proxy | Une interface d'administration de plus exposée au réseau de l'école, et un pas de plus vers une publication accidentelle de `/metrics`. |
| Grafana avec le compte applicatif de la base | Le compte applicatif écrit partout, y compris dans `app_user`. Une requête libre dans Grafana y aurait accès. |
| Une jauge de fraîcheur des relevés calculée par l'API au moment du scrape | Une requête SQL dans un collecteur synchrone, à chaque scrape. La même information se lit directement dans TimescaleDB depuis Grafana. |

## Conséquences

- **Secrets.** `.env.example` gagne `COMPOSE_PROFILES`, `APP_METRICS_TOKEN`,
  `GRAFANA_ADMIN_PASSWORD`, `SUPERVISION_DB_PASSWORD` et les ports.
  `scripts/provision-host.sh` génère ces secrets pour un nouvel environnement. Le `.env` d'un
  environnement déjà provisionné n'est jamais réécrit : il faut les y ajouter à la main.
  `make stack-up` refuse de démarrer si le profil est actif et qu'un secret manque.
- **Instrumentation.** L'API ne compte plus les sondes de santé dans ses métriques, et chaque
  application a son propre registre Prometheus.
- **cAdvisor tourne en `privileged`**, avec des montages en lecture seule et sans port publié.
  C'est le prix de la mémoire par conteneur, l'indicateur qui compte le plus sur une VM partagée.
- **Données non couvertes.** L'ingestion et les DAG Airflow n'ont pas encore de métriques
  (StatsD ou OpenTelemetry). Le tableau « Données » les supplée en lisant `reading`.
