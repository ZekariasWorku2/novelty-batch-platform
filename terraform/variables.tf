variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "aws_account_id" {
  type    = string
  default = "672350744457"
}
variable "environment" {
  type    = string
  default = "study"
}
variable "lake_bucket_name" {
  type    = string
  default = "novelty-margin-lakehouse-672350744457"
}
variable "manage_existing_iam" {
  description = "Import existing IAM roles/policies to state before enabling."
  type        = bool
  default     = false
}
variable "manage_existing_network" {
  description = "Import VPC/subnets/routes/security groups first. Never enable without a reviewed import plan."
  type        = bool
  default     = false
}
variable "manage_glue_jobs" {
  description = "Import five reference jobs before enabling. Also creates definitions for two missing jobs."
  type        = bool
  default     = false
}
variable "manage_catalog" {
  type    = bool
  default = false
}
variable "manage_workflows" {
  type    = bool
  default = false
}
variable "manage_monitoring" {
  type    = bool
  default = false
}
variable "manage_cicd" {
  type    = bool
  default = false
}
variable "enable_mwaa" {
  description = "Cost-incurring. Default OFF, matching intentionally deleted MWAA."
  type        = bool
  default     = false
}
variable "enable_nat" {
  description = "Cost-incurring. Does not automatically replace the existing blackhole route."
  type        = bool
  default     = false
}
variable "enable_redshift" {
  description = "Cost-incurring. Requires Redshift account/service readiness."
  type        = bool
  default     = false
}
variable "configure_sqlserver_connection" {
  type    = bool
  default = false
}
variable "sqlserver_jdbc_url" {
  description = "Example: jdbc:sqlserver://hostname:1433;databaseName=WideWorldImporters;encrypt=true;trustServerCertificate=false"
  type        = string
  default     = ""
}
variable "sqlserver_secret_arn" {
  description = "Existing Secrets Manager secret with username/password; never commit its value."
  type        = string
  default     = ""
}
variable "private_subnet_ids" {
  type    = list(string)
  default = ["subnet-0173f0d56db55ca14", "subnet-09d7c064734975724"]
}
variable "public_subnet_id" {
  type    = string
  default = "subnet-0d0a795cc7e255001"
}
variable "mwaa_security_group_id" {
  type    = string
  default = "sg-0585bcf31ea22f166"
}
variable "mwaa_environment_name" {
  type    = string
  default = "new-product-trend-mwaa"
}
variable "airflow_version" {
  type    = string
  default = "2.11.2"
}
variable "github_owner" {
  type    = string
  default = "ZekariasWorku2"
}
variable "github_repo" {
  type    = string
  default = "novelty-batch-platform"
}
variable "github_branch" {
  type    = string
  default = "main"
}
variable "codeconnection_arn" {
  type    = string
  default = "arn:aws:codeconnections:us-east-1:672350744457:connection/8690f980-f7a4-4aa6-b345-8f888ef008bc"
}
variable "allow_pipeline_deploy" {
  description = "Safeguard; requires explicit opt-in before CodeBuild uploads to S3."
  type        = bool
  default     = false
}
