# EnerVision · Recette et production sur la VM ENI, aujourd'hui

État au lundi 21 septembre 2026, 15h. Cible : deux environnements qui tournent sur la VM
`eadl-2025-nantes-g3` (`<IP-VM-G3>`) avant vendredi 25/09 9h, déployés automatiquement depuis
GitHub. Ce document donne la solution retenue, ce qu'elle change dans le dépôt, et le déroulé de
l'après-midi avec qui fait quoi.

## 1. La décision en une phrase

**Deux projets Docker Compose sur la même VM, un par environnement, déployés par un runner GitHub
Actions installé sur la VM.** `dev` alimente la recette, `main` alimente la production. Terraform
reste ce qu'il est : le module k3s, cible à terme, non utilisé pour cette mise en ligne.

| | Recette (`rec`) | Production (`prod`) |
|---|---|---|
| Branche | `dev` | `main` |
| Environnement GitHub | `rec` (créé ce midi) | `prod` (créé ce midi) |
| Dossier sur la VM | `/srv/enervision/rec` | `/srv/enervision/prod` |
| Projet Compose | `enervision-rec` | `enervision-prod` |
| URL | `https://rec.enervision.local:8443` | `https://enervision.local` |
| Proxy HTTPS | `8443` | `443` |
| Proxy HTTP (redirection) | `127.0.0.1:8081`, inutilisé | `80` |
| PostgreSQL, Mailpit, Airflow | `127.0.0.1` : `5434`, `8026`, `8082` | `127.0.0.1` : `5433`, `8025`, `8080` |
| Certificat | auto-signé, SAN `rec.enervision.local` | auto-signé, SAN `enervision.local` |
| Déclenchement | chaque push sur `dev` | push sur `main`, après approbation dans GitHub |

Les deux noms d'hôte pointent sur la même IP. Deux lignes dans le `/etc/hosts` des postes de
l'équipe suffisent. Deux noms distincts sont indispensables : le cookie de rafraîchissement
`__Secure-ev_refresh` est posé par hôte, pas par port, et un seul nom ferait se déconnecter la
prod à chaque connexion sur la recette.

## 2. Pourquoi c'est la solution la plus simple

- **Tout existe déjà.** L'overlay `docker-compose.prod.yml`, le proxy Nginx TLS, les scripts de
  certificat et `make stack-up` sont écrits et validés sur poste (PR #117, ADR 0007). Il ne
  manque que quatre variables pour que deux instances cohabitent sur une machine.
- **Un projet Compose isole tout.** Volumes, réseau, noms de conteneurs sont préfixés par le nom
  du projet. Casser la recette ne touche pas la prod, ce qui est la raison d'être d'une recette.
- **Le runner sur la VM est la seule façon d'atteindre une IP privée d'école depuis GitHub.** Les
  runners hébergés par GitHub ne voient pas `<IP-VM-G3>`. Le runner se connecte en sortie
  vers GitHub, aucun port entrant n'est nécessaire. C'était le choix 16 du dossier EC01 : il
  redevient tenu.
- **La promotion existe déjà dans la stratégie de branches** : `dev` puis `main` par PR. Le
  même code est déployé en recette, puis en production, sans troisième mécanisme.

Ce qu'on écarte, et pourquoi :

| Piste | Pourquoi pas cette semaine |
|---|---|
| k3s avec deux namespaces | Le cluster serait vide : aucun manifeste, aucun registre d'images, aucun stockage persistant. Trois jours de travail sans valeur visible au J10 |
| Terraform de `feat/deploy` (nginx système + copie de fichiers) | Revue postée sur l'issue #21 : huit points bloquants, `rec` et `prod` ne passent pas `terraform validate`. On abandonne cette voie |
| Azure ENI pour la prod | Deuxième infrastructure à provisionner, choix à justifier devant le jury (document 03), et rien n'est prêt côté Azure |
| Images publiées sur GHCR | Meilleure pratique, mais un registre de plus à authentifier sur la VM. Les images se construisent sur la VM, où le runner tourne déjà. À faire ensuite, issue à ouvrir |
| Let's Encrypt | Aucun domaine public ne résout vers la VM. Auto-signé assumé, chemin ACME déjà câblé |

## 3. Ce qui change dans le dépôt (une PR vers `dev`)

| Fichier | Changement | Raison |
|---|---|---|
| `apps/frontend/Dockerfile` | `FROM nginx:1.28-alpine` à la place de `dhi.io/nginx:...` | Le registre Docker Hardened Images demande une authentification. L'image frontend n'a jamais été construite, sur aucun poste : c'est le premier point où `make stack-up` échouerait sur la VM |
| `docker-compose.prod.yml` | Ports du proxy en variables `PROXY_HTTP_PORT` et `PROXY_HTTPS_PORT`. Origine publique `PUBLIC_ORIGIN` pour CORS et le lien de réinitialisation. `TS_TUNE_MEMORY` sur la base | Deux proxys ne peuvent pas publier 80 et 443. L'origine de la recette porte un port. Deux TimescaleDB sur 8 Go se réserveraient chacune 2 Go sans réglage |
| `.env.example` | `COMPOSE_PROJECT_NAME`, les variables ci-dessus, ports de la recette en commentaire | Le `.env` de chaque dossier est la seule différence entre les deux environnements |
| `.github/workflows/deploy.yml` | Nouveau. `on: push` sur `dev` et `main`, `runs-on: [self-hosted, eni-g3]`, `environment: rec` ou `prod`, puis `git reset --hard origin/<branche>` et `make stack-up` dans le dossier de l'environnement | Le D de CI/CD, issue #21 |
| `scripts/provision-host.sh` | Nouveau. Vérifie Docker et Compose 2.24.4 ou plus, crée `/srv/enervision/{rec,prod}`, clone les deux branches | Rejouable, et réutilisable par Terraform plus tard |
| `docs/adr/0009-...md`, `10-infra.md`, `50-cicd.md`, `infra/proxy/README.md` | Décision, vue infra, vue CI/CD, tableau des ports | Règle du dépôt : la vue change dans la même PR que le composant |

Ce qui ne change pas : `docker-compose.yml`, la configuration Nginx, `infra/terraform`.

## 4. Déroulé de l'après-midi

| # | Qui | Quoi | Durée |
|---|---|---|---|
| 1 | **ineszang** (seule admin du dépôt) | Environnement `prod` : branche autorisée `main`, un relecteur requis. Environnement `rec` : branche `dev`. Settings > Actions : « Require approval for all outside collaborators ». Générer le jeton d'enregistrement du runner (Settings > Actions > Runners > New self-hosted runner, Linux x64) et le transmettre à Johan | 10 min |
| 2 | **Johan** | Déposer sa clé sur la VM : `ssh-copy-id -i ~/.ssh/id_ed25519.pub root@<IP-VM-G3>`, mot de passe du compte administrateur local des postes de l'école | 2 min |
| 3 | Johan + Claude | **Fait à 15h** : branche locale `feat/deploy-rec-prod` avec tous les changements du §3, image frontend reconstruite avec succès, fusion Compose vérifiée pour les deux environnements. Reste : commit, push, PR vers `dev` | fait |
| 4 | Claude, par SSH | `scripts/provision-host.sh` sur la VM. Écrire les deux `.env` (secrets générés sur la VM, jamais dans git). Certificats : `PUBLIC_HOST=rec.enervision.local PUBLIC_IP=<IP-VM-G3> make tls-selfsigned` dans `rec`, idem avec `enervision.local` dans `prod`. Puis `make stack-up` dans chaque dossier | 20 min plus la construction des images |
| 5 | Johan, sur la VM | Installer le runner sous un utilisateur non-root membre du groupe `docker`, label `eni-g3`, en service systemd (`./config.sh --unattended --labels eni-g3`, `sudo ./svc.sh install && sudo ./svc.sh start`) | 10 min |
| 6 | Équipe | Merger la PR dans `dev` : la recette se redéploie seule. Ouvrir la PR `dev` vers `main` : la prod se déploie après approbation dans l'onglet Environments | 15 min |
| 7 | Tous | Vérifier depuis un poste de l'équipe, `/etc/hosts` renseigné : connexion, tableau de bord, Airflow par tunnel SSH | 15 min |

Contrôle en fin de chaîne, depuis la VM :

```bash
curl -k https://localhost/api/v1/health/ready          # prod
curl -k https://localhost:8443/api/v1/health/ready     # rec
docker compose -p enervision-prod ps
docker compose -p enervision-rec ps
```

## 5. Ce qui peut faire échouer la journée, et la parade

| Risque | Parade |
|---|---|
| **8 Go de RAM pour deux stacks complètes** (deux Airflow, deux TimescaleDB, deux API) | Demander dès maintenant le passage à 32 Go, prévu par les consignes. En attendant : `TS_TUNE_MEMORY=2GB` et deux workers gunicorn pour Airflow. Si la RAM ne suit pas, démarrer la recette sans Airflow (`docker compose up -d --scale airflow-webserver=0 --scale airflow-scheduler=0`) |
| **Compose trop ancien sur la VM** (les marqueurs `!override` et `!reset` exigent 2.24.4) | `docker compose version` en premier. Sinon installer le paquet `docker-compose-plugin` depuis le dépôt Docker |
| **Pas de sortie Internet depuis la VM** | `curl -sI https://github.com` et `docker pull hello-world` avant tout. Sans sortie, ni construction d'image ni runner : déploiement manuel par `scp` d'images, plan B lourd |
| **Runner auto-hébergé sur un dépôt public** | Le workflow de déploiement ne s'exécute que sur `push` vers `dev` et `main`, jamais sur `pull_request`. Réglage d'approbation des PR externes (étape 1). Runner sous un utilisateur dédié, jamais root |
| **Premier démarrage avec un volume `pgdata` vide** | C'est le cas nominal sur la VM : `db/init` crée les bases `enervision`, `enervision_test` et `airflow`. Ne pas restaurer un volume de poste |
| **Le jury accepte mal un certificat auto-signé** | Dire pourquoi avant qu'on le demande : aucun DNS public, ACME câblé et documenté, ADR 0007. Un clic « continuer » dans le navigateur |
| **Conflit avec `feat/deploy`** (ineszang y a mergé `dev` à 14h06) | Partager ce document avant de pousser. La PR remplace `feat/deploy`, elle ne s'y ajoute pas |

## 6. Ce que ça donne pour la grille

- **EC03, CI/CD** : la chaîne ne s'arrête plus au merge. Deux environnements, déploiement
  automatique en recette, promotion approuvée en production, journal des déploiements dans
  l'onglet Environments de GitHub.
- **EC04, cloud et sécurisation** : une application déployée et fonctionnelle, une seule surface
  exposée par environnement, secrets hors de git et hors de GitHub, base et Airflow joignables
  uniquement par tunnel SSH.
- **Dossier EC01** : le choix 16 (runner auto-hébergé, déploiement automatique) passe de « non
  fait » à « tenu ». Le choix 12 (Ansible) reste non fait, et la réponse est prête : le
  durcissement de la machine n'est pas automatisé, le script de provisionnement en est la
  première brique, Terraform pourra l'appeler.

## 7. Après vendredi, si on continue

Dans l'ordre de valeur : images construites une fois en CI et publiées sur GHCR, puis déployées
par digest (vraie promotion d'artefact). Racine Terraform `environments/eni-g3` qui provisionne
la machine et le runner à partir du script. Sauvegarde de `pgdata` par `pg_dump` planifié.
Monitoring (issue #26). Et seulement ensuite la bascule k3s, si elle garde un sens.
