# =============================================================================
# S3: Bucket for Iceberg data + UC managed storage
# =============================================================================

resource "aws_s3_bucket" "demo" {
  bucket = "${var.s3_bucket_prefix}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "can-streaming-demo"
  }
}

resource "aws_s3_bucket_versioning" "demo" {
  bucket = aws_s3_bucket.demo.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Bucket policy: allow Databricks UC IAM role (only if provided)
resource "aws_s3_bucket_policy" "demo" {
  count  = var.databricks_uc_iam_role_arn != "" ? 1 : 0
  bucket = aws_s3_bucket.demo.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowDatabricksUCAccess"
        Effect = "Allow"
        Principal = {
          AWS = var.databricks_uc_iam_role_arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.demo.arn,
          "${aws_s3_bucket.demo.arn}/*"
        ]
      }
    ]
  })
}
