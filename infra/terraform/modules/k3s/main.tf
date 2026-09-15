locals {
  sudo_prefix    = var.ssh_user == "root" ? "" : "sudo "
  install_env    = var.k3s_version != "" ? "INSTALL_K3S_VERSION=${var.k3s_version} " : ""
  disable_flags  = join(" ", [for c in var.k3s_disable_components : "--disable=${c}"])
  kubeconfig_cmd = "${local.sudo_prefix}cat /etc/rancher/k3s/k3s.yaml"
}

resource "null_resource" "k3s_install" {
  triggers = {
    ssh_host            = var.ssh_host
    k3s_version         = var.k3s_version
    disable_components  = join(",", var.k3s_disable_components)
  }

  connection {
    type        = "ssh"
    host        = var.ssh_host
    port        = var.ssh_port
    user        = var.ssh_user
    private_key = file(var.ssh_private_key_path)
  }

  provisioner "remote-exec" {
    inline = [
      "${local.sudo_prefix}sh -c 'curl -sfL https://get.k3s.io | ${local.install_env}sh -s - server --write-kubeconfig-mode 644 ${local.disable_flags}'",
      "until ${local.sudo_prefix}test -f /etc/rancher/k3s/k3s.yaml; do sleep 2; done",
    ]
  }
}

resource "null_resource" "fetch_kubeconfig" {
  depends_on = [null_resource.k3s_install]

  triggers = {
    install_id = null_resource.k3s_install.id
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      ssh -i "${var.ssh_private_key_path}" -p ${var.ssh_port} -o StrictHostKeyChecking=accept-new ${var.ssh_user}@${var.ssh_host} '${local.kubeconfig_cmd}' \
        | sed 's/127.0.0.1/${var.ssh_host}/' > "${var.kubeconfig_output_path}"
    EOT
  }
}
