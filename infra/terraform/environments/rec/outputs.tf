output "kubeconfig_path" {
  description = "Chemin local du kubeconfig recupere apres installation."
  value       = module.k3s.kubeconfig_path
}

output "node_host" {
  description = "Adresse du serveur sur lequel k3s est installe."
  value       = module.k3s.node_host
}
