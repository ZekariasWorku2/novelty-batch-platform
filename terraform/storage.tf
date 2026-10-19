# S3 bucket is already present, versioned and encrypted. Import before managing!
resource "aws_s3_bucket" "lake" {
  count  = var.manage_existing_bucket ? 1 : 0
  bucket = var.lake_bucket_name
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_s3_bucket_versioning" "lake" {
  count  = var.manage_existing_bucket ? 1 : 0
  bucket = aws_s3_bucket.lake[0].id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  count  = var.manage_existing_bucket ? 1 : 0
  bucket = aws_s3_bucket.lake[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}
resource "aws_s3_bucket_public_access_block" "lake" {
  count                   = var.manage_existing_bucket ? 1 : 0
  bucket                  = aws_s3_bucket.lake[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
