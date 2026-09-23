# Tests de bout en bout (Playwright)

Parcours utilisateur joués dans Chromium contre une stack qui tourne : frontend, API, base et,
en CI, le reverse proxy TLS. Issue #46, décisions dans l'ADR 0015.

## Ce qui est couvert

| Fichier | Parcours |
|---|---|
| `authentification.spec.ts` | Redirection sans session, identifiants refusés, connexion, session conservée au rechargement, déconnexion |
| `premiere-connexion.spec.ts` | Compte neuf : changement du mot de passe temporaire imposé avant le tableau de bord |
| `roles.spec.ts` | Lecteur et opérateur sans supervision ni génération, page admin refusée ; admin sur la santé des capteurs |
| `sites.spec.ts` | Liste des sites, détail (mesure instantanée, historique), recommandations filtrées sur le site |
| `recommandations.spec.ts` | Génération par l'admin, bilan, isolement d'une alerte (`?alert=`) |
| `alertes.spec.ts` | Pagination du fil (« Afficher plus »), filtres par sévérité et par site, fil vide |
| `mot-de-passe-oublie.spec.ts` | Lien invalide refusé ; réinitialisation par le lien reçu dans Mailpit |

Les parcours s'appuient sur le jeu `db/seeds/demo.sql` (sites `demo-*`) et sur les comptes créés
par `scripts/comptes-test.sh`.

## Lancer en local, contre `make dev`

```bash
make e2e-install     # une fois : dépendances et Chromium
make dev             # dans un autre terminal
make e2e-prepare     # sème demo.sql et crée les comptes test-* dans la base de dev
make e2e             # joue les parcours contre http://localhost:4200
```

`make e2e-prepare` écrit dans la base de `make dev` : trois sites `demo-*`, quatorze alertes et
des comptes `test-*`, dont un administrateur supplémentaire. Ne jamais le lancer contre la
recette ou la prod.

Rapport HTML : `cd tests/e2e && npx playwright show-report`.

## En CI

Le workflow `e2e.yml`, appelé par `ci.yml` dès que le frontend, l'API, le proxy, les fichiers
Compose ou ces tests changent :

1. construit et démarre `db`, `mailpit`, `backend`, `frontend` et `proxy` avec
   `docker-compose.prod.yml`, sur `https://localhost` et un certificat auto-signé ;
2. migre, sème `demo.sql`, crée les comptes ;
3. joue les parcours, puis publie `playwright-report` en artefact (traces au premier réessai).

## Règles d'écriture

- Sélecteurs par rôle, libellé ou `data-testid`, jamais par classe CSS de mise en page.
- Une session par fichier (`ouvrirSession` dans `beforeAll`, mode `serial`). Rejouer un cookie
  de refresh dans un autre contexte révoque la famille de session, donc pas de `storageState`
  partagé.
- Un seul worker : la zone `auth` de nginx admet 30 connexions par minute.
- Un parcours qui consomme un compte (premier login, réinitialisation) le crée lui-même par
  l'API (`creerCompteTemporaire`), pour qu'un nouvel essai ne retombe pas sur un compte déjà
  activé.

| Variable | Défaut | Rôle |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:4200` | Origine du frontend. Doit figurer dans `APP_CORS_ORIGINS` |
| `E2E_COMPTES` | aucun, requis | JSON écrit par `scripts/comptes-test.sh` |
| `E2E_MAILPIT_URL` | `http://localhost:8025` | API de Mailpit, pour le lien de réinitialisation |
