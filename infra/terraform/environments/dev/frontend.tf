locals {
  frontend_environments = {
    dev = {
      source_dir = "${path.root}/../../../../apps/frontend/dist/frontend/browser"
      domain     = "dev.enervision"
    }
  }

  selected_frontend = local.frontend_environments[var.deployment_environment]
}

provider "docker" {
  host = "npipe:////.//pipe//docker_cli"
}

resource "docker_image" "frontend" {
  name         = "enervision-front:latest"
  keep_locally = false

  depends_on = [module.k3s]

  triggers = {
    environment = var.deployment_environment

    build_hash = sha256(join("", [
      for file in fileset(local.selected_frontend.source_dir, "**") :
      filesha256("${local.selected_frontend.source_dir}/${file}")
    ]))
  }

  // Variables pour la connexion SSH
  connection {
    type        = "ssh"
    host        = var.ssh_host
    port        = var.ssh_port
    user        = var.ssh_user
    password    = var.ssh_password
    private_key = file(pathexpand(var.ssh_private_key_path))
  }

  // Lancement de script en SSH avec remote-exec
  // Installation de Nginx et initialisation du répertoire du frontend
  provisioner "remote-exec" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y nginx",
      "sudo mkdir -p /var/www/enervision",
      "sudo rm -rf /var/www/enervision/*"
    ]
  }

  // Copie des fichiers vers le serveur
  provisioner "file" {
    source      = "${local.selected_frontend.source_dir}/"
    destination = "/tmp/enervision-frontend"
  }

  // Déplacement des fichiers 
  provisioner "remote-exec" {
    inline = [
      "sudo cp -r /tmp/enervision-frontend/ /var/www/enervision/",
      "sudo chown -R www-data:www-data /var/www/enervision"
    ]
  }
}

resource "docker_container" "nginx" {
  image = "enervision-front:latest"
  name  = "front"
  ports {
    internal = 4200
    external = 3000
  }
}
