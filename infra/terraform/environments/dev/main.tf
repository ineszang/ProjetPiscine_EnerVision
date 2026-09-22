module "k3s" {
  source = "../../modules/k3s"

  ssh_host               = var.ssh_host
  ssh_port               = var.ssh_port
  ssh_user               = var.ssh_user
  ssh_private_key_path   = var.ssh_private_key_path
  ssh_password           = var.ssh_password
  k3s_version            = var.k3s_version
  k3s_disable_components = var.k3s_disable_components
  kubeconfig_output_path = var.kubeconfig_output_path
}

provider "vault" {
  # Adresse du serveur Vault (dev)
  address = "https://10.101.200.37:8200"

  # Auth par userpass 
  auth_login {
    path = "auth/userpass/login/${var.vault_username}"
    parameters = {
      login    = var.vault_username
      password = var.vault_password
    }
  }
  # Skip verify pour dev uniquement (pas en prod!)
  # skip_client_verification = true
}