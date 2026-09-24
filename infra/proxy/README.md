# Reverse proxy

Terminaison TLS et routage de la stack déployée. Sur un poste, seul composant publié sur le
réseau : il écoute en 80 et 443, et rien d'autre ne sort du réseau Compose. Sur la VM, il
n'écoute plus que sur `127.0.0.1`, derrière le frontal SNI `infra/front`, seul composant exposé
([ADR 0018](../../docs/adr/0018-noms-publics-certificats-dns01-et-frontal-sni.md)).

- `nginx.conf` : bloc `http`, journalisation, compression, zones de limitation de débit.
- `conf.d/enervision.conf` : redirection 80 vers 443, terminaison TLS, en-têtes de sécurité,
  routage.
- `tls/` : les deux fichiers que nginx lit, `fullchain.pem` et `privkey.pem`. Ignorés par git.
- `acme-deploy-hook.sh` : recopie le résultat de certbot dans `tls/`.

Pas de `Dockerfile` : l'image officielle `nginx:1.31-alpine` est utilisée telle quelle et la
configuration est montée en volume par `docker-compose.prod.yml`.

L'overlay emploie les marqueurs `!override` et `!reset`, qui demandent **Docker Compose 2.24.4
ou plus récent**. Sur une version antérieure, la fusion échoue au lieu de dépublier les ports.

Les ports publiés sont `PROXY_HTTP_PORT`, `PROXY_HTTPS_PORT` et `PROXY_FRONT_PORT`, 80, 443 et un
port aléatoire de la boucle locale par défaut. Sur la VM, trois environnements partagent la
machine ([ADR 0009](../../docs/adr/0009-deux-environnements-compose-sur-la-vm-eni.md),
[ADR 0017](../../docs/adr/0017-environnement-dev-a-la-demande.md)) : `scripts/provision-host.sh`
place les ports de chaque proxy sur `127.0.0.1` (HTTPS en 10443, 8443 et 9443 pour la production,
la recette et le dev), et le frontal aiguille chaque nom vers le sien. Les URL publiques n'ont
donc plus de port, et `PUBLIC_ORIGIN` vaut `https://` suivi du nom de l'environnement.

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

Le navigateur avertira d'un émetteur inconnu : c'est attendu. C'est le mode du poste de
développement et des tests e2e ; la VM utilise Let's Encrypt par DNS-01 (plus bas).

### Let's Encrypt

Le défi HTTP-01 exige un nom de domaine **résolvable publiquement** et le port 80 joignable
depuis Internet. La VM de l'école ne remplit ni l'une ni l'autre condition : ce chemin reste
livré pour une machine publique, et n'a pas été exercé. La VM passe par DNS-01 (section
suivante).

```bash
make stack-up                                     # nginx doit tourner pour servir le défi
make tls-acme PUBLIC_HOST=enervision.fr ACME_EMAIL=ops@enervision.fr
```

Renouvellement, à passer en tâche planifiée sur la machine :

```cron
17 3 * * * cd /srv/enervision && make tls-renew >> /var/log/enervision-tls.log 2>&1
```

### Let's Encrypt par DNS-01, le mode de la VM

La VM n'a qu'une IP privée : le défi HTTP-01 y est impossible. Ses trois noms sont chez dynv6,
dont l'API pose l'enregistrement TXT du défi DNS-01, et acme.sh le fait sans rien ouvrir
([ADR 0018](../../docs/adr/0018-noms-publics-certificats-dns01-et-frontal-sni.md)).

```bash
make tls-dns01          # PUBLIC_HOST lu dans .env, jeton dans ../dns.token (600)
```

Autre fournisseur : `DNS01_API` et `DNS01_JETON_VAR` nomment le greffon acme.sh et sa variable
(`dns_cf` et `CF_Token` pour Cloudflare, par exemple). La cible est rejouable : acme.sh ne renouvelle qu'à trente jours de l'échéance, installe le
résultat dans `tls/` et recharge le proxy s'il tourne. Son état vit dans `acme/`, ignoré par git.
`deploy.yml` la rejoue avant chaque `make stack-up`, et `/etc/cron.d/enervision-tls` chaque nuit.

## Écouteur PROXY protocol

Sur la VM, le frontal `infra/front` relaie les connexions TLS sans les déchiffrer. Reçues sur
443, elles porteraient son adresse, et `limit_req` comme `get_client_ip()` compteraient tous les
postes comme un seul. Le port 4443 ne les accepte qu'avec l'en-tête PROXY protocol, d'où
`real_ip_header proxy_protocol` tire l'IP du client ; seules les adresses des réseaux Docker ont
le droit de l'annoncer, et le port n'est publié que sur `127.0.0.1` (`PROXY_FRONT_PORT`).

## Vérifier la configuration sans démarrer la stack

`nginx -t` charge les certificats : `tls/` doit être rempli, par `make tls-selfsigned` au besoin.

```bash
docker run --rm \
  -v "$PWD/infra/proxy/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$PWD/infra/proxy/conf.d:/etc/nginx/conf.d:ro" \
  -v "$PWD/infra/proxy/tls:/etc/nginx/tls:ro" \
  nginx:1.31-alpine nginx -t
```

Monter `infra/proxy/` entier sur `/etc/nginx` échouerait : `mime.types` vient de l'image.
