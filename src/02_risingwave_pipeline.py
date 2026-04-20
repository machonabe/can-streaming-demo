# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # 02. RisingWave Pipeline Verification
# MAGIC
# MAGIC ## Overview
# MAGIC Connects to the RisingWave instance on EC2 and verifies the streaming pipeline:
# MAGIC ```
# MAGIC Kinesis Source -> MV: can_frames_decoded (CAN binary decode)
# MAGIC                           |
# MAGIC                           +-> MV: vehicle_summary_1min (1-min aggregation)
# MAGIC                           |
# MAGIC                           +-> Iceberg Sink (S3)
# MAGIC ```
# MAGIC
# MAGIC ## Prerequisites
# MAGIC - EC2 instance with RisingWave is running (provisioned by Terraform)
# MAGIC - Pipeline SQL was executed during EC2 bootstrap (user_data)

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

import psycopg2

# COMMAND ----------

# MAGIC %md
# MAGIC ## Connect to RisingWave

# COMMAND ----------

def rw_execute(sql: str, fetch=False):
    """Execute SQL on the RisingWave instance."""
    conn = psycopg2.connect(
        host=config["rw_host"],
        port=config["rw_port"],
        database=config["rw_db"],
        user=config["rw_user"],
    )
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute(sql)
        result = cur.fetchall() if fetch else None
        return result
    except Exception as e:
        print(f"ERROR executing SQL: {e}")
        print(f"  SQL: {sql[:200]}...")
        raise
    finally:
        cur.close()
        conn.close()

# Connection test
try:
    version = rw_execute("SELECT version();", fetch=True)
    print(f"Connected to RisingWave: {version[0][0]}")
except Exception as e:
    print(f"ERROR: Cannot connect to RisingWave at {config['rw_host']}:{config['rw_port']}")
    print(f"  {e}")
    print("\n  Ensure the EC2 instance is running and the security group allows access.")
    raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pipeline Objects

# COMMAND ----------

print("=== Sources ===")
sources = rw_execute("SHOW SOURCES;", fetch=True)
for s in sources:
    print(f"  {s}")

print("\n=== Materialized Views ===")
mvs = rw_execute("SHOW MATERIALIZED VIEWS;", fetch=True)
for mv in mvs:
    print(f"  {mv}")

print("\n=== Sinks ===")
sinks = rw_execute("SHOW SINKS;", fetch=True)
for sink in sinks:
    print(f"  {sink}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Preview

# COMMAND ----------

print("=== can_frames_decoded (latest 5 rows) ===")
rows = rw_execute("""
    SELECT ts_ms, sensor_type, speed_kmh, rpm, fuel_pct, latitude, longitude
    FROM can_frames_decoded
    ORDER BY ts_ms DESC
    LIMIT 5
""", fetch=True)
for r in rows:
    print(f"  {r}")

# COMMAND ----------

print("=== vehicle_summary_1min ===")
rows = rw_execute("""
    SELECT window_start, sensor_type, frame_count, avg_speed_kmh, avg_rpm
    FROM vehicle_summary_1min
    ORDER BY window_start DESC
""", fetch=True)
for r in rows:
    print(f"  {r}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Record Count Check

# COMMAND ----------

count = rw_execute("SELECT COUNT(*) FROM can_frames_decoded;", fetch=True)
print(f"Total records in can_frames_decoded: {count[0][0]:,}")

count_summary = rw_execute("SELECT COUNT(*) FROM vehicle_summary_1min;", fetch=True)
print(f"Total records in vehicle_summary_1min: {count_summary[0][0]:,}")

print(f"\nRisingWave: {config['rw_host']}:{config['rw_port']}")
print(f"Dashboard:  http://{config['rw_host']}:5691")
