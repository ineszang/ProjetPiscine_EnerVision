# 0009 - Deux environnements sur la VM ENI, un projet Compose chacun, déployés par un runner auto-hébergé

- Statut : accepté
- Date : 2026-09-21
- Complété par : [ADR 0017](0017-environnement-dev-a-la-demande.md), troisième environnement `dev`
- Note du 24/09 : l'approbation annoncée avant la production n'a jamais été activée. L'environnement GitHub `prod` n'accepte que `main`, sans relecteur requis.

## Contexte

La grille note EC03 à EC06 sur ce qui est déployé et fonctionnel au J10. Au 21/09, rien ne
l'est : la CI s'arrête au merge (issue #21), la topologie Compose avec reverse proxy
([ADR 0007](0007-terminaison-tls-et-reverse-proxy-nginx.md)) n'a jamais quitté le poste, et le
module Terraform k3s n'a jamais été appliqué. L'école met à disposition une seule VM,
`eadl-2025-nantes-g3`, sur une adresse privée que les runners hébergés par GitHub ne joignent
pas, sans DNS public.

Il faut deux environnements, recette et production, parce que la stratégie de branches en a
déjà deux, `dev` et `main`, et qu'un déploiement direct en production à chaque merge sur `dev`
n'est pas défendable.

La branche `feat/deploy` tentait de déployer par provisioners Terraform : nginx système et copie
du build Angular. La revue postée sur #21 relève huit points bloquants, dont des racines `rec`
et `prod` qui ne passent pas `terraform validate`.

## Décision

**Un projet Docker Compose par environnement, sur la même machine.** Deux clones du dépôt,
`/srv/enervision/rec` sur `dev` et `/srv/enervision/prod` sur `main`, chacun avec son `.env` et
son `COMPOSE_PROJECT_NAME`. Le nom de projet préfixe volumes, réseau et conteneurs : les deux
stacks ne partagent rien.

**Les ports du proxy et l'origine publique deviennent des variables** de
`docker-compose.prod.yml`. La production garde 80 et 443. La recette publie 8443 et ramène sa
redirection HTTP sur la boucle locale, faute de quoi elle renverrait vers la production. Base,
Mailpit et Airflow restent sur `127.0.0.1`, décalés d'un port.

**Deux noms d'hôte**, `enervision.local` et `rec.enervision.local`, sur la même IP. Le cookie de
rafraîchissement est posé par hôte, pas par port : un seul nom ferait se déconnecter la
production à chaque connexion en recette.

**Un runner GitHub Actions auto-hébergé sur la VM** exécute `deploy.yml` : un `push` sur `dev`
déploie la recette, un `push` sur `main` déploie la production après approbation dans
l'environnement GitHub `prod`. Le job aligne le clone sur la branche puis lance `make stack-up`.
Les images sont construites sur la machine.

**Les secrets vivent dans le `.env` de chaque dossier**, générés sur la machine par
`scripts/provision-host.sh`, jamais dans git ni dans GitHub. Le runner n'a besoin d'aucun
secret.

## Alternatives écartées

- **k3s avec un namespace par environnement** : le cluster serait vide, sans manifeste, sans
  registre, sans stockage persistant. C'est la cible de `10-infra.md`, pas celle de la semaine.
- **Provisioners Terraform de `feat/deploy`** : voir la revue sur #21. Terraform reste l'outil
  de provisionnement de la machine, pas de livraison applicative.
- **Deux machines**, VM Proxmox et VM Azure ENI : une deuxième infrastructure à justifier devant
  le jury et à provisionner, pour un bénéfice nul sur la grille.
- **Un seul proxy frontal routant par nom d'hôte vers les deux stacks** : des URL sans port,
  mais le proxy devrait joindre deux réseaux Compose où les services portent les mêmes noms.
  La complexité dépasse le gain.
- **Images publiées sur GHCR et déployées par digest** : la bonne pratique, remise à plus tard.
  Un registre à authentifier sur la machine, alors que le runner y construit déjà.

## Conséquences

- Deux TimescaleDB sur une machine de 8 Go : sans réglage, chacune se réserverait 25 % de la
  RAM au premier démarrage. L'overlay fixe `TS_TUNE_MEMORY` à 2 Go et `TS_TUNE_NUM_CPUS` à 2 par
  base. Airflow 3 n'a rien à régler de ce côté : son api-server lance un seul worker par défaut,
  là où le webserver d'Airflow 2 en lançait quatre. La montée à 32 Go prévue par les consignes
  est à demander.
- Un runner auto-hébergé sur un dépôt public exécute le code qu'on lui envoie. `deploy.yml` ne
  se déclenche jamais sur `pull_request`, le runner tourne sous un utilisateur dédié, et le
  dépôt doit exiger une approbation pour les workflows des PR externes.
- Les deux environnements construisent leurs images séparément à partir du même commit : ce qui
  tourne en production a été construit deux fois, pas promu. Le passage à GHCR lèvera cette
  limite.
- Le `make stack-up` du runner reconstruit l'image Airflow, qui copie `ml/` et `apps/backend/`,
  à chaque push : plusieurs minutes par déploiement, acceptable pour la cadence du projet.
- `environments/prod` de Terraform reste vide. Le provisionnement de la machine est porté par
  `scripts/provision-host.sh`, que Terraform pourra appeler par `remote-exec` le jour où une
  racine visant la VM existera. Cette racine existe depuis l'[ADR 0010](0010-terraform-provisionne-github-actions-deploie.md),
  sous le nom `environments/vm-eni`, et `environments/prod` a disparu avec elle.
- L'image frontend quitte `dhi.io/nginx`, registre authentifié dont personne n'a l'accès, pour
  `nginx:1.28-alpine`, la même image que le proxy. Elle n'avait jamais été construite.
