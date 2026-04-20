# =============================================================================
# Databricks: Unity Catalog resources
# =============================================================================

# Catalog (uses metastore default managed storage)
resource "databricks_catalog" "demo" {
  name           = var.uc_catalog_name
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
# Only created when a valid storage credential is provided
resource "databricks_external_location" "iceberg" {
  count           = var.databricks_storage_credential_name != "" ? 1 : 0
  name            = "${var.uc_catalog_name}-iceberg"
  credential_name = var.databricks_storage_credential_name
  url             = "s3://${aws_s3_bucket.demo.id}/iceberg/"
  comment         = "RisingWave Iceberg sink output"
}
