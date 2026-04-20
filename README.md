# CAN Streaming Demo: RisingWave + Databricks

Real-time vehicle CAN bus data processing with RisingWave streaming database and Databricks Lakehouse.

## Architecture

```
[Vehicle ECU]  ->  [Kinesis Data Streams]  ->  [RisingWave on EC2]  ->  [Iceberg Sink (S3)]
                                                   |  MV: CAN binary decode
                                                   |  MV: 1-min aggregation
                                                   v
                                          [Databricks Batch Job]  ->  [UC Managed Iceberg]
                                                                           |
                                                                      [SQL / Notebooks / AI-ML]
```

```mermaid
flowchart LR
    subgraph Vehicle["Vehicle / Edge"]
        ECU["ECU<br/>CAN Bus"]
        GW["Telematics<br/>Gateway"]
    end

    subgraph AWS_Ingest["AWS - Ingestion"]
        KDS["Amazon Kinesis<br/>Data Streams"]
    end

    subgraph AWS_Stream["AWS - Stream Processing"]
        RW["RisingWave<br/>(EC2)"]
    end

    subgraph AWS_Storage["AWS - Storage"]
        S3["Amazon S3<br/>Iceberg"]
    end

    subgraph Databricks["Databricks Lakehouse"]
        UC["Unity Catalog<br/>Managed Iceberg"]
        SQL["SQL / Notebooks"]
    end

    ECU --> GW --> KDS --> RW --> S3 --> UC --> SQL

    style RW fill:#4B0082,color:#fff
    style S3 fill:#FF9900,color:#000
    style UC fill:#FF3621,color:#fff
```

## CAN Frame Format (20 bytes binary)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0-7 | 8B | Timestamp | Unix epoch ms (Big Endian) |
| 8-9 | 2B | CAN ID | Arbitration ID |
| 10 | 1B | DLC | Data Length (always 8) |
| 11-18 | 8B | DATA | Sensor payload |
| 19 | 1B | CRC | XOR checksum |

### Sensor Types

| CAN ID | Sensor | Decode |
|--------|--------|--------|
| 0x0B0 | Speed (km/h) | `DATA[0:2] / 100.0` |
| 0x0C0 | RPM | `DATA[0:2] / 4.0` |
| 0x1A0 | Fuel (%) | `DATA[0] / 2.55` |
| 0x300 | GPS (lat/lon) | `4B each, /1e5 - offset` |
| 0x400 | Accelerometer | 3-axis (m/s^2) |
| 0x500 | Battery | Voltage + SOC |

## Prerequisites

- AWS account with CLI configured
- Databricks workspace (AWS)
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) with DAB support
- `psql` (optional, for direct RisingWave access)

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_ORG/can-streaming-demo.git
cd can-streaming-demo

# Copy the config template and fill in your values
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform/terraform.tfvars` with your:
- AWS VPC/subnet IDs
- Your IP address (for security group access)
- **Databricks NAT gateway IPs** (required for notebooks to connect to RisingWave — find under AWS Console > VPC > NAT Gateways, filter by your Databricks workspace VPC)
- Databricks workspace URL and token
- Databricks storage credential name and IAM role ARN (optional — leave empty to use metastore default storage)

### 2. Deploy infrastructure

```bash
make deploy-infra
```

This provisions:
- **S3 bucket** for Iceberg data and UC managed storage
- **Kinesis Data Stream** for CAN frame ingestion
- **EC2 instance** with RisingWave (auto-configured pipeline)
- **Security Group** with access for your IP
- **S3 VPC Endpoint** for SCP-compliant access
- **Unity Catalog** catalog, schema, and external location

### 3. Deploy notebooks

```bash
make deploy-notebooks
```

Deploys Databricks notebooks and job definitions via DAB.

### 4. Run the demo

Run notebooks in order:

| Step | Notebook | Description |
|------|----------|-------------|
| 1 | `01_kinesis_producer` | Generate CAN data and send to Kinesis |
| 2 | `02_risingwave_pipeline` | Verify RisingWave pipeline is processing |
| 3 | `rw_to_uc_ingestion` | Batch load from RisingWave to UC Managed Iceberg |
| 4 | `03_databricks_catalog` | Analyze data in Unity Catalog |
| 5 | `04_monitoring` | View pipeline metrics and data quality |

### 5. Access RisingWave directly

After `terraform apply`, the outputs show connection info:

```bash
# Dashboard (browser)
terraform -chdir=terraform output risingwave_dashboard_url

# psql
eval $(terraform -chdir=terraform output -raw risingwave_psql_command)
```

## Cleanup

```bash
make destroy
```

## Notes

### Multiple deployments in the same AWS account / region

Terraform creates IAM resources with fixed names (e.g., `risingwave-ec2-us-west-2`). If you need to run multiple instances of this demo in the same AWS account and region, change `uc_catalog_name` to a unique value and either `terraform destroy` the previous deployment first or manually rename the IAM resources in `terraform/aws_iam.tf`.

### AWS credentials for the Kinesis Producer notebook

The `01_kinesis_producer` notebook needs AWS credentials to write to Kinesis. There are two options:

1. **Instance Profile (no extra config)** — If your Databricks workspace is configured with an instance profile that has `kinesis:PutRecord` and `kinesis:PutRecords` permissions, no extra setup is needed. Leave `secrets_scope` empty.

2. **Databricks Secrets** — If your workspace doesn't have a Kinesis-capable instance profile, create a secret scope and store your AWS credentials:

   ```bash
   databricks secrets create-scope <SCOPE_NAME>
   databricks secrets put-secret <SCOPE_NAME> aws-access-key --string-value "<YOUR_ACCESS_KEY>"
   databricks secrets put-secret <SCOPE_NAME> aws-secret-key --string-value "<YOUR_SECRET_KEY>"
   # For temporary credentials (AWS SSO / STS):
   databricks secrets put-secret <SCOPE_NAME> aws-session-token --string-value "<YOUR_SESSION_TOKEN>"
   ```

   Then pass `secrets_scope` when deploying notebooks:

   ```bash
   databricks bundle deploy --var="secrets_scope=<SCOPE_NAME>" ...
   ```

   Or add `-var="secrets_scope=<SCOPE_NAME>"` to the `deploy-notebooks` target in the `Makefile`.

### Databricks NAT gateway IPs

Databricks serverless compute egresses through NAT gateways whose IPs may vary across runs. To find the correct CIDR:

1. Go to **AWS Console > VPC > NAT Gateways**
2. Filter by the VPC used by your Databricks workspace (look for VPC names containing `databricks`)
3. Note the **Elastic IP** of each NAT gateway
4. Add them as `/32` entries (or use a broader `/24` if IPs change frequently) in `databricks_nat_cidr_blocks` in your `terraform.tfvars`

Without this, the `rw_to_uc_ingestion` and `02_risingwave_pipeline` notebooks will fail with "Connection timed out" when trying to reach RisingWave on EC2.

### Running notebook 02 interactively

`02_risingwave_pipeline.py` requires `psycopg2-binary`. When running it interactively (not via DAB job), add `%pip install psycopg2-binary` at the top of the notebook, or install it on your cluster.

### Simulated GPS data

The Kinesis Producer generates GPS coordinates centered around Tokyo (35.681N, 139.767E). This is hardcoded demo data and does not affect pipeline functionality.

## Project Structure

```
.
├── Makefile                    # Deploy/destroy commands
├── terraform/                  # AWS + Databricks infrastructure
│   ├── terraform.tfvars.example  # <- THE config file
│   ├── aws_ec2.tf             # EC2 + RisingWave
│   ├── aws_kinesis.tf         # Kinesis stream
│   ├── aws_s3.tf              # S3 bucket
│   ├── aws_iam.tf             # IAM roles
│   ├── aws_networking.tf      # Security group + VPC endpoint
│   ├── databricks_uc.tf       # Unity Catalog resources
│   └── templates/             # EC2 userdata + RW SQL templates
├── databricks.yml             # DAB bundle config
├── resources/jobs.yml         # Databricks job definitions
├── src/                       # Databricks notebooks
│   ├── 00_setup.py            # Shared config (widgets)
│   ├── 01_kinesis_producer.py # CAN data -> Kinesis
│   ├── 02_risingwave_pipeline.py  # RW pipeline verification
│   ├── 03_databricks_catalog.py   # UC analysis
│   ├── 04_monitoring.py       # Pipeline monitoring
│   └── rw_to_uc_ingestion.py  # Batch: RW -> UC Iceberg
└── docs/
    └── architecture.md        # Detailed architecture comparison
```
