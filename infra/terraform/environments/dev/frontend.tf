resource "null_resource" "frontend" {
  depends_on = [module.k3s]

  triggers = {
    build_hash = sha256(join("", [
      for file in fileset("${path.root}/../../../apps/frontend/dist/frontend/browser", "**") :
      filesha256("${path.root}/../../../apps/frontend/dist/frontend/browser/${file}")
    ]))
  }

  connection {
    type        = "ssh"
    host        = var.ssh_host
    port        = var.ssh_port
    user        = var.ssh_user
    private_key = file(pathexpand(var.ssh_private_key_path))
  }

  provisioner "remote-exec" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y nginx",
      "sudo mkdir -p /var/www/enervision",
      "sudo rm -rf /var/www/enervision/*"
    ]
  }

  provisioner "file" {
    source      = "${path.root}/../../../apps/frontend/dist/frontend/browser/"
    destination = "/tmp/enervision-frontend"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo cp -r /tmp/enervision-frontend/* /var/www/enervision/",
      "sudo chown -R www-data:www-data /var/www/enervision"
    ]
  }
}