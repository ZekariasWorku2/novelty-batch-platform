output "account_id" {
  value = var.aws_account_id
}
output "s3_lake_bucket" {
  value = var.lake_bucket_name
}
output "weekly_dag_s3_key" {
  value = "mwaa/dags/new_product_trend_weekly.py"
}
output "mwaa_environment_arn" {
  value = var.enable_mwaa ? aws_mwaa_environment.weekly[0].arn : null
}
output "redshift_workgroup_name" {
  value = var.enable_redshift ? aws_redshiftserverless_workgroup.weekly[0].workgroup_name : null
}
