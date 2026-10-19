# Cost-incurring environment intentionally deleted from AWS on prior request.
# The execution role is preserved in AWS; IAM snapshot is in recovered/iam_roles.json.
resource "aws_mwaa_environment" "weekly" {
  count                  = var.enable_mwaa ? 1 : 0
  name                   = var.mwaa_environment_name
  airflow_version        = var.airflow_version
  environment_class      = "mw1.micro"
  source_bucket_arn      = "arn:aws:s3:::${var.lake_bucket_name}"
  dag_s3_path            = "mwaa/dags"
  execution_role_arn     = "arn:aws:iam::${var.aws_account_id}:role/NewProductTrendMWAAExecutionRole"
  min_workers            = 1
  max_workers            = 1
  min_webservers         = 1
  max_webservers         = 1
  webserver_access_mode  = "PUBLIC_ONLY"
  network_configuration {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.mwaa_security_group_id]
  }
  logging_configuration {
    dag_processing_logs {
      enabled   = true
      log_level = "INFO"
    }
    scheduler_logs {
      enabled   = true
      log_level = "INFO"
    }
    task_logs {
      enabled   = true
      log_level = "INFO"
    }
    webserver_logs {
      enabled   = true
      log_level = "INFO"
    }
    worker_logs {
      enabled   = true
      log_level = "INFO"
    }
  }
  airflow_configuration_options = {
    "core.load_examples" = "False"
  }
}
