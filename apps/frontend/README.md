# Frontend EnerVision

Le squelette applicatif n'est pas versionne a la main : il est genere par Angular CLI.

## Initialisation

Depuis `apps/` :

```bash
npx --yes @angular/cli@latest new frontend \
  --directory frontend \
  --style=scss \
  --routing \
  --ssr=false \
  --package-manager=npm \
  --skip-git
```

Le dossier `apps/frontend` doit etre vide (hors ce README) avant de lancer la commande.

## Apres generation

1. Pointer l'API dans `src/environments/` sur `http://localhost:8000/api/v1`.
2. Ajouter le proxy de developpement (`proxy.conf.json`) vers le backend.
3. Verifier que `npm start` sert bien sur le port 4200 attendu par `docker-compose.yml`.
4. Ajouter le `Dockerfile` multi-stage (build Angular puis service statique nginx).
