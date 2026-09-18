# Frontend EnerVision

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 22.1.8.

## Development server

To start a local development server, run:

```bash
ng serve
```

Once the server is running, open your browser and navigate to `http://localhost:4200/`. The application will automatically reload whenever you modify any of the source files.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Vitest](https://vitest.dev/) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Configuration spécifique au projet EnerVision

Le squelette applicatif n'est pas versionné à la main : il a été généré par Angular CLI avec la commande suivante, depuis `apps/` :

```bash
npx --yes @angular/cli@latest new frontend \
  --directory frontend \
  --style=scss \
  --routing \
  --ssr=false \
  --package-manager=npm \
  --skip-git
```

Points à vérifier après toute regénération :

1. Pointer l'API dans `src/environments/` sur `http://localhost:8000/api/v1`.
2. Ajouter le proxy de développement (`proxy.conf.json`) vers le backend.
3. Vérifier que `npm start` sert bien sur le port 4200, valeur par défaut d'`APP_CORS_ORIGINS`
   côté backend. Le `docker-compose.yml` n'a aucun service frontend.
4. Ajouter le `Dockerfile` multi-stage (build Angular puis service statique nginx).

## Design système

Tokens (couleurs, typo, espacements) et composants partagés (`ev-button`, `ev-card`,
`ev-alert`, `ev-badge`) sont documentés dans
[`docs/architecture/32-design-systeme-frontend.md`](../../docs/architecture/32-design-systeme-frontend.md).
Toute nouvelle page doit les réutiliser plutôt que définir ses propres valeurs.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
