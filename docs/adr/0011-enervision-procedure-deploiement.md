# EnerVision · procédure de déploiement (22/09/2026)

Terraform provisionne la machine, GitHub Actions déploie (ADR 0010). Deux environnements Compose
sur la VM ENI `<IP-VM-G3>` : `rec` sur la branche `dev`, `prod` sur `main` (ADR 0009).

| | recette | production |
|---|---|---|
| Branche, environnement GitHub | `dev`, `rec` | `main`, `prod` |
| Dossier, projet Compose | `/srv/enervision/rec`, `enervision-rec` | `/srv/enervision/prod`, `enervision-prod` |
| URL | `https://rec.enervision.local:8443` | `https://enervision.local` |
| Proxy HTTP / HTTPS | `127.0.0.1:8081` / `8443` | `80` / `443` |
| Postgres / Mailpit / Airflow (locaux) | `5434` / `8026` / `8082` | `5433` / `8025` / `8080` |

## 0. Avant toute commande

1. **Clé SSH déposée** sur la VM : `ssh-copy-id -i ~/.ssh/id_ed25519.pub root@<IP-VM-G3>`.
   Terraform ne gère **pas** l'authentification par mot de passe (elle finirait dans le state).
2. **L'utilisateur propriétaire existe déjà** sur la VM (ex. `enervision`) : il possède
   `/srv/enervision` et fait tourner le runner. Terraform échoue tôt s'il manque, il ne le crée pas.
3. **Jeton d'enregistrement du runner** : Settings > Actions > Runners > New self-hosted runner.
   Valable 1 h, une seule inscription, créé par un administrateur du dépôt (ineszang).
4. **`main` est en retard de 64 commits** et ne porte ni `deploy.yml`, ni `provision-host.sh`, ni
   le Terraform, ni l'overlay paramétré (ports et `PUBLIC_ORIGIN` en dur). Tant que `dev` n'est pas
   remonté dans `main`, seule la recette est déployable : le clone `prod` sera préparé mais son
   `make stack-up` publierait 80/443 sans les variables, et aucun push sur `main` ne déclencherait
   de déploiement (le workflow n'y existe pas). **Remonter `dev` → `main` avant de toucher à prod.**

## 1. Provisionner la machine (depuis le poste)

```bash
cd infra/terraform/environments/vm-eni
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

`terraform.tfvars`, ignoré par git, trois valeurs à renseigner :

```hcl
proprietaire   = "enervision"   # doit exister sur la VM
runner_version = "2.330.0"      # épingler depuis github.com/actions/runner/releases
runner_token   = "..."          # jeton d'1 h, à retirer du fichier après l'apply
```

Défauts utiles : `ssh_host = "<IP-VM-G3>"`, `ssh_user = "root"`,
`ssh_private_key_path = "~/.ssh/id_ed25519"`, `racine = "/srv/enervision"`,
`runner_labels = "eni-g3"` (ciblé par `deploy.yml`), `runner_dossier = "/opt/actions-runner"`.

L'apply fait trois choses, dans cet ordre : Docker + plugin Compose et `usermod -aG docker`,
puis `scripts/provision-host.sh`, puis l'installation et l'enregistrement du runner en service.
Il ne construit aucune image et ne démarre aucun conteneur : un apply n'interrompt pas la stack.

Rejouable : un clone existant est réaligné, un `.env` présent n'est **jamais** réécrit, un
certificat présent n'est jamais régénéré. Un nouvel apply de la ressource runner redemande un
jeton frais (il expire en 1 h).

## 2. Variables d'environnement

Un `.env` par dossier, en `600`, généré sur la machine depuis `.env.example`. **Aucun secret ne
passe par git ni par GitHub** : le runner n'en reçoit aucun (seul `SONAR_TOKEN` existe côté CI).

**Générés automatiquement** : `POSTGRES_PASSWORD`, `APP_SECRET_KEY`, `AIRFLOW_FERNET_KEY`,
`AIRFLOW_API_SECRET_KEY`, `AIRFLOW_JWT_SECRET`, `AIRFLOW_ADMIN_PASSWORD`, `AIRFLOW_APP_SECRET_KEY`.

**Fixés par environnement** : `COMPOSE_PROJECT_NAME`, `PUBLIC_HOST`, `PUBLIC_ORIGIN`,
`PROXY_HTTP_PORT`, `PROXY_HTTPS_PORT`, `POSTGRES_PORT`, `MAILPIT_UI_PORT`, `AIRFLOW_PORT`.

**À renseigner à la main**, dans chaque `.env`, avant le premier démarrage :

```
APP_MOCK_API_USERNAME=...
APP_MOCK_API_PASSWORD=...
```

Garde-fou : le script refuse d'écrire un `.env` s'il reste un `change_me` hors `APP_MOCK_API_*`
(cas vécu d'une clé renommée en amont, `AIRFLOW_WEBSERVER_SECRET_KEY` sous Airflow 3).

`APP_ENV=prod` et `APP_DEBUG=false` sont en dur dans l'overlay, pas dans le `.env` : la valeur
`local` du poste reprendrait le dessus et rouvrirait `/docs` sans cookie `__Secure-`.

`TS_TUNE_MEMORY=2GB` et `TS_TUNE_NUM_CPUS=2` sont obligatoires : deux TimescaleDB sur 8 Go se
réserveraient 25 % de la RAM chacune. La montée à 32 Go est à demander.

Certificats auto-signés générés par le script (`infra/proxy/tls/`), couvrant le nom d'hôte,
`localhost` et l'IP. Let's Encrypt (`make tls-acme`, `ACME_EMAIL`) reste hors d'atteinte sans
domaine public résolvable.

## 3. Premier démarrage (manuel, une seule fois, sur la VM)

```bash
cd /srv/enervision/rec && make stack-up      # build + up + alembic upgrade head
cd /srv/enervision/prod && make stack-up     # seulement après la remontée dev → main
```

`stack-up` refuse de démarrer si le certificat manque ou ne couvre pas `PUBLIC_HOST`, et applique
les migrations : sans elles la stack démarrerait verte sur une base sans schéma.

Premier administrateur, stack démarrée, dans chaque dossier :

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
    python -m app.cli create-admin --email <adresse>
```

Données historiques : `data/raw` n'est pas dans git. Déposer les fichiers dans chaque dossier
avant de déclencher le DAG `historical_import`.

## 4. Réglages GitHub (administrateur du dépôt)

- Environnement `prod` : branche `main` seule autorisée, **approbation d'un relecteur** requise.
- Environnement `rec` : branche `dev` seule autorisée, sans approbation.
- Settings > Actions : **« Require approval for all outside collaborators »**. Un runner
  auto-hébergé sur un dépôt public exécute ce qu'on lui envoie ; `deploy.yml` ne se déclenche
  jamais sur `pull_request`, et le runner ne tourne jamais en root.

## 5. Déploiement continu, ensuite

Un push sur `dev` déploie la recette, un push sur `main` la production après approbation.
Le job (runner `eni-g3`) aligne le clone (`fetch`, `checkout`, `reset --hard`), lance
`make stack-up`, puis sonde `/api/v1/health/ready` derrière le proxy pendant 3 minutes ; en cas
d'échec il publie `ps` et les 50 dernières lignes de `backend` et `proxy`. Pas de `checkout` dans
l'espace du runner : `.env`, certificats et volumes doivent survivre d'un déploiement à l'autre.
Concurrence par branche, sans annulation.

Déclenchement manuel possible : `workflow_dispatch`.

## 6. Vérifier

```bash
curl -k https://localhost:8443/api/v1/health/ready    # recette, sur la VM
curl -k https://localhost/api/v1/health/ready         # production, sur la VM
```

Depuis un poste, ajouter à `/etc/hosts` :

```
<IP-VM-G3> enervision.local rec.enervision.local
```

Les deux noms sont obligatoires : le cookie `__Secure-ev_refresh` est posé par hôte et non par
port ; un seul nom déconnecterait la production à chaque connexion en recette.

## Pièges à connaître

- Compose **2.24.4 minimum** : l'overlay emploie `!override` et `!reset`, sans quoi l'API resterait
  joignable en clair à côté du proxy. Le script le vérifie.
- Le runner doit tourner sous le propriétaire de `/srv/enervision` : sinon git refuse les clones
  (propriété douteuse) et le `.env` en `600` lui échappe. Correctif :
  `PROPRIETAIRE=<utilisateur> bash scripts/provision-host.sh`.
- Chaque environnement reconstruit ses images à partir du même commit : la production n'exécute
  pas l'artefact validé en recette, mais un second build. Le passage à GHCR lèvera cette limite.
- Un `.env` perdu se régénère, mais invalide les sessions et les connexions chiffrées par Airflow :
  ils ne sont sauvegardés nulle part ailleurs.
- Retirer le runner se fait à la main, depuis les paramètres du dépôt : `terraform destroy` ne le
  désinscrit pas.

## Références dans le dépôt

`docs/adr/0009-deux-environnements-compose-sur-la-vm-eni.md`,
`docs/adr/0010-terraform-provisionne-github-actions-deploie.md`,
`docs/architecture/50-cicd.md`, `docs/architecture/10-infra.md`, `infra/README.md`,
`scripts/provision-host.sh`, `.github/workflows/deploy.yml`, `docker-compose.prod.yml`.
