terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.50"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "can-streaming-demo"
      ManagedBy = "terraform"
    }
  }
}

provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token != "" ? var.databricks_token : null
}
