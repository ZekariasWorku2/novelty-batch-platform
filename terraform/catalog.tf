# Five existing reference tables are defined from exact Glue Data Catalog snapshots.
resource "aws_glue_catalog_database" "reference" {
  count       = var.manage_catalog ? 1 : 0
  name        = "reference_new_product_trend"
  description = "Recovered weekly new-product-trend catalog"
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_glue_catalog_table" "reference" {
  for_each      = var.manage_catalog ? { for t in local.recovered_catalog.tables : t.Name => t } : {}
  name          = each.value.Name
  database_name = aws_glue_catalog_database.reference[0].name
  table_type    = try(each.value.TableType, "EXTERNAL_TABLE")
  parameters    = try(each.value.Parameters, {})
  storage_descriptor {
    location      = try(each.value.StorageDescriptor.Location, null)
    input_format  = try(each.value.StorageDescriptor.InputFormat, null)
    output_format = try(each.value.StorageDescriptor.OutputFormat, null)
    dynamic "columns" {
      for_each = try(each.value.StorageDescriptor.Columns, [])
      content {
        name    = columns.value.Name
        type    = columns.value.Type
        comment = try(columns.value.Comment, null)
      }
    }
    dynamic "ser_de_info" {
      for_each = try(each.value.StorageDescriptor.SerdeInfo, null) == null ? [] : [each.value.StorageDescriptor.SerdeInfo]
      content {
        name                  = try(ser_de_info.value.Name, null)
        serialization_library = try(ser_de_info.value.SerializationLibrary, null)
        parameters            = try(ser_de_info.value.Parameters, {})
      }
    }
  }
  dynamic "partition_keys" {
    for_each = try(each.value.PartitionKeys, [])
    content {
      name = partition_keys.value.Name
      type = partition_keys.value.Type
    }
  }
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_glue_data_quality_ruleset" "staged" {
  count = var.manage_catalog ? 1 : 0
  name  = "staged_trend_features_structural_rules"
  ruleset = file(format("%s/../reference/staged-validation/config/dq_ruleset.dqdl", path.module))
  target_table {
    database_name = aws_glue_catalog_database.reference[0].name
    table_name    = aws_glue_catalog_table.reference["staged_trend_features_reference"].name
  }
}
resource "aws_athena_workgroup" "reference" {
  for_each = var.manage_catalog ? toset(["reference-staged-validation", "reference-redshift-smoke-validation"]) : toset([])
  name     = each.key
  configuration {
    result_configuration {
      output_location = format("s3://%s/reference/athena-results/%s/", var.lake_bucket_name, each.key)
    }
  }
}
