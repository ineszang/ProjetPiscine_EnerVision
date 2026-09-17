# Design système frontend

Ce que toute nouvelle page ou tout nouveau composant Angular doit réutiliser, plutôt que
redéfinir ses propres couleurs, rayons ou espacements en dur. Contexte : issue
[#91](https://github.com/ineszang/ProjetPiscine_EnerVision/issues/91), née d'une incohérence
visuelle accumulée page après page (aucun jeton partagé n'existait avant ce chantier).

## Tokens

Déclarés en CSS custom properties dans `apps/frontend/src/styles/_tokens.scss`, importés une
seule fois dans `src/styles.scss`. Disponibles partout sans import supplémentaire.

| Variable | Rôle |
|---|---|
| `--color-primary`, `--color-primary-hover`, `--color-primary-light` | Couleur de marque (vert, dérivé du logo), actions principales |
| `--color-text`, `--color-text-muted`, `--color-label` | Hiérarchie de texte (titres, texte secondaire, labels de formulaire) |
| `--color-border`, `--color-border-light` | Bordures d'inputs et de cartes |
| `--color-bg`, `--color-surface` | Fond de page vs fond des cartes/panneaux |
| `--color-disabled` | Éléments désactivés |
| `--color-success` / `-bg`, `--color-warning` / `-bg` / `-text`, `--color-danger` / `-hover` / `-bg` / `-border`, `--color-critical` | États sémantiques (alertes, badges) |
| `--color-text-inverse` | Texte sur fond coloré plein (boutons/badges) |
| `--font-family` | Police unique de l'application |
| `--radius-sm`, `--radius-md`, `--radius-pill` | Rayons de bordure (input/bouton, carte, pastille) |
| `--shadow-card` | Ombre portée des cartes |
| `--space-1` à `--space-5` | Échelle d'espacement (0.35rem à 2.5rem) |

Les classes de formulaire partagées (`.form-label`, `.form-input`, `.form-hint`) sont dans
`apps/frontend/src/styles/_forms.scss`, importées globalement de la même façon. Elles
s'appliquent directement à des `<label>`/`<input>` natifs liés par `formControlName` : pas de
composant `ControlValueAccessor` dédié, le gain n'en vaut pas la complexité pour des formulaires
aussi simples que ceux de ce projet. Les erreurs de formulaire, elles, s'affichent via
`<ev-alert severity="danger">`, pas une classe dédiée.

La classe `.auth-page` (`apps/frontend/src/styles/_auth-page.scss`, importée globalement) porte
le fond dégradé et le centrage commun aux pages d'authentification (`login`, `change-password`,
et à terme `forgot-password`/`reset-password`) : elle enveloppe la carte, pas de duplication du
fond par page.

## Composants partagés

Dans `apps/frontend/src/app/shared/components/ui/`, chacun standalone, à importer directement
dans le tableau `imports` du composant qui l'utilise.

- **`<ev-button>`** (`button/`) : `variant` (`primary` / `secondary` / `danger`, défaut
  `primary`), `type` (`button` / `submit`, défaut `button`), `disabled`, `fullWidth` (défaut
  `true` ; passer `false` pour un bouton qui ne doit pas occuper toute la largeur de son
  conteneur, ex. une action isolée dans un en-tête).
  ```html
  <ev-button type="submit" [disabled]="form.invalid">Valider</ev-button>
  <ev-button variant="secondary" [fullWidth]="false">Déconnexion</ev-button>
  ```
- **`<ev-card>`** (`card/`) : conteneur à padding/rayon/ombre standard, sans input, tout est le
  contenu projeté (`<ng-content>`). Le style vit sur `:host` : une classe externe passée par le
  parent (`<ev-card class="ma-classe">`) se combine avec le style du composant sans le masquer.
  ```html
  <ev-card><h1>Titre</h1></ev-card>
  ```
- **`<ev-alert>`** (`alert/`) : `severity` (`success` / `warning` / `danger`, défaut `danger`),
  `role="alert"` posé automatiquement. Même principe de style sur `:host`.
  ```html
  <ev-alert severity="danger">Erreur : {{ message }}</ev-alert>
  ```
- **`<ev-badge>`** (`badge/`) : `tone` (`success` / `warning` / `danger` / `critical` /
  `neutral`, défaut `neutral`), pastille à bord arrondi pour un statut court. `danger` et
  `critical` sont deux rouges distincts (`--color-danger` vs `--color-critical`, plus sombre) :
  une sévérité `critical` ne doit pas se confondre visuellement avec une `high`.
  ```html
  <ev-badge tone="danger">critique</ev-badge>
  ```
- **`<ev-brand>`** (`brand/`) : lockup icône + « EnerVision », sans input. La taille se pilote
  entièrement via `font-size` (l'icône et le texte sont exprimés en `em`, donc ils grossissent
  ensemble en gardant le même écart proportionnel) : une page l'agrandit simplement avec
  `ev-brand { font-size: 2.1rem; }`. Ne pas recomposer icône + texte en une seule image bitmap :
  un essai en ce sens (recadrage pixel de l'asset source) a produit un rendu bruité et un espacement
  figé, impossible à ajuster proprement.
  ```html
  <ev-brand />
  ```

## Logo

L'icône seule (sans le mot-symbole), recadrée depuis l'asset source du projet, vit à deux
endroits qui doivent rester synchronisés si le logo change un jour :
`apps/frontend/public/logo-icon.png` (utilisée par `<ev-brand>`) et
`apps/backend/app/static/logo-icon.png` (référencée par `/docs`, favicon Swagger, et `/redoc` via
l'extension `x-logo` du schéma OpenAPI, voir `app/main.py`). Le mot-symbole « EnerVision » n'est
jamais une image : c'est le texte du composant `<ev-brand>`, en police système.

Le favicon `apps/frontend/public/favicon.ico` est généré depuis la même icône (multi-tailles
16 à 256px).

## Règle pour toute nouvelle page

Utiliser les tokens et les composants ci-dessus plutôt que des valeurs en dur (couleurs
hexadécimales, rayons, espacements). Étendre ce document si un nouveau composant partagé est
créé.
