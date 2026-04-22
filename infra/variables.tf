variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "novelty-batch-platform"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "github_owner" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "github_branch" {
  type    = string
  default = "main"
}

variable "codeconnection_arn" {
  type = string
}

variable "airflow_version" {
  type    = string
  default = "2.11.0"
}