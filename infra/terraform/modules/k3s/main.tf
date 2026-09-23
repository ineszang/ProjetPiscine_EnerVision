locals {
  sudo_prefix    = var.ssh_user == "root" ? "" : "sudo "
  install_env    = "INSTALL_K3S_VERSION=${var.k3s_version} "
  disable_flags  = join(" ", [for c in var.k3s_disable_components : "--disable=${c}"])
  kubeconfig_cmd = "${local.sudo_prefix}cat /etc/rancher/k3s/k3s.yaml"
}

# Piege : un provisioner `destroy` impose que tout le bloc `connection` ne lise que `self`, sinon
# `terraform init` refuse le module. D'ou la connexion batie sur `triggers`, ou ne figurent que
# l'adresse, le port, l'utilisateur et le chemin de la cle : jamais la cle ni un mot de passe.
resource "null_resource" "k3s_install" {
  triggers = {
    ssh_host           = var.ssh_host
    ssh_port           = tostring(var.ssh_port)
    ssh_user           = var.ssh_user
    ssh_password       = var.ssh_password
    k3s_version        = var.k3s_version
    disable_components = join(",", var.k3s_disable_components)
    sudo_prefix        = local.sudo_prefix
    ssh_host           = var.ssh_host
    ssh_port           = tostring(var.ssh_port)
    ssh_user           = var.ssh_user
    ssh_key_path       = var.ssh_private_key_path
    sudo_prefix        = local.sudo_prefix
    k3s_version        = var.k3s_version
    disable_components = join(",", var.k3s_disable_components)
  }

  connection {
    type     = "ssh"
    host     = self.triggers.ssh_host
    port     = self.triggers.ssh_port
    user     = self.triggers.ssh_user
    password = self.triggers.ssh_password
  }

  provisioner "remote-exec" {
    inline = [
      "${local.sudo_prefix}sh -c 'curl -sfL https://get.k3s.io | ${local.install_env}sh -s - server ${local.disable_flags}'",
      "until ${local.sudo_prefix}test -f /etc/rancher/k3s/k3s.yaml; do sleep 2; done",
    ]
  }

  # Le kubeconfig est lu via sudo (fetch_kubeconfig), pas besoin de --write-kubeconfig-mode :
  # il reste 600/root par defaut, ce qui evite d'exposer les droits cluster-admin a tout utilisateur local.
  provisioner "remote-exec" {
    when       = destroy
    on_failure = continue
    inline = [
      "${self.triggers.sudo_prefix}sh -c 'test -x /usr/local/bin/k3s-uninstall.sh && /usr/local/bin/k3s-uninstall.sh || true'",
    ]
  }
}

resource "null_resource" "fetch_kubeconfig" {
  depends_on = [null_resource.k3s_install]

  triggers = {
    install_id = null_resource.k3s_install.id
  }

  provisioner "local-exec" {
    interpreter = ["PowerShell", "-NoProfile", "-Command"]

    command = <<-EOT
      $content = ssh -i "${pathexpand(var.ssh_private_key_path)}" -p ${var.ssh_port} -o StrictHostKeyChecking=accept-new ${var.ssh_user}@${var.ssh_host} "cat /etc/rancher/k3s/k3s.yaml"
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
      $content -replace "127.0.0.1", "${var.ssh_host}" |
        Set-Content -Path "${var.kubeconfig_output_path}" -Encoding UTF8
    EOT
  }
}
