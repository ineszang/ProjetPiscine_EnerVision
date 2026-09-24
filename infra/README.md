# Infrastructure

Provisionnement Terraform des machines on-premise. Terraform prepare la machine, GitHub Actions
deploie l'application : voir l'[ADR 0010](../docs/adr/0010-terraform-provisionne-github-actions-deploie.md).
Rien ici ne construit d'image ni ne lance de conteneur.

- `terraform/modules` : modules reutilisables.
  - `k3s` : installe un cluster k3s single-node sur une machine distante via SSH
    (script officiel `get.k3s.io`) et rapatrie le kubeconfig en local.
- `terraform/environments/<racine>` : une racine par machine provisionnee.
  - `vm-eni` : la VM `eadl-2025-nantes-g3`, qui porte les environnements `dev`, `rec` et `prod`
    ([ADR 0009](../docs/adr/0009-deux-environnements-compose-sur-la-vm-eni.md),
    [ADR 0017](../docs/adr/0017-environnement-dev-a-la-demande.md)). Installe Docker,
    execute `scripts/provision-host.sh`, enregistre le runner GitHub Actions.
  - `k3s-cible` : le cluster k3s, cible a terme de `docs/architecture/10-infra.md`. Jamais
    applique.

## Usage (environments/vm-eni)

```bash
cd infra/terraform/environments/vm-eni
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

`terraform.tfvars` est ignore par git. Trois valeurs sont a renseigner avant l'apply :

- `proprietaire` : l'utilisateur qui possede `/srv/enervision` et fait tourner le runner. Il doit
  deja exister sur la machine.
- `runner_version` : a epingler depuis <https://github.com/actions/runner/releases>.
- `runner_token` : jeton d'enregistrement, valable une heure et pour une seule inscription.
  Parametres du depot, Actions, Runners, New self-hosted runner. Seul un administrateur du depot
  peut le creer.

Apres l'apply, la machine porte `/srv/enervision/dev`, `/srv/enervision/rec` et
`/srv/enervision/prod`, chacun avec son `.env` et son certificat. Le premier demarrage reste
manuel, `make stack-up` dans chaque dossier ; les suivants sont joues par le runner a chaque push
sur `dev` et sur `main`, et a chaque lancement manuel d'une autre branche pour `dev`.

Noms et certificats (ADR 0018) : avant l'apply, la zone `domaine` doit exister chez dynv6 et son
jeton se trouver dans `<racine>/dns.token` (600, proprietaire). L'apply fait alors pointer la
zone, `prod`, `rec` et `dev` vers la machine, obtient un certificat Let's Encrypt par environnement et planifie leur
renouvellement ; sans jeton, chaque environnement garde un certificat auto-signe. Le frontal SNI (`infra/front`)
se demarre une fois depuis le dossier de la prod, `make front-up`.

Chiffrement au repos ([ADR 0020](../docs/adr/0020-chiffrement-au-repos-coffre-luks-et-sse-c.md)) :
`coffre_taille = "30G"` fait poser par `scripts/coffre-luks.sh` un coffre LUKS2 sous `/var/lib/docker/volumes` ;
vide par defaut, rien n'est pose. La premiere pose arrete Docker le temps de copier les volumes, et la cle
`/root/enervision-coffre.key` est a sauvegarder hors de la VM.

Retirer le runner se fait a la main, depuis les parametres du depot : `terraform destroy` ne le
desinscrit pas.

## Usage (environments/k3s-cible)

```bash
cd infra/terraform/environments/k3s-cible
cp terraform.tfvars.example terraform.tfvars   # renseigner ssh_host / ssh_private_key_path
terraform init
terraform apply
```

Le kubeconfig est ecrit localement au chemin defini par `kubeconfig_output_path`
(par defaut `./kubeconfig`, ignore par git).
