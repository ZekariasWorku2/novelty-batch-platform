# Actual trust/inline/managed policy snapshots are versioned in recovered/iam_roles.json.
# BEFORE enabling manage_existing_iam, import each pre-existing role and policy into state.
resource "aws_iam_role" "recovered" {
  for_each           = var.manage_existing_iam ? local.recovered_roles : {}
  name               = each.key
  assume_role_policy = jsonencode(each.value.assume_role_policy)
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_iam_role_policy" "recovered" {
  for_each = var.manage_existing_iam ? local.role_inline : {}
  name     = each.value.name
  role     = aws_iam_role.recovered[each.value.role].id
  policy   = jsonencode(each.value.policy)
}
resource "aws_iam_role_policy_attachment" "recovered" {
  for_each   = var.manage_existing_iam ? local.role_attachments : {}
  role       = aws_iam_role.recovered[each.value.role].name
  policy_arn = each.value.arn
}
# These two roles do not exist in AWS; they back the missing extraction/transform jobs.
resource "aws_iam_role" "missing_glue" {
  for_each = var.manage_glue_jobs ? toset(["ReferenceRawIngestGlueRole", "ReferenceTransformToStagingGlueRole"]) : toset([])
  name     = each.key
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy_attachment" "missing_glue_service" {
  for_each   = aws_iam_role.missing_glue
  role       = each.value.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}
resource "aws_iam_role_policy" "missing_glue_data_access" {
  for_each = aws_iam_role.missing_glue
  role     = each.value.name
  name     = "NewProductTrendS3AndSourceRead"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = [format("arn:aws:s3:::%s", var.lake_bucket_name)]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [format("arn:aws:s3:::%s/*", var.lake_bucket_name)]
      }
    ], var.sqlserver_secret_arn == "" ? [] : [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.sqlserver_secret_arn]
    }])
  })
}
