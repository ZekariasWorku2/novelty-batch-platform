# The AWS account currently has no Redshift cluster or Serverless workgroup.
# Keep OFF for the cost-controlled study account until source/curated data exists.
resource "aws_redshiftserverless_namespace" "weekly" {
  count                   = var.enable_redshift ? 1 : 0
  namespace_name          = "reference-new-product-trend-ns"
  db_name                 = "analytics"
  manage_admin_password   = true
  iam_roles               = ["arn:aws:iam::${var.aws_account_id}:role/ReferenceRedshiftCuratedLoadRole"]
}
resource "aws_redshiftserverless_workgroup" "weekly" {
  count                = var.enable_redshift ? 1 : 0
  workgroup_name       = "reference-new-product-trend-wg"
  namespace_name       = aws_redshiftserverless_namespace.weekly[0].namespace_name
  base_capacity        = 8
  enhanced_vpc_routing = true
  publicly_accessible  = false
  subnet_ids           = var.redshift_subnet_ids
  security_group_ids   = var.redshift_security_group_ids
}
