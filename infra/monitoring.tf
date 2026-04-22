resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"
}

resource "aws_cloudwatch_metric_alarm" "codepipeline_failed" {
  alarm_name          = "${local.name_prefix}-codepipeline-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FailedPipelineExecutions"
  namespace           = "AWS/CodePipeline"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Alarm when pipeline has failed executions"

  dimensions = {
    PipelineName = aws_codepipeline.this.name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "codebuild_validate_failed" {
  alarm_name          = "${local.name_prefix}-codebuild-validate-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FailedBuilds"
  namespace           = "AWS/CodeBuild"
  period              = 300
  statistic           = "Sum"
  threshold           = 0

  dimensions = {
    ProjectName = aws_codebuild_project.validate.name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "codebuild_deploy_failed" {
  alarm_name          = "${local.name_prefix}-codebuild-deploy-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FailedBuilds"
  namespace           = "AWS/CodeBuild"
  period              = 300
  statistic           = "Sum"
  threshold           = 0

  dimensions = {
    ProjectName = aws_codebuild_project.deploy.name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = "${local.name_prefix}-ops"

  dashboard_body = jsonencode({
    widgets = [
      {
        "type" : "metric",
        "x" : 0, "y" : 0, "width" : 12, "height" : 6,
        "properties" : {
          "metrics" : [
            ["AWS/CodePipeline", "FailedPipelineExecutions", "PipelineName", aws_codepipeline.this.name]
          ],
          "period" : 300,
          "stat" : "Sum",
          "region" : var.aws_region,
          "title" : "Failed Pipeline Executions"
        }
      },
      {
        "type" : "metric",
        "x" : 12, "y" : 0, "width" : 12, "height" : 6,
        "properties" : {
          "metrics" : [
            ["AWS/CodeBuild", "FailedBuilds", "ProjectName", aws_codebuild_project.validate.name],
            ["AWS/CodeBuild", "FailedBuilds", "ProjectName", aws_codebuild_project.deploy.name]
          ],
          "period" : 300,
          "stat" : "Sum",
          "region" : var.aws_region,
          "title" : "Failed Builds"
        }
      },
      {
        "type" : "metric",
        "x" : 0, "y" : 6, "width" : 12, "height" : 6,
        "properties" : {
          "metrics" : [
            ["AmazonMWAA", "TaskInstanceFailures"],
            ["AmazonMWAA", "ImportErrors"]
          ],
          "period" : 300,
          "stat" : "Sum",
          "region" : var.aws_region,
          "title" : "MWAA Failures / Import Errors"
        }
      }
    ]
  })
}