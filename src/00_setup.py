# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # 00. Setup
# MAGIC CAN Streaming Demo configuration and shared settings.
# MAGIC
# MAGIC ## How Configuration Works
# MAGIC - When run as a **DAB job**: parameters are passed automatically from `resources/jobs.yml`
# MAGIC - When run **interactively**: edit the widget defaults below or set them in the notebook UI

# COMMAND ----------

# %pip install boto3 psycopg2-binary faker

# COMMAND ----------

# dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration Widgets

# COMMAND ----------

# Define widgets with defaults (overridden by DAB job parameters)
dbutils.widgets.text("uc_catalog", "can_streaming", "UC Catalog Name")
dbutils.widgets.text("uc_schema", "vehicle_streaming", "UC Schema Name")
dbutils.widgets.text("aws_region", "us-west-2", "AWS Region")
dbutils.widgets.text("kinesis_stream_name", "can-data-stream", "Kinesis Stream Name")
dbutils.widgets.text("s3_bucket", "", "S3 Bucket Name")
dbutils.widgets.text("rw_host", "", "RisingWave EC2 IP")
dbutils.widgets.text("rw_port", "4566", "RisingWave Port")
dbutils.widgets.text("secrets_scope", "", "Databricks Secrets Scope (optional)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build Config Dictionary

# COMMAND ----------

config = {
    # Unity Catalog
    "uc_catalog": dbutils.widgets.get("uc_catalog"),
    "uc_schema": dbutils.widgets.get("uc_schema"),

    # AWS
    "aws_region": dbutils.widgets.get("aws_region"),
    "kinesis_stream_name": dbutils.widgets.get("kinesis_stream_name"),
    "kinesis_shard_count": 1,

    # S3 / Iceberg
    "s3_bucket": dbutils.widgets.get("s3_bucket"),
    "s3_prefix": "iceberg",

    # RisingWave
    "rw_host": dbutils.widgets.get("rw_host"),
    "rw_port": int(dbutils.widgets.get("rw_port")),
    "rw_db": "dev",
    "rw_user": "root",

    # Secrets
    "secrets_scope": dbutils.widgets.get("secrets_scope"),

    # CAN generation parameters
    "batch_size": 500,
    "frames_per_second": 60,
}

# Derived values
DB = f"{config['uc_catalog']}.{config['uc_schema']}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set Default Catalog & Schema
# MAGIC This allows SQL cells in downstream notebooks to use short table names
# MAGIC (e.g., `can_frames_decoded` instead of `catalog.schema.can_frames_decoded`).

# COMMAND ----------

spark.sql(f"USE CATALOG {config['uc_catalog']}")
spark.sql(f"USE SCHEMA {config['uc_schema']}")
print(f"Default catalog/schema set to: {DB}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## AWS Credentials

# COMMAND ----------

aws_access_key = None
aws_secret_key = None
aws_session_token = None

if config["secrets_scope"]:
    try:
        aws_access_key = dbutils.secrets.get(config["secrets_scope"], "aws-access-key")
        aws_secret_key = dbutils.secrets.get(config["secrets_scope"], "aws-secret-key")
        print(f"AWS credentials loaded from Databricks Secrets scope: {config['secrets_scope']}")
        try:
            aws_session_token = dbutils.secrets.get(config["secrets_scope"], "aws-session-token")
            print("  Session token also loaded (temporary credentials)")
        except Exception:
            pass  # Session token is optional (not needed for IAM user keys)
    except Exception as e:
        print(f"WARNING: Failed to load from Secrets scope '{config['secrets_scope']}': {e}")
        print("  Falling back to cluster IAM role / Instance Profile")
else:
    print("No secrets_scope configured - using cluster IAM role / Instance Profile")

# COMMAND ----------

# Summary
print("=" * 55)
print("  CAN Streaming Demo - Setup Complete")
print("=" * 55)
print(f"  UC Catalog     : {config['uc_catalog']}")
print(f"  UC Schema      : {config['uc_schema']}")
print(f"  AWS Region     : {config['aws_region']}")
print(f"  Kinesis Stream : {config['kinesis_stream_name']}")
print(f"  S3 Bucket      : {config['s3_bucket']}")
print(f"  RisingWave     : {config['rw_host']}:{config['rw_port']}")
print("=" * 55)
