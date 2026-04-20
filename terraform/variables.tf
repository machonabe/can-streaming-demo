# =============================================================================
# AWS
# =============================================================================

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-west-2"
}

variable "aws_profile" {
  description = "AWS CLI profile name"
  type        = string
  default     = "default"
}

# =============================================================================
# Networking
# =============================================================================

variable "vpc_id" {
  description = "Existing VPC ID where EC2 and VPC Endpoint will be created"
  type        = string
}

variable "subnet_id" {
  description = "Public subnet ID for the EC2 instance (must have internet access)"
  type        = string
}

variable "admin_cidr_blocks" {
  description = "CIDR blocks allowed to access RisingWave psql (4566) and Dashboard (5691)"
  type        = list(string)
}

# =============================================================================
# EC2 (RisingWave)
# =============================================================================

variable "ec2_instance_type" {
  description = "EC2 instance type for RisingWave"
  type        = string
  default     = "t3.medium"
}

variable "ec2_ami_id" {
  description = "AMI ID for EC2 (leave empty for latest Ubuntu 24.04)"
  type        = string
  default     = ""
}

# =============================================================================
# Kinesis
# =============================================================================

variable "kinesis_stream_name" {
  description = "Name of the Kinesis Data Stream"
  type        = string
  default     = "can-data-stream"
}

variable "kinesis_shard_count" {
  description = "Number of shards for the Kinesis stream"
  type        = number
  default     = 1
}

# =============================================================================
# S3
# =============================================================================

variable "s3_bucket_prefix" {
  description = "S3 bucket name prefix (actual name: {prefix}-{account_id})"
  type        = string
  default     = "can-streaming-demo"
}

# =============================================================================
# Databricks
# =============================================================================

variable "databricks_host" {
  description = "Databricks workspace URL (e.g., https://xxx.cloud.databricks.com)"
  type        = string
}

variable "databricks_token" {
  description = "Databricks personal access token (or set DATABRICKS_TOKEN env var)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "databricks_uc_iam_role_arn" {
  description = "IAM role ARN used by Databricks Unity Catalog for S3 access (from Storage Credentials)"
  type        = string
}

variable "databricks_storage_credential_name" {
  description = "Name of the existing Databricks Storage Credential (from Catalog > External Data > Storage Credentials)"
  type        = string
}

# =============================================================================
# Unity Catalog
# =============================================================================

variable "uc_catalog_name" {
  description = "Unity Catalog catalog name"
  type        = string
  default     = "can_streaming"
}

variable "uc_schema_name" {
  description = "Unity Catalog schema name"
  type        = string
  default     = "vehicle_streaming"
}
