# =============================================================================
# EC2: RisingWave Instance
# =============================================================================

# Latest Ubuntu 24.04 LTS AMI
data "aws_ami" "ubuntu" {
  count       = var.ec2_ami_id == "" ? 1 : 0
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  ami_id = var.ec2_ami_id != "" ? var.ec2_ami_id : data.aws_ami.ubuntu[0].id

  # Render the RisingWave pipeline SQL
  rw_pipeline_sql = templatefile("${path.module}/templates/rw_pipeline.sql.tpl", {
    kinesis_stream_name = var.kinesis_stream_name
    aws_region          = var.aws_region
    s3_bucket           = aws_s3_bucket.demo.id
    s3_prefix           = "iceberg"
    uc_schema_name      = var.uc_schema_name
  })
}

resource "aws_instance" "risingwave" {
  ami                         = local.ami_id
  instance_type               = var.ec2_instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.risingwave.id]
  iam_instance_profile        = aws_iam_instance_profile.risingwave.name
  associate_public_ip_address = true

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/templates/ec2_userdata.sh.tpl", {
    rw_pipeline_sql = local.rw_pipeline_sql
  })

  tags = {
    Name = "risingwave-streaming"
  }
}
