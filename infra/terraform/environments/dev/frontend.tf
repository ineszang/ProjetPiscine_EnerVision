locals {
  frontend_environments = {
    dev = {
      source_dir = "${path.root}/../../../../apps/frontend/dist/frontend/browser"
      domain     = "dev.enervision"
    }
  }

  frontend_dir   = "../../../../apps/frontend"
  image_name     = "enervision-front"
  image_tag      = "latest"
  container_name = "enervision-frontend"

  selected_frontend = local.frontend_environments[var.deployment_environment]
}

provider "docker" {
  host = var.docker_host
}

#  Build le front
resource "null_resource" "build_frontend" {
  triggers = {
    frontend_files = sha256(join("", [
      for file in fileset(local.frontend_dir, "src/**,package.json") :
      filesha256("${local.frontend_dir}/${file}")
    ]))
  }

  provisioner "local-exec" {
    command = "cd ${local.frontend_dir} && npm ci && npm run build"
  }
}

# Build l'image docker du front
resource "docker_image" "frontend" {
  name = "${local.image_name}:${local.image_tag}"

  build {
    context    = local.frontend_dir
    dockerfile = "Dockerfile"
  }

  triggers = {
    build_hash = sha256(join("", [
      for file in fileset(local.frontend_dir, "**") :
      filesha256("${local.frontend_dir}/${file}")
    ]))
  }

  depends_on = [null_resource.build_frontend]
}

# Création du container Docker
resource "docker_container" "frontend" {
  image = docker_image.frontend.image_id
  name  = local.container_name

  ports {
    internal = 3000
    external = var.frontend_port
  }

  # Volume pour les logs
  volumes {
    host_path      = "/var/log/enervision"
    container_path = "/var/log/nginx"
  }

  depends_on = [docker_image.frontend]
}

# Déploiement du container sur le serveur via SSH
resource "null_resource" "deploy_to_server" {
  depends_on = [docker_image.frontend]

  triggers = {
    image_id = docker_image.frontend.image_id
  }

  connection {
    type        = "ssh"
    host        = var.ssh_host
    port        = var.ssh_port
    user        = var.ssh_user
    password    = var.ssh_password
    private_key = try(file(pathexpand(var.ssh_private_key_path)), null)
    timeout     = "5m"
  }

  # Copie le Dockerfile et nginx.conf
  provisioner "file" {
    source      = "${local.frontend_dir}/Dockerfile"
    destination = "/tmp/Dockerfile"
  }

  provisioner "file" {
    source      = "${local.frontend_dir}/nginx.conf"
    destination = "/tmp/nginx.conf"
  }

  # Copie les sources pour le build
  provisioner "file" {
    source      = "${local.frontend_dir}/"
    destination = "/tmp/frontend/"
  }

  # Build et lance le container sur le serveur
  provisioner "remote-exec" {
    inline = [
      "cd /tmp/frontend",
      "sudo docker stop ${local.container_name} 2>/dev/null || true",
      "sudo docker rm ${local.container_name} 2>/dev/null || true",
      "sudo docker build -t ${local.image_name}:${local.image_tag} .",
      "sudo docker run -d \\",
      "  --name ${local.container_name} \\",
      "  -p ${var.frontend_port}:3000 \\",
      "  --restart always \\",
      "  -v /var/log/enervision:/var/log/nginx \\",
      "  ${local.image_name}:${local.image_tag}"
    ]
  }
}


