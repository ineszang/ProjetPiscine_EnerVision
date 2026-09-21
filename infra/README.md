# Infrastructure

Provisionnement Terraform de la machine on-premise (serveur physique, accessible en SSH).

- `terraform/modules` : modules reutilisables.
  - `k3s` : installe un cluster k3s single-node sur une machine distante via SSH
    (script officiel `get.k3s.io`) et rapatrie le kubeconfig en local.
- `terraform/environments/<env>` : racines Terraform, une par environnement.
  - `dev` : instancie le module `k3s` sur le serveur de l'ecole.
  - `prod` : non initialise, voir le ticket dedie.

## Usage (environments/dev)

```bash
cd infra/terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars   # renseigner ssh_host / ssh_private_key_path
terraform init
terraform apply
```

Le kubeconfig est ecrit localement au chemin defini par `kubeconfig_output_path`
(par defaut `./kubeconfig`, ignore par git).
