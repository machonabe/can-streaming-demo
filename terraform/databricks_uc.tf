# =============================================================================
# Databricks: Unity Catalog resources
# =============================================================================

# Catalog with storage_root on the customer's S3 bucket
resource "databricks_catalog" "demo" {
  name           = var.uc_catalog_name
  storage_root   = "s3://${aws_s3_bucket.demo.id}/uc_managed/"
  isolation_mode = "OPEN"
  comment        = "CAN Streaming Demo - Managed Iceberg tables"
}

# Schema for streaming tables
resource "databricks_schema" "demo" {
  catalog_name = databricks_catalog.demo.name
  name         = var.uc_schema_name
  comment      = "Vehicle CAN streaming data from RisingWave pipeline"
}

# External location for reading RisingWave Iceberg output on S3
resource "databricks_external_location" "iceberg" {
  name            = "${var.uc_catalog_name}-iceberg"
  credential_name = data.databricks_storage_credential.existing.name
  url             = "s3://${aws_s3_bucket.demo.id}/iceberg/"
  comment         = "RisingWave Iceberg sink output"

  depends_on = [aws_s3_bucket_policy.demo]
}

# Look up the existing storage credential by IAM role ARN
data "databricks_storage_credential" "existing" {
  name = var.databricks_storage_credential_name
}
