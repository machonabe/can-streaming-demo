# =============================================================================
# Networking: Security Group + S3 VPC Gateway Endpoint
# =============================================================================

data "aws_vpc" "selected" {
  id = var.vpc_id
}

data "aws_subnet" "selected" {
  id = var.subnet_id
}

data "aws_route_tables" "vpc" {
  vpc_id = var.vpc_id
}

# --- Security Group ---

resource "aws_security_group" "risingwave" {
  name_prefix = "risingwave-"
  description = "RisingWave EC2 - psql + dashboard + egress"
  vpc_id      = var.vpc_id

  # psql (PostgreSQL wire protocol)
  ingress {
    description = "RisingWave psql"
    from_port   = 4566
    to_port     = 4566
    protocol    = "tcp"
    cidr_blocks = var.admin_cidr_blocks
  }

  # Dashboard GUI
  ingress {
    description = "RisingWave Dashboard"
    from_port   = 5691
    to_port     = 5691
    protocol    = "tcp"
    cidr_blocks = var.admin_cidr_blocks
  }

  # Egress (all)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "risingwave-sg"
  }
}

# --- S3 VPC Gateway Endpoint ---
# Ensures EC2 can reach S3 even if SCPs block non-VPCE traffic.

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = data.aws_route_tables.vpc.ids

  tags = {
    Name = "can-streaming-s3-vpce"
  }
}
