data "aws_iam_policy_document" "mwaa_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type = "Service"
      identifiers = [
        "airflow.amazonaws.com",
        "airflow-env.amazonaws.com"
      ]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "mwaa_execution" {
  name               = "${local.name_prefix}-mwaa-exec"
  assume_role_policy = data.aws_iam_policy_document.mwaa_assume_role.json
}

data "aws_iam_policy_document" "mwaa_execution" {
  statement {
    sid    = "S3DagBucketAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject*",
      "s3:GetBucket*",
      "s3:List*",
      "s3:PutObject"
    ]
    resources = [
      aws_s3_bucket.dags.arn,
      "${aws_s3_bucket.dags.arn}/*"
    ]
  }

  statement {
    sid    = "CloudWatchLogsAccess"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:GetLogEvents",
      "logs:GetLogRecord",
      "logs:GetLogGroupFields",
      "logs:GetQueryResults",
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
      "logs:FilterLogEvents"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "SQSAccessRequiredByMWAA"
    effect = "Allow"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
      "sqs:SendMessage"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "GlueAthenaRedshiftAccessForDag"
    effect = "Allow"
    actions = [
      "glue:StartJobRun",
      "glue:GetJobRun",
      "glue:GetJobRuns",
      "glue:BatchStopJobRun",
      "athena:StartQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:StopQueryExecution",
      "redshift-data:ExecuteStatement",
      "redshift-data:DescribeStatement",
      "redshift-data:GetStatementResult",
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "mwaa_execution" {
  name   = "${local.name_prefix}-mwaa-execution-policy"
  policy = data.aws_iam_policy_document.mwaa_execution.json
}

resource "aws_iam_role_policy_attachment" "mwaa_execution" {
  role       = aws_iam_role.mwaa_execution.name
  policy_arn = aws_iam_policy.mwaa_execution.arn
}

data "aws_iam_policy_document" "codepipeline_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["codepipeline.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "codepipeline" {
  name               = "${local.name_prefix}-codepipeline-role"
  assume_role_policy = data.aws_iam_policy_document.codepipeline_assume_role.json
}

data "aws_iam_policy_document" "codepipeline" {
  statement {
    effect = "Allow"
    actions = [
      "s3:*",
      "codebuild:BatchGetBuilds",
      "codebuild:StartBuild",
      "codeconnections:UseConnection"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "codepipeline" {
  name   = "${local.name_prefix}-codepipeline-policy"
  policy = data.aws_iam_policy_document.codepipeline.json
}

resource "aws_iam_role_policy_attachment" "codepipeline" {
  role       = aws_iam_role.codepipeline.name
  policy_arn = aws_iam_policy.codepipeline.arn
}

data "aws_iam_policy_document" "codebuild_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "codebuild" {
  name               = "${local.name_prefix}-codebuild-role"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume_role.json
}

data "aws_iam_policy_document" "codebuild" {
  statement {
    effect = "Allow"
    actions = [
      "logs:*",
      "s3:*",
      "codebuild:*",
      "codeconnections:UseConnection",

      "iam:PassRole",
      "iam:GetRole",
      "iam:CreateRole",
      "iam:AttachRolePolicy",
      "iam:PutRolePolicy",
      "iam:CreatePolicy",
      "iam:CreateServiceLinkedRole",

      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListPolicyVersions",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",

      "ec2:*",
      "mwaa:*",
      "cloudwatch:*",

      "sns:GetTopicAttributes",
      "sns:ListTagsForResource",
      "sns:TagResource",
      "sns:UntagResource",
      "sns:CreateTopic",
      "sns:SetTopicAttributes"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "codebuild" {
  name   = "${local.name_prefix}-codebuild-policy"
  policy = data.aws_iam_policy_document.codebuild.json
}

resource "aws_iam_role_policy_attachment" "codebuild" {
  role       = aws_iam_role.codebuild.name
  policy_arn = aws_iam_policy.codebuild.arn
}
