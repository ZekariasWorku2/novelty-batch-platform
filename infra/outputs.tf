output "dag_bucket_name" {
  value = aws_s3_bucket.dags.bucket
}

output "artifact_bucket_name" {
  value = aws_s3_bucket.artifacts.bucket
}

output "mwaa_env_name" {
  value = aws_mwaa_environment.this.name
}