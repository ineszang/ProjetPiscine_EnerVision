output "machine" {
  description = "Machine provisionnee et racine qui porte un clone par environnement."
  value       = "${var.ssh_user}@${var.ssh_host}:${var.racine}"
}

output "runner" {
  description = "Dossier d'installation du runner et libelles supplementaires annonces a GitHub."
  value       = "${var.runner_dossier} (${var.runner_labels})"
}
