# Traçabilité OWASP

Ce document remplace la revendication « couverture OWASP Top 10 et OWASP API Security Top 10 »
de la NFR4 du dossier EC01. Cette formulation est indéfendable telle quelle : vingt items, non
vérifiables en deux semaines, et « montrez-moi votre couverture de A04 Insecure Design » n'a pas
de réponse honnête.

Ce qui est défendable, c'est une ligne par contrôle réellement implémenté, l'item qu'il adresse,
et une section qui dit ce qui n'est pas couvert et pourquoi.

Statut : `Fait` pour le périmètre authentification et autorisation. `GET /sites` et
`GET /recommendations`, chacune avec sa route de détail, sont les premiers endpoints métier, en
lecture seule ; plusieurs lignes resteront à compléter une fois les endpoints d'écriture posés.

## Contrôles en place

| Contrôle | Où | Item adressé |
|---|---|---|
| Interdire par défaut, liste blanche de routes publiques vérifiée par un test qui appelle réellement chaque route | `tests/api/test_route_protection.py` | API5 Broken Function Level Authorization, A01 Broken Access Control |
| RBAC à trois rôles ordonnés, décision prise sur la ligne en base et jamais sur le claim | `app/api/deps.py` | A01, API5 |
| Révocation immédiate : compte relu à chaque requête, `credentials_changed_at` invalide les jetons antérieurs | `app/api/deps.py`, `app/repositories/user.py` | A01, API2 Broken Authentication |
| Argon2id m=19456 t=2 p=1, re-hachage passif quand les paramètres changent | `app/core/hashing.py` | A02 Cryptographic Failures, A07 Identification and Authentication Failures |
| Message et temps de réponse identiques quelle que soit la cause de l'échec, haché leurre sur adresse inconnue | `app/services/auth.py` | A07, API2 |
| Limitation de débit à fenêtre glissante sur trois clés, évaluée avant le hachage | `app/services/auth.py`, `app/repositories/login_attempt.py` | A07, API4 Unrestricted Resource Consumption |
| `GET /readings` : fenêtre temporelle plafonnée à 90 jours (24h par défaut), `limit`/`offset` plafonné à 2000, refus `400` si la fenêtre est inversée ou trop large | `app/services/reading.py` | API4 |
| Absence de verrouillage de compte, qui serait un déni de service | ADR 0002 | API4 |
| Jeton de rafraîchissement opaque, haché en base, rotation avec détection de réutilisation | `app/services/auth.py`, `app/repositories/refresh_token.py` | A07, API2 |
| Séparation structurelle accès / rafraîchissement, impossible à confondre | ADR 0002 | API2 |
| Algorithme épinglé, `aud`, `iss` et `typ` vérifiés, `alg: none` rejeté | `app/core/security.py` | A02, API2 |
| Cookie `HttpOnly`, `Secure`, `SameSite=Strict`, `Path` restreint, suppression symétrique | `app/core/cookies.py` | A05 Security Misconfiguration |
| Vérification d'`Origin` sur les trois routes portant le cookie | `app/api/deps.py` | A01 |
| Schémas de lecture et d'écriture séparés, aucun modèle ORM en réponse | `app/schemas/user.py` | API3 Broken Object Property Level Authorization |
| Validation stricte Pydantic en entrée, mot de passe borné à 128 caractères | `app/schemas/auth.py` | A03 Injection, API4 |
| Requêtes paramétrées par SQLAlchemy, aucune concaténation SQL | `app/repositories/` | A03 |
| Réponse 422 qui ne renvoie jamais la valeur rejetée | `app/api/errors.py` | A09 Security Logging and Monitoring Failures |
| Réponse 500 générique avec identifiant de corrélation, trace côté serveur seulement | `app/api/errors.py` | A05 |
| Journal d'audit en ajout seul garanti par déclencheurs, liste blanche des clés de détail | ADR 0004, `app/repositories/audit_log.py` | A09 |
| Caviardage des jetons, empreintes, mots de passe et cookies dans les journaux | `app/core/logging.py` | A09, A02 |
| Cinq gardes de configuration qui refusent le démarrage plutôt que de dégrader silencieusement | `app/core/config.py` | A05 |
| Documentation interactive fermée hors développement, `/metrics` derrière un jeton, sonde qui ne publie plus de version | `app/main.py`, `app/api/security.py` | A05 |
| En-têtes `nosniff`, `DENY`, `no-referrer`, et `no-store` sur les routes d'authentification | `app/api/middleware.py` | A05 |
| Refus de rétrograder ou désactiver le dernier administrateur actif | `app/services/user.py` | A04 Insecure Design |
| Amorçage du premier administrateur hors dépôt, mot de passe jamais dans `argv` ni dans Git | `app/cli.py` | A02, A05 |
| Réponse de l'API Mock bornée avant écriture : timeout, plafond de sites et de mesures, bornes physiques par grandeur, recopie des seuls champs attendus | `app/etl/mock_api_import.py` | API10 Unsafe Consumption of APIs |
| CI bloquante : format, lint avec règles Bandit, typage strict, tests avec seuil de couverture | `.github/workflows/backend.yml` | A06 Vulnerable and Outdated Components |

Note sur A06 : le jeu de règles `S` de ruff, déjà actif dans `pyproject.toml`, est le portage des
règles Bandit. Ajouter Bandit à la CI serait redondant, contrairement à ce qu'annonce l'EC01.

## Non couvert, et pourquoi

| Item | État | Raison |
|---|---|---|
| **API1 Broken Object Level Authorization** | **ouvert** | Les rôles sont globaux, il n'y a pas de portée par site : `GET /sites/{site_id}` et `GET /recommendations/{recommendation_id}` répondent à tout compte `lecteur` pour n'importe quel site ou recommandation, sans vérifier une affectation compte-site qui n'existe pas encore. Un opérateur du site A pourra agir sur le site B dès que les endpoints d'écriture métier existeront. Correctif prévu : table d'affectation compte-site, contrôle d'appartenance dans la même dépendance que le contrôle de rôle. |
| **API4, lectures de séries temporelles** | **partiel** | `GET /readings` plafonne la fenêtre temporelle (90 jours) et la pagination (`limit` ≤ 2000), voir plus haut. Reste ouvert : pagination en `limit`/`offset` simple plutôt qu'en curseur (un `offset` élevé sur une fenêtre dense reste coûteux), et aucun `statement_timeout` au niveau de la connexion pour borner une requête individuelle si les plafonds au-dessus s'avéraient insuffisants. |
| **API8 Security Misconfiguration, transport** | **ouvert** | Pas de TLS, donc ni HSTS, ni cookie `Secure` réellement posé en production. Ils appartiennent au terminateur TLS, qui n'existe pas. |
| **API10 Unsafe Consumption of APIs** | **partiel, et spécifique à ce projet** | L'API Mock de l'école n'a aucune authentification, tourne en HTTP clair sur le réseau de l'école, et expose un endpoint mutatif à quiconque. Sa réponse est traitée comme une entrée hostile par `app/etl/mock_api_import.py`, son seul consommateur à ce jour : les quatre garde-fous attendus sont en place, voir la ligne correspondante plus haut. Reste ouvert : le plafond de taille s'applique après désérialisation de la réponse, borner le corps HTTP lui-même demanderait une lecture en flux ; et `APP_MOCK_API_BASE_URL` n'impose pas `https`, donc les identifiants Basic partiraient en clair sur une URL en `http`. La conséquence la plus sérieuse n'est pas la fausse alerte, c'est l'empoisonnement du jeu d'entraînement du modèle de prédiction. |
| **A08 Software and Data Integrity Failures** | **partiel** | La CI vérifie le code mais n'analyse ni les dépendances ni les images. `.terraform.lock.hcl` reste ignoré par git, ce qui contredit une chaîne d'approvisionnement maîtrisée. |
| **A10 Server-Side Request Forgery** | **sans objet aujourd'hui** | Aucune URL sortante n'est pilotée par une donnée utilisateur. Le jour où l'adresse d'une source devient un champ de configuration, il faudra une liste blanche de schémas et d'hôtes, sans suivi de redirection. |
| **Cantonnement des accès ETL et ML** | **dette assumée** | Le compte applicatif porte l'identité, le rôle PostgreSQL porterait le cantonnement. Voir ADR 0003. |
| **Non-répudiation de l'audit** | **dette assumée** | Les déclencheurs arrêtent les accidents, pas un compte détenant `ALTER TABLE`. Voir ADR 0004. |

## Ce qu'il faut répondre, et ne pas répondre

Sur A04 Insecure Design, la réponse n'est pas une case cochée mais deux décisions concrètes : le
refus du verrouillage de compte, qui aurait été un déni de service, et le refus de laisser un
administrateur se verrouiller lui-même dehors.

Sur l'audit, ne jamais prétendre que la table est inviolable : elle ne l'est pas contre un compte
qui a les droits sur la base, et c'est vrai de tout journal co-localisé avec ce qu'il journalise.

Sur l'API Mock, ne jamais répondre « c'est un mock, ce n'est pas notre périmètre ». C'est
précisément le périmètre : c'est la frontière de confiance.
