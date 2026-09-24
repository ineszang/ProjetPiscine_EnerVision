# Contrat d'authentification, côté frontend

Ce que le frontend doit savoir pour coder la connexion, et rien de plus. Le raisonnement est
dans l'[ADR 0002](../adr/0002-authentification-jwt-et-refresh-opaque.md).

Statut : `Fait` côté backend, `Cible` côté Angular.

## En une phrase

Le **jeton d'accès** vit en mémoire JavaScript et part dans l'en-tête `Authorization`. Le
**jeton de rafraîchissement** est un cookie `HttpOnly` que le code ne voit jamais et n'a pas à
gérer : il suffit d'envoyer les requêtes avec `withCredentials`.

## Endpoints

| Méthode | Chemin | Authentification | Réponse |
|---|---|---|---|
| POST | `/api/v1/auth/login` | aucune | `200` `TokenResponse` |
| POST | `/api/v1/auth/refresh` | cookie | `200` `TokenResponse` |
| POST | `/api/v1/auth/logout` | cookie | `204` |
| POST | `/api/v1/auth/logout-all` | jeton d'accès | `204` |
| POST | `/api/v1/auth/password` | jeton d'accès | `200` `TokenResponse` |
| POST | `/api/v1/auth/forgot-password` | aucune | `202` (toujours, que le compte existe ou non) |
| POST | `/api/v1/auth/reset-password` | aucune (jeton dans le corps) | `200` `TokenResponse` |
| GET | `/api/v1/auth/me` | jeton d'accès | `200` `PrincipalResponse` |
| GET | `/api/v1/users` | jeton d'accès, `admin` | `200` `UserResponse[]` |
| POST | `/api/v1/users` | jeton d'accès, `admin` | `201` `TemporaryPasswordResponse` |
| PATCH | `/api/v1/users/{id}` | jeton d'accès, `admin` | `200` `UserResponse` |
| POST | `/api/v1/users/{id}/password-reset` | jeton d'accès, `admin` | `200` `TemporaryPasswordResponse` |

Le schéma exact est dans [`apps/backend/openapi.json`](../../apps/backend/openapi.json),
lisible sans lancer l'API, et servi par `/docs` en local et en développement. La table des
codes d'erreur ci-dessous reste la référence de comportement, le schéma celle de forme.

## Charges utiles

```jsonc
// POST /auth/login
{ "email": "operateur@enervision.fr", "password": "..." }

// TokenResponse, rendu par login, refresh et password
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "principal": {
    "id": "3f2a...",
    "email": "operateur@enervision.fr",
    "role": "lecteur | operateur | admin",
    "kind": "human",
    "must_change_password": false
  }
}

// POST /auth/password
{ "current_password": "...", "new_password": "..." }   // 8 à 128 caractères, au moins 1 majuscule, 1 minuscule, 1 chiffre, 1 caractère spécial

// POST /auth/forgot-password
{ "email": "operateur@enervision.fr" }
// Répond toujours 202, sans corps, que le compte existe, soit inactif, ou soit inconnu.

// POST /auth/reset-password
{ "token": "...", "new_password": "..." }   // même règle de complexité que /auth/password
// Le jeton vient du lien reçu par email, valable 15 minutes, à usage unique. Répond
// TokenResponse au succès (l'appareil qui pose le nouveau mot de passe reste connecté), ou 400
// si le jeton est invalide, déjà utilisé, ou expiré.
```

Le secret de rafraîchissement **n'apparaît jamais** dans le corps de la réponse.

## Codes d'erreur à traiter

| Code | Quand | Ce que fait le frontend |
|---|---|---|
| `401` sur `/auth/login` | identifiants faux, compte désactivé, compte inconnu | afficher le message générique tel quel, ne rien déduire de plus |
| `429` sur `/auth/login` | trop de tentatives | afficher l'attente, l'en-tête `Retry-After` donne les secondes |
| `401` avec `WWW-Authenticate: ... error="expired"` | jeton d'accès périmé | **rafraîchir**, puis rejouer la requête |
| `401` avec `error="token_stale"` | rôle changé ou compte désactivé pendant la session | **rafraîchir** ; si le rafraîchissement échoue, déconnecter |
| `401` avec `error="invalid_token"` | jeton illisible ou compte disparu | déconnecter |
| `401` sur `/auth/refresh` | session révoquée, expirée ou rejouée | **déconnecter** et renvoyer vers la page de connexion |
| `403` avec `detail: "password_change_required"` | mot de passe provisoire | rediriger vers l'écran de changement de mot de passe |
| `403` avec `detail: "Droits insuffisants"` | rôle trop bas | masquer ou griser l'action, ne pas déconnecter |
| `403` sur `/auth/refresh`, `/logout`, `/logout-all`, `/password` | origine hors liste autorisée (voir « Origines autorisées ») | erreur de configuration réseau, pas un cas à gérer par l'utilisateur |
| `422` | corps invalide | le détail donne `champ` et `type`, jamais la valeur envoyée |
| `429` sur `/auth/forgot-password` | trop de demandes | afficher l'attente, l'en-tête `Retry-After` donne les secondes |
| `400` sur `/auth/reset-password` | lien invalide, déjà utilisé, ou expiré | inviter à redemander un lien depuis `/forgot-password` |
| `403` sur `/auth/reset-password` | origine hors liste autorisée | erreur de configuration réseau, pas un cas à gérer par l'utilisateur |

## Les quatre règles qui comptent

**1. Le jeton d'accès ne se persiste jamais.** Ni `localStorage`, ni `sessionStorage`, ni
cookie : un signal dans un service racine. Un rechargement de page le perd, c'est voulu.

**2. Au démarrage de l'application, appeler `/auth/refresh`.** C'est ce qui restaure la session
après un rechargement, via `provideAppInitializer`. Un `401` y est normal : il signifie
simplement qu'il n'y a pas de session, on affiche la page de connexion.

**3. Un seul rafraîchissement en vol à la fois.** C'est une exigence, pas une optimisation.
Cinq requêtes parallèles qui prennent cinq fois `401` déclencheraient cinq rotations
concurrentes ; le serveur n'en accepte qu'une et considère les autres comme un rejeu, ce qui
**révoque toute la session**. L'utilisateur serait déconnecté à chaque chargement de page.

```ts
// Dans l'intercepteur : une seule rotation partagée par tous les appelants.
private rotation$?: Observable<TokenResponse>;

private rafraichir(): Observable<TokenResponse> {
  this.rotation$ ??= this.http.post<TokenResponse>('/api/v1/auth/refresh', {}, { withCredentials: true })
    .pipe(finalize(() => (this.rotation$ = undefined)), shareReplay(1));
  return this.rotation$;
}
```

**4. Toutes les requêtes vers `/auth/*` portent `withCredentials: true`.** Sans quoi le cookie
n'est pas envoyé et le rafraîchissement échoue toujours.

## Ce qu'il faut savoir sur le cookie

- Nom `ev_refresh` en local, `__Secure-ev_refresh` ailleurs. Le code ne le lit jamais.
- `HttpOnly`, `SameSite=Strict`, `Path=/api/v1/auth`. Il n'est donc envoyé que sur ces routes.
- `Secure` dès que l'environnement n'est pas `local`, donc **HTTPS obligatoire hors poste de
  développement**.
- `HttpOnly` empêche de voler le cookie, pas de s'en servir : une XSS peut appeler
  `/auth/refresh` depuis l'origine de la victime. La vraie défense contre ce cas reste de ne pas
  avoir de XSS.

## Dev et production, le point à ne pas rater

En développement, `proxy.conf.json` fait passer `/api` par `localhost:4200`, donc tout est
**même origine** et le cookie marche sans rien configurer.

En déploiement, les deux conditions sont désormais remplies par le reverse proxy
([ADR 0007](../adr/0007-terminaison-tls-et-reverse-proxy-nginx.md)) : `environment.ts` porte un
`apiUrl` relatif, `/api/v1`, et le proxy sert le SPA sur `/` et l'API sur `/api/` **sous la même
origine, en HTTPS**. C'est cela, et rien d'autre, qui rend le cookie `__Secure-ev_refresh`
utilisable : servi en HTTP simple ou depuis une autre origine, il n'est jamais posé et
l'authentification ne survit pas à un rechargement de page.

Sur la machine, le certificat vient de Let's Encrypt par DNS-01
([ADR 0018](../adr/0018-noms-publics-certificats-dns01-et-frontal-sni.md)) : le navigateur n'a
aucune exception à accepter. Sur le poste, il reste auto-signé, et un navigateur qui refuse
l'exception refusera aussi le cookie.

Et au moins une fois avant la soutenance, lancer le front **sans le proxy**, en cross-origin
réel : c'est le seul moyen d'exercer le préflight CORS et `SameSite`, que la même origine masque.

## Origines autorisées

Le backend ne monte le middleware CORS que si `APP_CORS_ORIGINS` est renseigné, et refuse de
démarrer hors `local` si la liste est vide. Les routes portant le cookie vérifient en plus
l'en-tête `Origin` : une origine absente de la liste reçoit un `403`.

Méthodes autorisées : `GET`, `POST`, `PATCH`, `PUT`, `DELETE`, `OPTIONS`.
En-têtes autorisés : `Authorization`, `Content-Type`. En-tête exposé : `Retry-After`.

## Premier compte

Créé en ligne de commande côté serveur (`make bootstrap-admin EMAIL=...`), avec
`must_change_password` à vrai. La première connexion renvoie donc `403
password_change_required` sur toute route métier, et seuls `/auth/me` et `/auth/password`
répondent. L'écran de changement de mot de passe doit exister avant la démonstration.

Idem pour tout compte créé par un administrateur : le mot de passe provisoire est affiché **une
seule fois** dans la réponse, il n'est plus jamais récupérable.
