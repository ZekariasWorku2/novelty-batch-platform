# Optional adoption of the existing GitHub CodeConnection + CodePipeline/CodeBuild.
# Existing resources must be imported to Terraform state before enabling.
# No pipeline source-change trigger; deployment also requires explicit opt-in.
resource "aws_codebuild_project" "validate" {
  count        = var.manage_cicd ? 1 : 0
  name         = "new-product-trend-dag-validate"
  description  = "Static DAG, Python, JSON and Terraform validation"
  service_role = "arn:aws:iam::${var.aws_account_id}:role/NewProductTrendCodeBuildRole"
  artifacts {
    type = "CODEPIPELINE"
  }
  source {
    type      = "CODEPIPELINE"
    buildspec = "cicd/buildspec-dag-validate.yml"
  }
  environment {
    compute_type = "BUILD_GENERAL1_SMALL"
    image        = "aws/codebuild/standard:8.0"
    type         = "LINUX_CONTAINER"
  }
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_codebuild_project" "deploy" {
  count        = var.manage_cicd ? 1 : 0
  name         = "new-product-trend-dag-deploy"
  description  = "Explicitly gated S3 code uploads; NEVER runs terraform apply"
  service_role = "arn:aws:iam::${var.aws_account_id}:role/NewProductTrendCodeBuildRole"
  artifacts {
    type = "CODEPIPELINE"
  }
  source {
    type      = "CODEPIPELINE"
    buildspec = "cicd/buildspec-dag-deploy.yml"
  }
  environment {
    compute_type = "BUILD_GENERAL1_SMALL"
    image        = "aws/codebuild/standard:8.0"
    type         = "LINUX_CONTAINER"
    environment_variable {
      name  = "ALLOW_PIPELINE_DEPLOY"
      value = var.allow_pipeline_deploy ? "true" : "false"
    }
    environment_variable {
      name  = "LAKE_BUCKET"
      value = var.lake_bucket_name
    }
  }
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_codepipeline" "weekly" {
  count         = var.manage_cicd ? 1 : 0
  name          = "new-product-trend-mwaa-dag-pipeline"
  role_arn      = "arn:aws:iam::${var.aws_account_id}:role/NewProductTrendCodePipelineRole"
  pipeline_type = "V1"
  artifact_store {
    type     = "S3"
    location = var.lake_bucket_name
  }
  stage {
    name = "Source"
    action {
      name             = "SourceFromGitHub"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      output_artifacts = ["SourceOutput"]
      configuration = {
        ConnectionArn        = var.codeconnection_arn
        FullRepositoryId     = "${var.github_owner}/${var.github_repo}"
        BranchName           = var.github_branch
        DetectChanges        = "false"
        OutputArtifactFormat = "CODE_ZIP"
      }
    }
  }
  stage {
    name = "Validate"
    action {
      name             = "ValidateDag"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["SourceOutput"]
      output_artifacts = ["ValidatedOutput"]
      configuration = {
        ProjectName = aws_codebuild_project.validate[0].name
      }
    }
  }
  stage {
    name = "Deploy"
    action {
      name            = "DeployDagAndScriptsToS3"
      category        = "Build"
      owner           = "AWS"
      provider        = "CodeBuild"
      version         = "1"
      input_artifacts = ["ValidatedOutput"]
      configuration = {
        ProjectName = aws_codebuild_project.deploy[0].name
      }
    }
  }
  lifecycle {
    prevent_destroy = true
  }
}
