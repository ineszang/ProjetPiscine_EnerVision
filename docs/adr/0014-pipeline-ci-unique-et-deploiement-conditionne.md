# 0014 - Un pipeline CI unique appelle les workflows de composant et conditionne le déploiement

- Statut : accepté
- Date : 2026-09-23
- Note du 24/09 : au gel, les règles de branche ne sont pas posées : `prod` n'accepte que `main` mais sans relecteur, `rec` et `dev` n'ont aucune règle, aucune branche n'est protégée. L'approbation des workflows externes n'est pas lisible avec les droits d'un membre.
- Complète : [0009](0009-deux-environnements-compose-sur-la-vm-eni.md), qui reste en vigueur

## Contexte

Au 22/09, huit workflows se déclenchaient chacun de leur côté, et l'audit y a relevé :

- **Double exécution.** Chaque workflow partait sur `push` (toutes branches) **et** sur
  `pull_request`. Un commit poussé sur une branche de PR jouait donc toute la CI deux fois,
  à la même minute (constaté dans l'historique des runs de `test/integration-api-db-ml`).
- **Sonar refaisait tout.** `sonarqube.yml` reconstruisait le frontend et retestait frontend,
  backend et ML pour produire ses rapports de couverture, en double exact de `frontend.yml`,
  `backend.yml` et `ml.yml`. Son test backend tournait sans `uv sync`. Il n'avait ni
  `permissions` ni `concurrency`.
- **Déploiement non conditionné.** `deploy.yml` partait à chaque push sur `dev` ou `main`,
  que la CI du commit soit verte ou non, et déployait la pointe de branche du moment plutôt
  que le commit poussé.
- **Erreurs silencieuses et hygiène.**
  - `npm test --watch=false --code-coverage` : npm garde ces options pour lui, `ng test` ne
    les reçoit jamais, et la CI ne tenait que par les réglages d'`angular.json`.
  - `uv sync --frozen` ne vérifie pas que `uv.lock` suit `pyproject.toml`.
  - Plusieurs actions tierces étaient épinglées par tag, contrairement à la règle Sonar
    `githubactions:S7637`.
  - Aucun job n'avait de `timeout-minutes` (360 minutes par défaut).

## Décision

**`ci.yml` est le seul workflow déclenché par `pull_request` et par les push sur `dev` et
`main`.** Les workflows de composant (`backend`, `frontend`, `ml`, `airflow`, `infra`, `e2e`)
passent en `workflow_call` et n'ont plus de déclencheur propre.

1. **`changes`.** Un job initial calcule, par `dorny/paths-filter` épinglé sur un SHA, les
   composants touchés par la PR, et chaque composant n'est appelé que si son filtre vaut vrai.
   Sur un push vers `dev` ou `main`, tous les filtres valent vrai : l'analyse Sonar reste
   complète sur les branches longues, et paths-filter ne compare pas à la base de fusion avec
   `main`, qui a 80 commits de retard.
2. **`sonar`.** Il ne reconstruit ni ne reteste plus rien : il télécharge, dans le même run, les
   couvertures versées par les jobs `verification` des composants.
3. **`CI ok`.** Le job agrège le résultat de tous les autres. Il tourne toujours (`if:
   always()`) et échoue dès qu'un job est en `failure` ou `cancelled`. **C'est le seul check à
   exiger dans les règles de branche** : un composant sauté par son filtre ne publie aucun check
   interne, qui resterait « en attente » s'il était exigé.
4. **`deploy`.** Il appelle `deploy.yml`, sur les seuls push, et seulement si `CI ok` a réussi.
   `deploy.yml` aligne le dossier de l'environnement sur `GITHUB_SHA`, le commit testé, sauf
   si ce commit précède celui déjà déployé : les CI de deux push peuvent finir dans le désordre,
   et un environnement ne recule jamais. Les déploiements d'un même environnement passent un par
   un sous un verrou `flock` sur la VM, et non dans un groupe `concurrency`, où GitHub ne garde
   qu'un job en attente et annule le précédent quand un troisième arrive.

`deploy.yml` n'a toujours **aucun déclencheur `pull_request`** : il n'accepte que
`workflow_call` et `workflow_dispatch`, dans l'esprit de l'ADR 0009.

## Alternatives écartées

| Écartée | Raison |
|---|---|
| Garder huit workflows et restreindre seulement `push` à `dev` et `main` | Supprime la double exécution, pas le doublon Sonar : il faudrait toujours rejouer les tests pour que Sonar ait ses couvertures, les artefacts ne passant pas d'un workflow à l'autre. Et rien n'empêche un déploiement rouge. |
| Déclencher le déploiement par `workflow_run` | `workflow_run` joue toujours le fichier de la branche par défaut, `main`, en retard de 80 commits : la recette ne se serait plus déployée avant la prochaine remontée vers `main`, sans erreur visible. |
| `alls-green` ou une action tierce d'agrégation | Dix lignes de shell sur `toJSON(needs.*.result)` font le même travail, sans dépendance de plus à épingler. |
| Cache de couches Docker (`bake-action`, `type=gha`) pour l'e2e | Quatre pièges (noms d'image, cibles Compose, buildx, `load`) pour deux à quatre minutes gagnées. Reporté après le rendu. |

## Conséquences

- Une PR ne joue que ce qu'elle touche. Une PR de documentation ne joue que `changes` et
  `CI ok`.
- Les checks s'appellent désormais « Backend / Lint, typage et tests », etc. Au 23/09, ni `dev`
  ni `main` n'ont de règle de protection : à la première, exiger **« CI ok »** et rien d'autre.
- Modifier `ci.yml` rejoue toute la CI sur la PR (filtre `ci`).
- Le job `deploy` reste en file tant que le runner `eni-g3` n'est pas enregistré sur la VM,
  comme avant. Le groupe de concurrence par SHA des push l'empêche de bloquer les runs suivants.
- La sécurité du runner auto-hébergé ne repose pas sur l'absence de `pull_request` dans
  `deploy.yml`. Une PR de fork peut ajouter son propre workflow. Ce qui protège le runner :
  - l'approbation obligatoire des workflows de tous les contributeurs externes ;
  - les règles de branche des environnements `rec` (`dev`) et `prod` (`main` et un relecteur).

  Ces deux réglages restent à poser par l'administratrice du dépôt.
