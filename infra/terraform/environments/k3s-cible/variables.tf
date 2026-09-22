variable "ssh_host" {
  type        = string
  description = "Adresse IP ou nom d'hote du serveur on-premise de l'ecole."
}

variable "ssh_port" {
  type        = number
  description = "Port SSH du serveur."
  default     = 22
}

variable "ssh_user" {
  type        = string
  description = "Utilisateur SSH utilise pour l'installation."
  default     = "root"
}

variable "ssh_private_key_path" {
  type        = string
  description = "Chemin local vers la cle privee SSH."
  sensitive   = true
}

variable "k3s_version" {
  type        = string
  description = "Version k3s a epingler pour un deploiement reproductible (ex: v1.31.5+k3s1). Voir https://github.com/k3s-io/k3s/releases."
}

variable "k3s_disable_components" {
  type        = list(string)
  description = "Composants embarques k3s a desactiver."
  default     = ["traefik"]
}

variable "kubeconfig_output_path" {
  type        = string
  description = "Chemin local ou ecrire le kubeconfig recupere apres installation."
  default     = "./kubeconfig"
}
