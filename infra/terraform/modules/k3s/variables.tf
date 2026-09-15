variable "ssh_host" {
  type        = string
  description = "Adresse IP ou nom d'hote de la machine on-premise cible."
}

variable "ssh_port" {
  type        = number
  description = "Port SSH de la machine cible."
  default     = 22
}

variable "ssh_user" {
  type        = string
  description = "Utilisateur SSH. Si different de root, les commandes d'installation sont prefixees par sudo."
  default     = "root"
}

variable "ssh_private_key_path" {
  type        = string
  description = "Chemin local vers la cle privee SSH utilisee pour se connecter a la machine cible."
  sensitive   = true
}

variable "k3s_version" {
  type        = string
  description = "Version k3s a epingler pour un deploiement reproductible (ex: v1.31.5+k3s1). Voir https://github.com/k3s-io/k3s/releases."

  validation {
    condition     = length(trimspace(var.k3s_version)) > 0
    error_message = "k3s_version doit etre epinglee explicitement, pas de valeur vide (sinon k3s.io installerait la derniere version a chaque run, non reproductible)."
  }
}

variable "k3s_disable_components" {
  type        = list(string)
  description = "Composants embarques a desactiver a l'installation (ex: traefik, servicelb)."
  default     = ["traefik"]
}

variable "kubeconfig_output_path" {
  type        = string
  description = "Chemin local ou ecrire le kubeconfig recupere apres installation."
}
