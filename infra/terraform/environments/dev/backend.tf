locals {
  backend_dir            = "../../../../apps/backend"
  backend_image_name     = "enervision-back"
  backend_image_tag      = "latest"
  backend_container_name = "enervision-backend"
}

resource "docker_image" "backend" {
  name = "${local.backend_image_name}:${local.backend_image_tag}"

  build {
    context    = local.backend_dir
    dockerfile = "Dockerfile"
  }

  triggers = {
    build_hash = sha256(join("", [
      for file in fileset(local.backend_dir, "**") :
      filesha256("${local.backend_dir}/${file}")
    ]))
  }
}

resource "docker_container" "backend" {
  image = docker_image.backend.image_id
  name  = local.backend_container_name

  ports {
    internal = 8000
    external = var.backend_port
  }

  volumes {
    host_path      = "/var/log/enervision"
    container_path = "/var/log/enervision"
  }

  depends_on = [docker_image.backend]
}

resource "null_resource" "deploy_backend_to_server" {
  depends_on = [docker_image.backend]

  triggers = {
    image_id = docker_image.backend.image_id
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

  provisioner "file" {
    source      = "${local.backend_dir}/Dockerfile"
    destination = "/tmp/Dockerfile"
  }
  provisioner "file" {
    source      = "${local.backend_dir}/"
    destination = "/tmp/backend/"
  }

  provisioner "remote-exec" {
    inline = [
      "cd /tmp/backend",
      "sudo docker stop ${local.backend_container_name} 2>/dev/null || true",
      "sudo docker rm ${local.backend_container_name} 2>/dev/null || true",
      "sudo docker build -t ${local.backend_image_name}:${local.backend_image_tag} .",
      "sudo docker run -d --name ${local.backend_container_name} -p ${var.backend_port}:8000 --restart always -v /var/log/enervision:/var/log/enervision ${local.backend_image_name}:${local.backend_image_tag}"
    ]
  }
}


