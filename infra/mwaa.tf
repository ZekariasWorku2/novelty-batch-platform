resource "aws_mwaa_environment" "this" {
  name               = "${local.name_prefix}-mwaa"
  airflow_version    = var.airflow_version
  environment_class  = "mw1.micro"
  dag_s3_path        = "dags"
  source_bucket_arn  = aws_s3_bucket.dags.arn
  execution_role_arn = aws_iam_role.mwaa_execution.arn

  webserver_access_mode = "PUBLIC_ONLY"

  min_workers = 1
  max_workers = 1

  min_webservers = 1
  max_webservers = 1

  network_configuration {
    security_group_ids = [aws_security_group.mwaa.id]
    subnet_ids         = aws_subnet.private[*].id
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

  endpoint_management = "SERVICE"

  weekly_maintenance_window_start = "SUN:03:30"

  depends_on = [
    aws_s3_bucket_versioning.dags
  ]
}