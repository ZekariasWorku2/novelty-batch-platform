resource "aws_codebuild_project" "validate" {
  name         = "${local.name_prefix}-validate"
  service_role = aws_iam_role.codebuild.arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:8.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "TF_IN_AUTOMATION"
      value = "true"
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "TF_VAR_github_owner"
      value = var.github_owner
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "TF_VAR_github_repo"
      value = var.github_repo
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "TF_VAR_github_branch"
      value = var.github_branch
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "TF_VAR_codeconnection_arn"
      value = var.codeconnection_arn
      type  = "PLAINTEXT"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "cicd/buildspec-validate.yml"
  }
}

resource "aws_codebuild_project" "deploy" {
  name         = "${local.name_prefix}-deploy"
  service_role = aws_iam_role.codebuild.arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:8.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "AWS_REGION"
      value = var.aws_region
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "MWAA_ENV_NAME"
      value = aws_mwaa_environment.this.name
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "DAG_BUCKET"
      value = aws_s3_bucket.dags.bucket
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "TF_IN_AUTOMATION"
      value = "true"
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "TF_VAR_github_owner"
      value = var.github_owner
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "TF_VAR_github_repo"
      value = var.github_repo
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "TF_VAR_github_branch"
      value = var.github_branch
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "TF_VAR_codeconnection_arn"
      value = var.codeconnection_arn
      type  = "PLAINTEXT"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "cicd/buildspec-deploy.yml"
  }
}
