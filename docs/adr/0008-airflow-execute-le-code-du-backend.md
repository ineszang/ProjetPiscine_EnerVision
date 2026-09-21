# 0008 - Airflow exécute le code du backend en sous-processus

- Statut : accepté
- Date : 2026-09-21

## Contexte

L'issue #116 demande un DAG d'alertes. Ce qu'il a à ordonnancer existe déjà et n'est pas à
réécrire : `AlertService.detect()` et ses cinq règles (#104), puis le moteur de recommandations
(#38). Les deux vivent dans `apps/backend/app/`, et
l'[ADR 0006](0006-moteur-de-regles-dans-le-backend.md) a précisément décidé qu'ils y restent parce
qu'ils s'appuient sur les repositories ORM de l'API plutôt que sur du SQL brut. Les deux
sont décrits par la documentation comme « lancés à la main ».

L'image Airflow livrée par #115 ne porte que `ml/`, dans un environnement `uv` distinct
(`/opt/ml/.venv`, Python 3.14) de celui d'Airflow lui-même (Python 3.12, contraint par
apache-airflow 2.10). Les DAGs `ml_train` et `ml_score` shellent vers cet environnement. Rien
d'équivalent n'existe pour `apps/backend` : un `BashOperator` sur
`python -m app.detection.internal_alerts` échouerait en `ModuleNotFoundError`.

## Décision

**L'image Airflow porte un troisième environnement, `/opt/backend/.venv`**, construit depuis le
`pyproject.toml`, le `uv.lock` et le paquet `app/` du backend. Le DAG `alertes` shelle vers lui
exactement comme `ml_score` shelle vers `/opt/ml/.venv`.

Trois raisons :

- **Le patron existe et vient d'être revu.** #115 a posé `BashOperator` + `uv run --no-sync` +
  `env -u VIRTUAL_ENV`, avec les tests d'intégrité qui le verrouillent. Introduire une seconde
  forme d'appel dans le même dossier `dags/` coûterait plus cher à lire qu'un second environnement
  dans le même `Dockerfile`.
- **Aucune surface réseau n'est ajoutée.** La détection n'a pas de route HTTP, contrairement à la
  génération de recommandations (`POST /recommendations/generate`, rôle `admin`). En créer une pour
  qu'Airflow l'appelle donnerait à l'ordonnanceur un compte administrateur de l'API, en plus des
  identifiants PostgreSQL complets qu'il détient déjà, et ferait dépendre la production d'alertes
  de la disponibilité du conteneur `backend`.
- **La logique reste où l'ADR 0006 l'a mise.** Le DAG n'apprend rien du domaine : ni les seuils, ni
  les cinq règles, ni les clés d'idempotence. Il ne sait que l'heure à laquelle appeler.

## Conséquences

- **Airflow reçoit une `APP_SECRET_KEY` délibérément distincte de celle de l'API.** La
  configuration du backend refuse de se construire sans elle (`app/core/config.py`), et
  `internal_alerts.main()` appelle `get_settings()` avant toute requête pour échouer tôt. Mais la
  détection ne signe ni ne vérifie aucun jeton, et Airflow permet d'exécuter du code arbitraire
  depuis son interface : un Airflow compromis ne doit pas livrer la clé de signature des JWT. D'où
  `AIRFLOW_APP_SECRET_KEY`, avec sa propre garde dans `airflow-init`.
- **`DATABASE_URL`, en dialecte asyncpg, rejoint `ML_DATABASE_URL`** dans l'environnement du
  conteneur. Le cantonnement des rôles PostgreSQL reste la dette de
  l'[ADR 0003](0003-autorisation-rbac-a-trois-roles.md), et cette décision l'alourdit d'un
  consommateur de plus.
- **La CI Airflow se déclenche sur les changements du backend.** L'image le `COPY` : sans
  `apps/backend/app/**`, `pyproject.toml` et `uv.lock` dans les déclencheurs du workflow, une
  dépendance modifiée casserait la construction sans que rien ne le signale avant le déploiement.
  En contrepartie, l'image grossit de ce que pèsent SQLAlchemy, asyncpg et pandas.
- **Aucune variable ne départage les deux environnements, et c'est voulu.** `uv` place par défaut
  le venv d'un projet dans `<projet>/.venv` : `cd /opt/ml` ou `cd /opt/backend` suffit à choisir le
  bon. L'image ne pose donc plus de `UV_PROJECT_ENVIRONMENT` global, hérité de #115 : il vaudrait
  pour les deux projets, et `uv run` dans l'un résoudrait le venv de l'autre. Le symptôme n'est pas
  une construction ratée mais un `ModuleNotFoundError` à la première tâche, d'où la vérification
  d'import sans réseau que la CI fait maintenant sur chacun des deux.
- Airflow lui-même reste étranger au domaine : ni LightGBM, ni SQLAlchemy, ni FastAPI n'entrent
  dans son interpréteur. C'est la propriété que #115 avait établie, et elle tient toujours.

## Alternatives écartées

- **Route HTTP `POST /alerts/detect` réservée `admin`, appelée par le DAG.** L'image ne bougeait
  pas, mais Airflow détenait alors un compte administrateur de l'API, la détection devenait
  tributaire du conteneur `backend`, et l'API gagnait une route d'écriture dont aucun client
  humain n'a l'usage. À rouvrir si un jour un tiers doit déclencher la détection.
- **`DockerOperator` lançant l'image du backend.** Demande la socket Docker de l'hôte dans le
  conteneur Airflow, c'est-à-dire un équivalent root sur la machine, pour un service qui permet
  déjà d'exécuter du code depuis son interface. Le provider n'est d'ailleurs pas installé.
- **Réécrire les cinq règles en SQL dans le DAG.** Contredit frontalement l'ADR 0006, duplique le
  domaine, et fait diverger les deux copies au premier changement de seuil.
- **Monter `apps/backend` en volume plutôt que le copier.** L'environnement ne serait plus figé à
  la construction, `uv` resynchroniserait au premier lancement, et la CI ne prouverait plus rien
  de ce qui tourne réellement.
