# 0010 - Terraform provisionne la machine, GitHub Actions déploie l'application

- Statut : accepté
- Date : 2026-09-22

## Contexte

L'[ADR 0009](0009-deux-environnements-compose-sur-la-vm-eni.md) a posé la livraison : deux
projets Compose sur la VM ENI, alignés sur `dev` et sur `main` par un runner auto-hébergé. Elle
ne dit pas qui prépare la machine. C'est `scripts/provision-host.sh`, lancé à la main en SSH.

La grille d'évaluation attend en C22 que l'infrastructure soit « provisionnée via du code
(Terraform, Ansible…) ». Le seul Terraform du dépôt installe un cluster k3s que rien ne
consomme, qui n'a jamais été appliqué, et dont la racine ne passait même pas `terraform init`
depuis que Terraform refuse les provisioners `destroy` dont la connexion lit autre chose que
`self`. Sa racine s'appelait `environments/dev`, nom qui laissait croire à un environnement
applicatif alors que les deux environnements réels sont `rec` et `prod`, sur la même machine.

La branche `feat/deploy` (PR #141) proposait la réponse inverse : Terraform construit les
images, lance les conteneurs et copie les sources par SSH. La revue a relevé deux racines sur
trois qui ne passent pas `terraform validate`, le mot de passe SSH écrit en clair dans le state,
un backend lancé sans base ni variables d'environnement, et trois architectures différentes pour
trois environnements.

## Décision

**Terraform provisionne la machine, GitHub Actions déploie l'application.** La frontière est
nette et vérifiable : `infra/terraform/environments/vm-eni` installe Docker et le plugin
Compose, exécute `scripts/provision-host.sh`, enregistre le runner. Il ne construit aucune
image, ne lance aucun conteneur, et un `apply` n'interrompt pas la stack qui tourne.

**Le déploiement continu ne change pas.** `deploy.yml` reste le seul chemin de livraison : push
sur `dev` ou `main`, alignement du clone, `make stack-up`, sonde `/api/v1/health/ready`.

**Le Bash reste la mécanique, Terraform devient le point d'entrée.** `provision-host.sh` connaît
les deux environnements, leurs ports décalés, leurs secrets et leurs certificats. Le réécrire en
HCL créerait une seconde source de vérité qui divergerait au premier changement de port.

**Aucun secret dans le state.** Authentification SSH par clé seulement, pas de variable de mot
de passe. Le jeton d'enregistrement du runner est une variable `sensitive` fournie à l'`apply`,
jamais un `trigger` : les `triggers` sont la seule partie d'un `null_resource` que Terraform
persiste.

**Les racines portent le nom de ce qu'elles provisionnent**, pas d'un environnement applicatif :
`vm-eni` pour la machine, `k3s-cible` pour le cluster resté en cible. `environments/prod`,
dossier vide, disparaît.

## Alternatives écartées

- **Ansible à la place du Bash** : plus idiomatique pour de la configuration de machine, et le
  jury le reconnaîtrait immédiatement comme de l'IaC. Mais c'est un outil de plus à installer et
  à faire tourner, pour réécrire un script qui fonctionne, à trois jours du gel technique.
- **Provisioners applicatifs de `feat/deploy`** : voir la revue sur #141. Terraform y devenait un
  orchestrateur concurrent de Compose, sans base de données ni migrations.
- **Terraform appelle aussi `make stack-up`** : le premier démarrage serait plus court d'une
  commande, mais Terraform se mettrait à porter la livraison, que le runner rejoue à chaque
  push. Deux chemins pour le même acte, c'est précisément ce que #141 montre qu'il ne faut pas.
- **k3s tout de suite** : le cluster serait vide, sans manifeste, sans registre et sans stockage
  persistant. Le module reste, documenté comme cible.
- **State Terraform distant** : un seul opérateur, pas d'exécution concurrente. Le backend local
  suffit, comme pour `k3s-cible`.

## Conséquences

- Le premier `apply` exige un jeton d'enregistrement du runner, valable une heure et pour une
  seule inscription, que seul un administrateur du dépôt peut créer. L'`apply` n'est donc pas
  rejouable sans intervention humaine, ce qui est acceptable : il ne se joue qu'à l'installation.
- L'utilisateur propriétaire de `/srv/enervision` doit exister sur la machine avant l'`apply`.
  Terraform vérifie et échoue tôt plutôt que de le créer : décider d'un compte système est une
  décision d'administration, pas un effet de bord de déploiement.
- Terraform ne sait rien de l'état de la stack. `terraform plan` ne dira jamais que la recette
  est tombée ; c'est la sonde de `deploy.yml` qui le dit.
- Pas de provisioner `destroy` sur le runner : il imposerait de mettre le chemin de la clé SSH
  dans le state, et `svc.sh uninstall` ne désinscrit pas le runner côté GitHub. Le retrait reste
  manuel, depuis les paramètres du dépôt.
- C22 cesse de reposer sur `docker-compose.prod.yml` seul. C23 reste porté par les scripts, que
  Terraform appelle désormais au lieu de les remplacer.
