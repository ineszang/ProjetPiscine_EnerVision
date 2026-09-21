# Reverse proxy

Terminaison TLS et routage de la stack déployée. Seul composant publié sur le réseau : il
écoute en 80 et 443, et rien d'autre ne sort du réseau Compose.

- `nginx.conf` : bloc `http`, journalisation, compression, zones de limitation de débit.
- `conf.d/enervision.conf` : redirection 80 vers 443, terminaison TLS, en-têtes de sécurité,
  routage.
- `tls/` : les deux fichiers que nginx lit, `fullchain.pem` et `privkey.pem`. Ignorés par git.
- `acme-deploy-hook.sh` : recopie le résultat de certbot dans `tls/`.

Pas de `Dockerfile` : l'image officielle `nginx:1.28-alpine` est utilisée telle quelle et la
configuration est montée en volume par `docker-compose.prod.yml`.

L'overlay emploie les marqueurs `!override` et `!reset`, qui demandent **Docker Compose 2.24.4
ou plus récent**. Sur une version antérieure, la fusion échoue au lieu de dépublier les ports.

## Routage

| Chemin | Destination | Remarque |
|---|---|---|
| `/.well-known/acme-challenge/` | `/var/www/certbot` sur le port 80 | Seul chemin non redirigé vers HTTPS |
| `/api/v1/auth/` + `login`, `password`, `forgot-password`, `reset-password` | `backend:8000` | Zone resserrée, 30 requêtes par minute |
| `/api/` | `backend:8000` | Préfixe `/api/v1` préservé tel quel, 20 requêtes par seconde |
| `/` | `frontend:3000` | Le SPA, qui renvoie `index.html` sur les routes inconnues |

La zone resserrée ne couvre que les routes qui vérifient un secret. `/auth/me` et `/auth/refresh`
partent à chaque chargement de page et restent dans la zone générale : derrière un NAT, où une
seule adresse porte tous les postes, les y soumettre aurait produit des 429 en usage normal.

L'interface Airflow, celle de Mailpit et la base ne passent pas par le proxy : l'overlay les
ramène sur `127.0.0.1`, donc joignables par tunnel SSH et pas autrement. Les publier derrière le
proxy demanderait une authentification propre, qui n'est pas la leur.

`/docs`, `/redoc`, `/openapi.json`, `/static` et `/metrics` sont montés par l'API **à la racine**,
pas sous `/api`. Ils tombent donc dans `location /`, donc sur le SPA : ils ne sont pas joignables
depuis l'extérieur, sans qu'aucune règle de blocage ait à être écrite. Y toucher, c'est les
exposer.

## Certificat : deux modes, un seul emplacement

nginx lit toujours `tls/fullchain.pem` et `tls/privkey.pem`. Seule leur fabrication change, la
configuration n'a jamais à bouger.

### Démonstration, certificat auto-signé

```bash
make tls-selfsigned PUBLIC_HOST=enervision.local
make stack-up
```

Le navigateur avertira d'un émetteur inconnu : c'est attendu, et c'est le seul mode exploitable
tant que la machine cible n'a pas de nom de domaine public.

### Let's Encrypt

Le défi HTTP-01 exige un nom de domaine **résolvable publiquement** et le port 80 joignable
depuis Internet. La cible documentée aujourd'hui (`ssh_host = "10.0.0.10"`, serveur de l'école)
ne remplit ni l'une ni l'autre condition : le chemin ci-dessous est livré et documenté, il n'a
pas été exercé.

```bash
make stack-up                                     # nginx doit tourner pour servir le défi
make tls-acme PUBLIC_HOST=enervision.fr ACME_EMAIL=ops@enervision.fr
```

Renouvellement, à passer en tâche planifiée sur la machine :

```cron
17 3 * * * cd /srv/enervision && make tls-renew >> /var/log/enervision-tls.log 2>&1
```

Pour un domaine sans port 80 entrant, le défi DNS-01 est l'alternative : elle demande un
greffon certbot propre au fournisseur DNS et un jeton d'API, hors périmètre à ce jour.

## Vérifier la configuration sans démarrer la stack

`nginx -t` charge les certificats : `tls/` doit être rempli, par `make tls-selfsigned` au besoin.

```bash
docker run --rm \
  -v "$PWD/infra/proxy/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$PWD/infra/proxy/conf.d:/etc/nginx/conf.d:ro" \
  -v "$PWD/infra/proxy/tls:/etc/nginx/tls:ro" \
  nginx:1.28-alpine nginx -t
```

Monter `infra/proxy/` entier sur `/etc/nginx` échouerait : `mime.types` vient de l'image.
