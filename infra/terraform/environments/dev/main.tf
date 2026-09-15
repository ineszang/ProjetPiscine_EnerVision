module "k3s" {
  source = "../../modules/k3s"

  ssh_host               = var.ssh_host
  ssh_port               = var.ssh_port
  ssh_user               = var.ssh_user
  ssh_private_key_path   = var.ssh_private_key_path
  k3s_version            = var.k3s_version
  k3s_disable_components = var.k3s_disable_components
  kubeconfig_output_path = var.kubeconfig_output_path
}
