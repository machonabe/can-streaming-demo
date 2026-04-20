#!/bin/bash
set -ex
exec > /var/log/risingwave-setup.log 2>&1

echo "=== RisingWave EC2 Setup Start $(date) ==="

# System update and Docker install (Ubuntu 24.04)
apt-get update -y
apt-get install -y docker.io postgresql-client-16 unzip curl

# Install AWS SSM Agent
snap install amazon-ssm-agent --classic
systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service
systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service

# Start Docker
systemctl enable docker
systemctl start docker

# RisingWave with --network host so it can access EC2 IMDS for IAM credentials
docker pull risingwavelabs/risingwave:latest
docker run -d --name risingwave \
  --network host \
  --restart unless-stopped \
  risingwavelabs/risingwave:latest \
  playground

# Wait for RisingWave to be ready
echo "Waiting for RisingWave to start..."
for i in $(seq 1 60); do
  if PGPASSWORD="" psql -h 127.0.0.1 -p 4566 -U root -d dev -c "SELECT 1;" 2>/dev/null; then
    echo "RisingWave is ready (attempt $i)"
    break
  fi
  sleep 2
done

# Write pipeline SQL to file
cat > /tmp/rw_pipeline.sql << 'PIPELINE_SQL'
${rw_pipeline_sql}
PIPELINE_SQL

# Execute pipeline SQL
echo "Setting up RisingWave pipeline..."
PGPASSWORD="" psql -h 127.0.0.1 -p 4566 -U root -d dev -f /tmp/rw_pipeline.sql

echo "=== RisingWave EC2 Setup Complete $(date) ==="
