output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "ec2_public_ip" {
  description = "Public IP of the RisingWave EC2 instance"
  value       = aws_instance.risingwave.public_ip
}

output "ec2_instance_id" {
  description = "EC2 instance ID (for SSM access)"
  value       = aws_instance.risingwave.id
}

output "s3_bucket_name" {
  description = "S3 bucket for Iceberg data and UC managed storage"
  value       = aws_s3_bucket.demo.id
}

output "kinesis_stream_name" {
  description = "Kinesis Data Stream name"
  value       = aws_kinesis_stream.can_data.name
}

output "uc_catalog_name" {
  description = "Unity Catalog catalog name"
  value       = databricks_catalog.demo.name
}

output "uc_schema_name" {
  description = "Unity Catalog schema name"
  value       = databricks_schema.demo.name
}

output "risingwave_dashboard_url" {
  description = "RisingWave Dashboard URL"
  value       = "http://${aws_instance.risingwave.public_ip}:5691"
}

output "risingwave_psql_command" {
  description = "Command to connect to RisingWave via psql"
  value       = "psql -h ${aws_instance.risingwave.public_ip} -p 4566 -d dev -U root"
}
