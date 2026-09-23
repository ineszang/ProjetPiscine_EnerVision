# Tests de charge (k6)

Scénarios k6 contre l'API EnerVision. Issue #47, décisions dans l'ADR 0015.

## Scénarios

| Script | Cible | Profil | Quand |
|---|---|---|---|
| `smoke.js` | API directe | 2 utilisateurs pendant 1 min, chaque route de lecture | Chaque PR (job E2E), `make load-smoke` |
| `charge.js` | API directe | 50 utilisateurs simultanés : montée 2 min, plateau 5 min, descente 1 min | `make load-test`, avant une livraison |
| `stress.js` | API directe | Débit croissant de 5 à 200 req/s, arrêt au-delà de 10 % d'erreurs | `make load-stress`, pour situer la rupture |
| `limitation-debit.js` | Proxy nginx | 80 req/s pendant 15 s depuis une seule adresse | Chaque PR (job E2E), `make load-limits` |

### Hypothèses de charge

Le cahier des charges ne chiffre ni volume d'utilisateurs ni temps de réponse. Les hypothèses
retenues :

- **50 utilisateurs simultanés.** C'est un gestionnaire d'énergie par site suivi, plus
  l'exploitation, avec de la marge.
- **40 gardent le tableau de bord ouvert.** Le frontend interroge `/stats/summary` toutes les
  10 s et `/alerts` toutes les 60 s, et charge `/predictions` une fois (`dashboard.ts`,
  `alert-feed.ts`).
- **10 explorent les sites.** Ils ouvrent la liste, puis un détail avec sa mesure courante, ses
  relevés sur 24 h et ses recommandations, avec 3 à 8 s de lecture entre deux pages.

Soit environ 12 req/s en régime établi, avec des pointes au démarrage des sessions.

### Seuils

Les seuils sont posés par l'ADR 0015 et partagés par `lib/config.js`.

| Seuil | Valeur | Raison |
|---|---|---|
| `http_req_failed` | < 1 % | Aucune erreur attendue en charge nominale |
| `checks` | > 99 % | Chaque réponse est un 200 |
| Lectures, p95 | < 500 ms | Rafraîchissement du tableau de bord imperceptible |
| Lectures, p99 | < 1 s | Borne des cas les plus lents |
| `/stats/summary`, p95 | < 500 ms | Route la plus appelée (`DISTINCT ON` sur tout l'historique) |
| `/readings`, p95 | < 800 ms | Fenêtre de 24 h, la plus volumineuse |

Un seuil franchi fait échouer le tir (code de sortie 99). Le test de stress n'a qu'un seuil
bloquant, 10 % d'erreurs : il cherche la rupture, pas un niveau de service.

## Pourquoi k6 ne passe pas par le proxy

nginx limite chaque adresse IP à 20 req/s, avec une rafale de 40 (ADR 0007). Un tir depuis une
seule machine mesurerait cette limite, pas l'API.

k6 tourne donc en service Compose (profil `load`) sur le réseau du projet, et vise
`backend:8000`. Seul `limitation-debit.js` passe par `https://proxy`, précisément pour vérifier
que la limite tient : des 429 au-delà du débit autorisé, jamais d'erreur serveur.

## Lancer un tir

Il faut une stack démarrée, des données et un compte `lecteur` **déjà activé** (mot de passe
définitif).

```bash
# Poste, stack de `make dev` (API sur l'hôte) : jeu de démonstration et comptes de test
make e2e-prepare
make load-smoke K6_BASE_URL=http://host.docker.internal:8000 \
    K6_EMAIL="$(jq -r .lecteur.email tests/e2e/.comptes.json)" \
    K6_PASSWORD="$(jq -r .lecteur.password tests/e2e/.comptes.json)"

# Poste, stack conteneurisée (make stack-up) : l'API est joignable en backend:8000
make load-test K6_EMAIL=... K6_PASSWORD=...

# Recette, sur la VM, dans /srv/enervision/rec : compte lecteur créé depuis l'interface
make load-test K6_EMAIL=charge@enervision.fr K6_PASSWORD=...
```

**Recette et prod partagent la VM** (ADR 0009). `make load-test` y reste raisonnable.
`make load-stress` sature l'hôte et ralentit la prod : ne le lancer qu'en accord avec l'équipe,
hors démonstration.

`scripts/comptes-test.sh` ne sert qu'aux bases jetables. En recette, un administrateur crée le
compte `lecteur` du tir depuis l'interface, puis on s'y connecte une fois pour changer le mot de
passe temporaire.

## Lire les résultats

Chaque tir écrit dans `tests/load/results/` (ignoré par git) :

- `<scénario>-<horodatage>.html` : rapport du tableau de bord web de k6 (courbes de débit, de
  latence et de VUs), à joindre au dossier de preuves ;
- `<scénario>-<horodatage>.md` : synthèse et état de chaque seuil, aussi affichée en console et,
  en CI, dans le résumé du job ;
- `<scénario>-<horodatage>.json` : métriques brutes.

Pendant un tir, le tableau de bord Grafana « API » (profil `monitoring`) montre le débit et les
latences vus par l'API elle-même.
