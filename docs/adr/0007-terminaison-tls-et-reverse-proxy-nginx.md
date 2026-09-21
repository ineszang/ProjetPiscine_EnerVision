# 0007 - Terminaison TLS par un reverse proxy Nginx, en Docker Compose

- Statut : accepté
- Date : 2026-09-21

## Contexte

Quatre documents désignaient le même trou. `10-infra.md` ouvrait ses questions par « Quel ingress
remplace Traefik, et qui termine le TLS ». `00-vue-ensemble.md` rangeait « TLS, HSTS et CSP » dans
« Absent, et assumé ». `owasp-traceabilite.md` laissait la ligne API8 transport ouverte.
`31-contrat-authentification.md` listait deux corrections « à faire avant la démonstration » :
servir le SPA et l'API sous la même origine, et servir en HTTPS.

Ce n'est pas un durcissement facultatif, c'est une condition de fonctionnement. Les deux fichiers
`apps/frontend/src/environments/environment*.ts` portent `apiUrl: '/api/v1'`, en relatif. En
développement, `proxy.conf.json` route `/api` vers l'API. Une fois en conteneur, plus rien ne le
fait : l'application déployée ne peut pas appeler son API. Et le cookie de rafraîchissement prend
le préfixe `__Secure-` dès que `APP_ENV` sort de `local`, donc sans HTTPS il n'est jamais posé et
l'authentification ne tient pas au rechargement de page.

La contrainte qui cadre tout le reste : **aucun nom de domaine public n'existe**. La cible
documentée est le serveur on-premise de l'école, `ssh_host = "10.0.0.10"` dans le
`terraform.tfvars.example`. Sur une adresse privée, le défi HTTP-01 de Let's Encrypt ne peut pas
aboutir, faute de DNS public et de port 80 entrant.

## Décision

**Un service `proxy` dans Docker Compose**, image officielle `nginx:1.28-alpine`, seul composant à
publier des ports sur la machine : 80 et 443. Backend et frontend ne sont plus publiés du tout, la
base et l'interface Mailpit sont ramenées sur la boucle locale. La stack complète est décrite par
l'overlay `docker-compose.prod.yml`, le `docker-compose.yml` restant la boucle de développement.

**Le SPA et l'API sont servis sous la même origine** : `/` vers le conteneur frontend, `/api/` vers
l'API en préservant le préfixe `/api/v1`. Le CORS cesse d'être un mécanisme de production et
redevient ce qu'il est, un filet pour les appels croisés qui ne devraient plus exister.

**nginx lit toujours les deux mêmes fichiers**, `/etc/nginx/tls/fullchain.pem` et `privkey.pem`.
Seule leur fabrication varie : un script `openssl` pour la démonstration, le `--deploy-hook` de
certbot quand un domaine existera. La configuration nginx ne connaît pas la différence et n'aura
pas à changer le jour de la bascule.

**Le proxy pose HSTS et CSP**, que l'application refuse de poser. Ce refus est verrouillé par
`tests/api/test_hardening.py::test_the_application_never_sets_hsts_itself` : l'application ne peut
pas savoir si elle est jointe en HTTPS, le terminateur, si.

## Pourquoi Compose et pas l'ingress k3s

Le module `infra/terraform/modules/k3s/` installe un cluster et rien d'autre. Il ne déclare que le
provider `null`, aucun namespace, aucun déploiement, aucun service, aucun ingress, et il n'a jamais
été appliqué. Passer par un ingress supposait d'abord de combler tout ce qui manque entre les deux
topologies : un registre d'images alimenté, des manifestes pour le front, l'API et la base, un
stockage persistant pour PostgreSQL. C'est le chantier que `10-infra.md` nomme « le trou entre les
deux topologies », et il ne tient pas dans le jalon.

Compose, lui, fait déjà tourner les quatre services sur un réseau commun. Le proxy y entre comme un
cinquième service, sans rien déplacer. La décision de désactiver Traefik reste valable : le choix
d'ingress n'est pas tranché ici, il est repoussé avec le reste de la bascule Kubernetes.

## Ce que le proxy n'expose pas, et pourquoi c'est structurel

`/docs`, `/redoc`, `/openapi.json`, `/static` et `/metrics` sont montés par l'API **à la racine**,
pas sous le préfixe `/api`. Avec un routage où seul `/api/` part vers l'API, ils tombent dans
`location /`, donc sur le SPA, donc hors d'atteinte publique. Aucune règle de blocage n'est
nécessaire, et il n'y en a pas : le jour où quelqu'un routera la racine vers l'API pour « réparer »
Swagger, il publiera les métriques avec.

## Conséquences

- `APP_ENV`, `APP_DEBUG`, `APP_CORS_ORIGINS`, `APP_TRUST_PROXY_HEADERS` et le TLS changent
  ensemble, dans le même fichier. Hors `local`, la configuration refuse de démarrer sans origine
  CORS, et le cookie devient `__Secure-ev_refresh`.
- `APP_TRUST_PROXY_HEADERS` passe à vrai, et le proxy écrit `X-Forwarded-For` avec
  `$proxy_add_x_forwarded_for`, qui ajoute l'IP réelle en fin de chaîne. C'est exactement ce que
  lit `get_client_ip()`. Toute autre forme ferait compter la limitation de débit par IP sur l'IP
  du proxy, c'est-à-dire globalement.
- Une limitation de débit au frontal existe désormais, distincte de celle de l'application : 20
  requêtes par seconde sur l'API, 30 par minute sur `/api/v1/auth/`.
- La ligne API8 transport de `owasp-traceabilite.md` se referme.
- **Let's Encrypt n'est pas prouvé.** Le chemin ACME est livré, monté et documenté ; il n'a pas
  été exercé faute de domaine. Le certificat de démonstration est auto-signé, le navigateur
  avertit, et c'est la situation réelle du projet, pas un raccourci.
- Le proxy résout ses cibles par le résolveur interne de Docker plutôt que par un bloc `upstream`,
  sans quoi recréer le seul conteneur backend suffirait à produire des 502 jusqu'au rechargement.

## Alternatives écartées

- **Ingress k3s avec cert-manager** : la bonne cible, et elle reste la cible. Elle suppose un
  registre et des manifestes qui n'existent pas, à quatre jours du rendu.
- **Étendre le `nginx.conf` du conteneur frontend** avec un `location /api` et l'écoute TLS :
  moins de pièces, mais les certificats entrent dans l'image du front et tout rebuild du front
  redéploie le terminateur TLS. La séparation des cycles de vie vaut le conteneur supplémentaire.
- **Traefik ou Caddy**, qui automatisent ACME : ils déplacent le problème sans le résoudre, le
  défi HTTP-01 échouant pour la même raison. Et l'issue nomme Nginx.
- **Let's Encrypt par défi DNS-01** : fonctionne derrière une IP privée, mais exige un domaine
  possédé et un jeton d'API chez le fournisseur DNS. Rouvrable sans rien changer à la
  configuration nginx le jour où ces deux éléments existent.
- **Un `Dockerfile` de proxy** : inutile, la configuration est montée en volume. Cela évite aussi
  la dépendance à un registre authentifié, piège déjà présent dans `apps/frontend/Dockerfile`.
