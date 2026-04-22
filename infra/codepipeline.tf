resource "aws_codepipeline" "this" {
  name          = "${local.name_prefix}-pipeline"
  role_arn      = aws_iam_role.codepipeline.arn
  pipeline_type = "V2"

  artifact_store {
    location = aws_s3_bucket.artifacts.bucket
    type     = "S3"
  }

  stage {
    name = "Source"

    action {
      name             = "SourceFromGitHub"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      output_artifacts = ["source_output"]

      configuration = {
        ConnectionArn        = var.codeconnection_arn
        FullRepositoryId     = "${var.github_owner}/${var.github_repo}"
        BranchName           = var.github_branch
        OutputArtifactFormat = "CODE_ZIP"
      }
    }
  }

  stage {
    name = "Validate"

    action {
      name             = "ValidateInfraAndDag"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["source_output"]
      output_artifacts = ["validated_output"]

      configuration = {
        ProjectName = aws_codebuild_project.validate.name
      }
    }
  }

  stage {
    name = "Deploy"

    action {
      name            = "DeployInfraAndDags"
      category        = "Build"
      owner           = "AWS"
      provider        = "CodeBuild"
      version         = "1"
      input_artifacts = ["validated_output"]

      configuration = {
        ProjectName = aws_codebuild_project.deploy.name
      }
    }
  }
}