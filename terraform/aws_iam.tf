# =============================================================================
# IAM: EC2 role for S3, Kinesis, and SSM access
# =============================================================================

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "ec2_risingwave" {
  name = "risingwave-ec2-${var.aws_region}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

# S3 access for Iceberg sink
resource "aws_iam_role_policy" "ec2_s3" {
  name = "s3-iceberg-access"
  role = aws_iam_role.ec2_risingwave.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
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
    }]
  })
}

# Kinesis read access
resource "aws_iam_role_policy" "ec2_kinesis" {
  name = "kinesis-read-access"
  role = aws_iam_role.ec2_risingwave.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "kinesis:GetRecords",
        "kinesis:GetShardIterator",
        "kinesis:DescribeStream",
        "kinesis:DescribeStreamSummary",
        "kinesis:ListShards",
        "kinesis:ListStreams",
        "kinesis:SubscribeToShard"
      ]
      Resource = aws_kinesis_stream.can_data.arn
    }]
  })
}

# SSM for Session Manager access (no SSH key required)
resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2_risingwave.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "risingwave" {
  name = "risingwave-ec2-${var.aws_region}"
  role = aws_iam_role.ec2_risingwave.name
}
