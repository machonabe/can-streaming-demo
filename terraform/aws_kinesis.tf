# =============================================================================
# Kinesis Data Stream
# =============================================================================

resource "aws_kinesis_stream" "can_data" {
  name             = var.kinesis_stream_name
  shard_count      = var.kinesis_shard_count
  retention_period = 24 # hours

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }

  tags = {
    Name = var.kinesis_stream_name
  }
}
