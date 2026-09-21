terraform {
  required_version = ">= 1.7"

  required_providers {
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }

    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 4.5.0"
    }
  }

}
