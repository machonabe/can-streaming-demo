# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # 04. Streaming Pipeline Summary
# MAGIC
# MAGIC ## Architecture
# MAGIC ```
# MAGIC [Kinesis Data Streams] -> [RisingWave on EC2] -> [Iceberg Sink] -> [S3 Parquet] -> [Databricks Batch] -> [UC Managed Iceberg]
# MAGIC ```

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Quality Check

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     COUNT(*) AS total_records,
# MAGIC     MIN(event_time) AS first_event,
# MAGIC     MAX(event_time) AS last_event,
# MAGIC     ROUND((UNIX_TIMESTAMP(MAX(event_time)) - UNIX_TIMESTAMP(MIN(event_time))) / 60.0, 1) AS duration_min,
# MAGIC     ROUND(100.0 * COUNT(speed_kmh) / COUNT(*), 1) AS speed_fill_pct,
# MAGIC     ROUND(100.0 * COUNT(rpm) / COUNT(*), 1) AS rpm_fill_pct,
# MAGIC     ROUND(100.0 * COUNT(fuel_pct) / COUNT(*), 1) AS fuel_fill_pct,
# MAGIC     ROUND(100.0 * COUNT(latitude) / COUNT(*), 1) AS gps_fill_pct
# MAGIC FROM can_frames_decoded

# COMMAND ----------

# MAGIC %md
# MAGIC ## Speed / RPM / Fuel Analysis

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     'Speed (km/h)' AS metric,
# MAGIC     COUNT(speed_kmh) AS samples,
# MAGIC     ROUND(MIN(speed_kmh), 2) AS min_val,
# MAGIC     ROUND(AVG(speed_kmh), 2) AS avg_val,
# MAGIC     ROUND(MAX(speed_kmh), 2) AS max_val,
# MAGIC     ROUND(STDDEV(speed_kmh), 2) AS stddev_val
# MAGIC FROM can_frames_decoded
# MAGIC UNION ALL
# MAGIC SELECT
# MAGIC     'RPM' AS metric,
# MAGIC     COUNT(rpm) AS samples,
# MAGIC     ROUND(MIN(rpm), 0) AS min_val,
# MAGIC     ROUND(AVG(rpm), 0) AS avg_val,
# MAGIC     ROUND(MAX(rpm), 0) AS max_val,
# MAGIC     ROUND(STDDEV(rpm), 0) AS stddev_val
# MAGIC FROM can_frames_decoded
# MAGIC UNION ALL
# MAGIC SELECT
# MAGIC     'Fuel (%)' AS metric,
# MAGIC     COUNT(fuel_pct) AS samples,
# MAGIC     ROUND(MIN(fuel_pct), 1) AS min_val,
# MAGIC     ROUND(AVG(fuel_pct), 1) AS avg_val,
# MAGIC     ROUND(MAX(fuel_pct), 1) AS max_val,
# MAGIC     ROUND(STDDEV(fuel_pct), 1) AS stddev_val
# MAGIC FROM can_frames_decoded

# COMMAND ----------

# MAGIC %md
# MAGIC ## Throughput Estimate

# COMMAND ----------

from pyspark.sql import functions as F

df = spark.table(f"{DB}.can_frames_decoded")

stats = df.agg(
    F.count("*").alias("total_records"),
    F.min("event_time").alias("first_event"),
    F.max("event_time").alias("last_event"),
).collect()[0]

total = stats["total_records"]
first_ts = stats["first_event"]
last_ts = stats["last_event"]
duration_sec = (last_ts - first_ts).total_seconds() if first_ts and last_ts else 0

print(f"Total records     : {total:,}")
print(f"Time range        : {first_ts} -> {last_ts}")
print(f"Duration          : {duration_sec:.0f} sec ({duration_sec/60:.1f} min)")
if duration_sec > 0:
    rps = total / duration_sec
    print(f"Records/sec       : {rps:,.0f}")
    # Each pivoted record represents 6 CAN frames (all sensors)
    mb_per_min = rps * 20 * 6 * 60 / 1024 / 1024
    tb_per_day = mb_per_min * 60 * 24 / 1024 / 1024
    print(f"Throughput        : {mb_per_min:.1f} MB/min -> {tb_per_day:.3f} TB/day")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-Minute Aggregation Summary

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM vehicle_summary_1min
# MAGIC ORDER BY window_start DESC, sensor_type

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pipeline Status

# COMMAND ----------

print("=" * 60)
print("CAN Streaming Pipeline Status")
print("=" * 60)

for tbl in ["can_frames_decoded", "vehicle_summary_1min"]:
    fqn = f"{DB}.{tbl}"
    cnt = spark.table(fqn).count()
    print(f"  {tbl:30s} : {cnt:>10,} rows")

print()
print(f"RisingWave EC2  : {config['rw_host']}:{config['rw_port']}")
print(f"Kinesis Stream  : {config['kinesis_stream_name']} ({config['aws_region']})")
print(f"S3 Bucket       : s3://{config['s3_bucket']}/{config['s3_prefix']}/")
print(f"UC Catalog      : {DB} (Managed Iceberg)")
print("=" * 60)
