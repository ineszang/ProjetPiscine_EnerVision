variable "ssh_host" {
  type        = string
  description = "Adresse de la VM ENI qui porte les trois environnements (ADR 0009, ADR 0017)."
}

variable "ssh_port" {
  type        = number
  description = "Port SSH de la VM."
  default     = 22
}

variable "ssh_user" {
  type        = string
  description = "Utilisateur SSH du provisionnement. Different de root, les commandes privilegiees sont prefixees par sudo."
  default     = "root"
}

variable "ssh_private_key_path" {
  type        = string
  description = "Chemin local vers la cle privee SSH. L'authentification par mot de passe n'est volontairement pas prise en charge : une variable de mot de passe finit en clair dans le state ou dans les triggers."
  sensitive   = true
}

variable "proprietaire" {
  type        = string
  description = "Utilisateur qui possede la racine et fait tourner le runner. Il doit exister sur la machine : git refuse les depots appartenant a un autre utilisateur, et un .env en 600 lui echapperait."

  validation {
    condition     = can(regex("^[a-z_][a-z0-9_-]*$", var.proprietaire))
    error_message = "proprietaire doit etre un nom d'utilisateur Unix valide."
  }
}

variable "racine" {
  type        = string
  description = "Dossier qui porte un clone du depot par environnement."
  default     = "/srv/enervision"
}

variable "depot_url" {
  type        = string
  description = "URL de clonage du depot, passee a provision-host.sh."
  default     = "https://github.com/ineszang/ProjetPiscine_EnerVision.git"
}

variable "adresse_publique" {
  type        = string
  description = "Adresse annoncee dans les certificats auto-signes. Vide : la premiere adresse de la VM."
  default     = ""
}

variable "runner_url" {
  type        = string
  description = "Depot GitHub auquel le runner s'enregistre."
  default     = "https://github.com/ineszang/ProjetPiscine_EnerVision"
}

variable "runner_version" {
  type        = string
  description = "Version d'actions-runner a installer, sans le v initial (ex: 2.330.0). Voir https://github.com/actions/runner/releases."

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.runner_version))
    error_message = "runner_version doit etre epinglee explicitement (ex: 2.330.0), sinon l'installation cesse d'etre reproductible."
  }
}

variable "runner_token" {
  type        = string
  description = "Jeton d'enregistrement du runner. Expire au bout d'une heure et ne vaut que pour une inscription : Parametres du depot > Actions > Runners > New self-hosted runner. Seul un administrateur du depot peut le creer."
  sensitive   = true
}

variable "runner_labels" {
  type        = string
  description = "Libelles supplementaires du runner. deploy.yml cible [self-hosted, linux, eni-g3], les deux premiers etant poses par GitHub."
  default     = "eni-g3"
}

variable "runner_nom" {
  type        = string
  description = "Nom du runner cote GitHub, unique dans le depot. Vide : le nom d'hote de la machine, qui reste unique si cette racine est reprise pour une seconde VM. A renseigner pour faire tourner deux runners sur la meme machine."
  default     = ""
}

variable "runner_dossier" {
  type        = string
  description = "Dossier d'installation du runner sur la machine."
  default     = "/opt/actions-runner"
}
