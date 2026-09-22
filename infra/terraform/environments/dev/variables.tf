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

variable "ssh_password" {
  type      = string
  sensitive = true
}

variable "remote_path" {
  type        = string
  description = "Chemin distant sur le serveur pour le deploiement."
  default     = "/var/www/enervision"
}

variable "docker_host" {
  type        = string
  default     = "npipe:////.//pipe//docker_engine"
  description = "Host Docker (local ou distant)"
}

variable "frontend_port" {
  type        = number
  default     = 3000
  description = "Port externe du frontend"
}

variable "backend_port" {
  type        = number
  default     = 8000
  description = "Port externe du backend"
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

variable "deployment_environment" {
  type    = string
  default = "dev"

  validation {
    condition     = contains(["dev", "rec", "prod"], var.deployment_environment)
    error_message = "L'environnement doit être dev, rec ou prod."
  }
}

variable "vault_username" {
  description = "Username Vault"
  type        = string
  sensitive   = false
}

variable "vault_password" {
  description = "Password Vault"
  type        = string
  sensitive   = true
}
