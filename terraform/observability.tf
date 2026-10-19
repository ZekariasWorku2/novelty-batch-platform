# SNS topics already exist. Import when enabled.
locals {
  pipeline_sns_topics = toset([
    "new-product-trend-airflow-failures",
    "reference-raw-validation-failures",
    "reference-staged-validation-failures",
    "reference-redshift-smoke-validation-failures"
  ])
}
resource "aws_sns_topic" "pipeline" {
  for_each = var.manage_monitoring ? local.pipeline_sns_topics : toset([])
  name     = each.key
  lifecycle {
    prevent_destroy = true
  }
}
# Glue emits job-state-change events; no metrics-costing custom metric needed.
resource "aws_cloudwatch_event_rule" "glue_failed" {
  count = var.manage_monitoring ? 1 : 0
  name  = "new-product-trend-glue-job-failures"
  event_pattern = jsonencode({
    source = ["aws.glue"]
    "detail-type" = ["Glue Job State Change"]
    detail = {
      state = ["FAILED", "STOPPED", "TIMEOUT"]
      jobName = [
        "reference-raw-ingest",
        "reference-raw-data-validation",
        "reference-transform-to-staging",
        "reference-staged-data-validation",
        "reference-promote-staged-data",
        "reference-curated-to-redshift-load",
        "reference-redshift-postload-smoke-validation"
      ]
    }
  })
}
resource "aws_cloudwatch_event_target" "glue_failed_sns" {
  count     = var.manage_monitoring ? 1 : 0
  rule      = aws_cloudwatch_event_rule.glue_failed[0].name
  target_id = "notify-new-product-trend-failures"
  arn       = aws_sns_topic.pipeline["new-product-trend-airflow-failures"].arn
}
resource "aws_sns_topic_policy" "events_publish" {
  count = var.manage_monitoring ? 1 : 0
  arn   = aws_sns_topic.pipeline["new-product-trend-airflow-failures"].arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action = "sns:Publish"
      Resource = aws_sns_topic.pipeline["new-product-trend-airflow-failures"].arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.glue_failed[0].arn }
      }
    }]
  })
}
