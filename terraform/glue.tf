# Actual five job configurations are from AWS GetJob, not reconstructed from guesses.
# All existing jobs must be IMPORTED before turning on manage_glue_jobs.
resource "aws_glue_job" "pipeline" {
  for_each          = { for k, v in local.recovered_jobs : k => v if var.manage_glue_jobs }
  name              = each.key
  description       = each.value.Description
  role_arn          = each.key == "reference-raw-ingest" ? aws_iam_role.missing_glue["ReferenceRawIngestGlueRole"].arn : each.key == "reference-transform-to-staging" ? aws_iam_role.missing_glue["ReferenceTransformToStagingGlueRole"].arn : each.value.Role
  glue_version      = each.value.GlueVersion
  worker_type       = try(each.value.WorkerType, null)
  number_of_workers = try(each.value.NumberOfWorkers, null)
  max_capacity      = try(each.value.MaxCapacity, null)
  timeout           = each.value.Timeout
  max_retries       = each.value.MaxRetries
  connections       = each.key == "reference-raw-ingest" && !var.configure_sqlserver_connection ? [] : try(each.value.Connections.Connections, [])
  command {
    name            = each.value.Command.Name
    python_version  = each.value.Command.PythonVersion
    script_location = each.value.Command.ScriptLocation
  }
  default_arguments = merge(try(each.value.DefaultArguments, {}), each.key == "reference-raw-ingest" ? {
    "--secret_arn" = var.sqlserver_secret_arn
    "--jdbc_url"   = var.sqlserver_jdbc_url
  } : {})
  lifecycle {
    prevent_destroy = true
  }
}
# The source connection was absent in AWS. No username/password is stored in Terraform.
resource "aws_glue_connection" "sqlserver" {
  count           = var.configure_sqlserver_connection ? 1 : 0
  name            = "reference-sqlserver-source"
  connection_type = "JDBC"
  connection_properties = {
    JDBC_CONNECTION_URL = var.sqlserver_jdbc_url
    SECRET_ID           = var.sqlserver_secret_arn
  }
  physical_connection_requirements {
    subnet_id              = var.private_subnet_ids[0]
    security_group_id_list = [var.mwaa_security_group_id]
    availability_zone      = "us-east-1a"
  }
}
