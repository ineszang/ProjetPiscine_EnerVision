# Scripts

Outillage local du monorepo. Les taches courantes passent par le `Makefile` racine.

## dast-token.sh

Prépare le scan DAST (`.github/workflows/dast.yml`) : sur une API déjà démarrée, crée un compte
`lecteur` jetable, lui fait passer le changement de mot de passe obligatoire et écrit son jeton
d'accès sur la sortie standard. À lancer depuis `apps/backend`, contre une base **jetable** (il y
crée deux comptes) : `BASE_URL=http://localhost:8000 ../../scripts/dast-token.sh`. Nécessite `curl`,
`jq` et `openssl`.

## coffre-luks.sh

Pose un coffre LUKS2 dans un fichier image creux et bind-monte `/var/lib/docker/volumes` depuis ce
coffre : les volumes des trois environnements de la VM sont chiffrés au repos sans toucher aux
fichiers Compose (issue #42, [ADR 0020](../docs/adr/0020-chiffrement-au-repos-coffre-luks-et-sse-c.md)).
Rejouable, en root sur la VM : `COFFRE_TAILLE=30G COFFRE_MIGRER=1 bash scripts/coffre-luks.sh`. Sans
`COFFRE_MIGRER=1`, le coffre est préparé mais les volumes existants ne sont pas déplacés : la
migration arrête Docker le temps de la copie. Variables : `COFFRE_IMAGE`, `COFFRE_CLE`,
`COFFRE_MONTAGE`, `COFFRE_TAILLE`. La clé est à sauvegarder hors de la VM : perdue, tout est perdu.
Le script refuse de démarrer dans un conteneur LXC (`systemd-detect-virt`) ou sans device-mapper :
c'est le cas de la machine ENI, où le chiffrement du disque relève de l'hôte Proxmox.

## provision-host.sh

Prépare la machine et ses trois environnements, `prod` sur `main`, `rec` et `dev` sur `dev`
([ADR 0009](../docs/adr/0009-deux-environnements-compose-sur-la-vm-eni.md),
[ADR 0017](../docs/adr/0017-environnement-dev-a-la-demande.md)), sans démarrer aucune stack. Pour
chacun, sous `RACINE` (`/srv/enervision` par défaut) : un clone du dépôt, un `.env` en `600` dont
les secrets sont générés sur place et jamais réécrits s'ils existent, l'adressage réaligné, un
certificat Let's Encrypt par DNS-01 si le jeton dynv6 est dans `RACINE/dns.token` (auto-signé
sinon). Lancé en root avec `PROPRIETAIRE`, il pose aussi la tâche cron de renouvellement et donne
les dossiers au compte du runner. Joué par Terraform (`infra/terraform/environments/vm-eni`) ou à
la main : `PROPRIETAIRE=<utilisateur du runner> bash scripts/provision-host.sh`.
Rejouable. Variables : `REPO_URL`, `RACINE`, `DOMAINE`, `PUBLIC_IP`, `PROPRIETAIRE`.

## tls-selfsigned.sh

Écrit un certificat auto-signé dans `infra/proxy/tls/` (`fullchain.pem`, `privkey.pem`), là où
nginx lit toujours ses certificats, quel que soit le mode d'obtention. Sert au poste de
développement et aux tests e2e ; sur la machine, il ne reste en place que si Let's Encrypt échoue.
`make tls-selfsigned PUBLIC_HOST=enervision.local`, `FORCE=1` pour écraser. Variables :
`PUBLIC_HOST`, `PUBLIC_IP` (ajoutée au certificat), `TLS_DAYS` (365 par défaut).

## comptes-test.sh

Réservé à une base **jetable** (CI, e2e, charge sur le poste) : crée un administrateur par la CLI
du backend, puis un lecteur et un opérateur, leur fait passer le changement de mot de passe
obligatoire, et écrit leurs identifiants en JSON dans `COMPTES_FICHIER`. Appelé par `e2e.yml` et
par `make e2e-prepare`. Variables : `BASE_URL` (`http://localhost:8000` par défaut),
`COMPTES_FICHIER` (requis), `APP_CLI`, `ADMIN_SUPPLEMENTAIRE=1` pour la base du poste, qui a déjà
un administrateur. Nécessite `curl`, `jq` et `openssl`.
