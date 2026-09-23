# 0017 - Un troisième environnement, `dev`, déployé à la demande depuis n'importe quelle branche

- Statut : accepté
- Date : 2026-09-23

## Contexte

L'[ADR 0009](0009-deux-environnements-compose-sur-la-vm-eni.md) a posé deux environnements sur
la VM ENI : la recette suit `dev`, la production suit `main`. Les environnements GitHub en
comptent trois, `dev`, `rec` et `prod`, et le troisième ne déployait rien.

Il manque un endroit où montrer une branche de travail avant son merge : la recette ne doit
porter que ce qui est intégré à `dev`, sinon elle cesse d'être une recette. Un
`workflow_dispatch` sur une branche de travail envoyait d'ailleurs cette branche dans la
recette, puisque tout ce qui n'était pas `main` y partait.

La VM est passée à 32 Go : une troisième TimescaleDB, réglée à 2 Go comme les deux autres,
tient sans peine.

## Décision

**Un troisième projet Compose, `enervision-dev`, dans `/srv/enervision/dev`**, bâti exactement
comme les deux autres : son clone, son `.env`, son certificat, préparés par
`scripts/provision-host.sh`.

**Déployé à la demande, jamais sur un push.** `deploy.yml` envoie `main` en prod, `dev` en
recette, et toute autre branche lancée depuis l'onglet Actions dans `dev`. Seul un membre ayant
le droit d'écriture sur le dépôt peut lancer un workflow.

**Ports décalés d'un cran de plus** : HTTPS `9443`, et sur `127.0.0.1` la redirection HTTP
`8083`, PostgreSQL `5435`, Mailpit `8027`, Airflow `8084`. Nom d'hôte `dev.enervision.local`,
pour la même raison de cookie que la recette.

**Le groupe de concurrence suit l'environnement**, et non plus la branche : deux branches lancées
coup sur coup écriraient sinon dans le même dossier en même temps.

## Alternatives écartées

- **`dev` suit la branche `dev` à chaque push, la recette devient manuelle** : la recette
  offrirait une version figée au jury, mais la doc CI/CD, l'ADR 0009 et l'habitude de l'équipe
  basculeraient à deux jours du rendu.
- **Un environnement par branche de travail** : un projet Compose et une TimescaleDB par
  branche, sans mécanisme de nettoyage. La machine ne le porterait pas longtemps.
- **Garder `dev` sur les postes seulement** : rien à montrer d'une branche non mergée sans
  passer par la recette.

## Conséquences

- Une branche de travail créée avant ce changement porte l'ancien `deploy.yml` : lancée à la
  main, elle part encore dans la recette. Limiter l'environnement GitHub `rec` à la branche
  `dev` ferme ce chemin, réglage que seul un administrateur du dépôt peut poser.
- `dev` ne garde aucune donnée d'une branche à l'autre au-delà de ce que ses migrations
  acceptent : une branche dont les migrations divergent de `dev` peut laisser la base dans un
  état que la suivante refuse. Recréer le volume, `docker compose down -v`, est alors le remède.
- Trois environnements construisent leurs images séparément : l'écart de l'ADR 0009, un même
  commit construit deux fois, reste ouvert jusqu'au passage à GHCR.
