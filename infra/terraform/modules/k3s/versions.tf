terraform {
  required_version = ">= 1.7"

  required_providers {
    provider = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}
