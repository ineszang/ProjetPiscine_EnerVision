output "kubeconfig_path" {
  description = "Chemin local du kubeconfig recupere apres installation."
  value       = var.kubeconfig_output_path
}

output "node_host" {
  description = "Adresse de la machine sur laquelle k3s est installe."
  value       = var.ssh_host
}
