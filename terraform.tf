# Provider Docker
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {
  host = "unix:///var/run/docker.sock"
}

# Image Docker
resource "docker_image" "python" {
  name         = "python:3.14.7"
  keep_locally = true
}
