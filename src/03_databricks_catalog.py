# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # 03. Unity Catalog Analysis (Managed Iceberg)
# MAGIC
# MAGIC ## Overview
# MAGIC Analyze CAN streaming data that was processed by RisingWave, output to S3 as Iceberg,
# MAGIC and batch-loaded into Unity Catalog Managed Iceberg tables.
# MAGIC
# MAGIC ## Architecture
# MAGIC ```
# MAGIC Kinesis -> RisingWave (EC2) -> Iceberg Sink -> S3 (Parquet) -> Databricks Batch -> UC Managed Iceberg
# MAGIC                MV: can_frames_decoded (CAN binary decode + pivot)
# MAGIC                MV: vehicle_summary_1min (1-min aggregation)
# MAGIC ```
# MAGIC
# MAGIC ## Tables
# MAGIC | Table | Format | Description |
# MAGIC |-------|--------|-------------|
# MAGIC | `can_frames_decoded` | Managed Iceberg | All sensor values decoded and pivoted |
# MAGIC | `vehicle_summary_1min` | Managed Iceberg | 1-min sensor aggregation |

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Overview

# COMMAND ----------

decoded_table = f"{DB}.can_frames_decoded"
summary_table = f"{DB}.vehicle_summary_1min"

df_decoded = spark.table(decoded_table)

record_count = df_decoded.count()
print(f"Total records: {record_count:,}")
print()
df_decoded.show(10, truncate=False)

# COMMAND ----------

df_decoded.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## All-Sensor Statistics

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     COUNT(*) AS total_records,
# MAGIC     MIN(event_time) AS oldest_event,
# MAGIC     MAX(event_time) AS latest_event,
# MAGIC     ROUND(AVG(speed_kmh), 2) AS avg_speed_kmh,
# MAGIC     ROUND(AVG(rpm), 0) AS avg_rpm,
# MAGIC     ROUND(AVG(fuel_pct), 1) AS avg_fuel_pct,
# MAGIC     ROUND(AVG(latitude), 5) AS avg_lat,
# MAGIC     ROUND(AVG(longitude), 5) AS avg_lon
# MAGIC FROM can_frames_decoded

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Speed distribution histogram
# MAGIC SELECT
# MAGIC     FLOOR(speed_kmh / 10) * 10 AS speed_bucket,
# MAGIC     COUNT(*) AS count
# MAGIC FROM can_frames_decoded
# MAGIC WHERE speed_kmh IS NOT NULL
# MAGIC GROUP BY speed_bucket
# MAGIC ORDER BY speed_bucket

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1-Minute Aggregation Summary

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     window_start,
# MAGIC     sensor_type,
# MAGIC     frame_count,
# MAGIC     ROUND(CAST(avg_speed_kmh AS DOUBLE), 2) AS avg_speed_kmh,
# MAGIC     ROUND(CAST(max_speed_kmh AS DOUBLE), 2) AS max_speed_kmh,
# MAGIC     ROUND(CAST(avg_rpm AS DOUBLE), 0)       AS avg_rpm,
# MAGIC     ROUND(CAST(min_fuel_pct AS DOUBLE), 1)  AS min_fuel_pct
# MAGIC FROM vehicle_summary_1min
# MAGIC ORDER BY window_start DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ## GPS Data Distribution

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     latitude  AS lat,
# MAGIC     longitude AS lon,
# MAGIC     event_time
# MAGIC FROM can_frames_decoded
# MAGIC WHERE latitude IS NOT NULL
# MAGIC   AND longitude IS NOT NULL
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 10000

# COMMAND ----------

# MAGIC %md
# MAGIC ## RPM vs Speed Correlation

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     event_time,
# MAGIC     speed_kmh,
# MAGIC     rpm
# MAGIC FROM can_frames_decoded
# MAGIC WHERE speed_kmh IS NOT NULL
# MAGIC   AND rpm IS NOT NULL
# MAGIC ORDER BY event_time
# MAGIC LIMIT 5000

# COMMAND ----------

# MAGIC %md
# MAGIC ## Table Statistics Summary

# COMMAND ----------

for tbl_name in [decoded_table, summary_table]:
    try:
        df = spark.table(tbl_name)
        cnt = df.count()
        cols = len(df.columns)
        print(f"{tbl_name}")
        print(f"  Records: {cnt:,}")
        print(f"  Columns: {cols}")
        print()
    except Exception as e:
        print(f"{tbl_name}: Access error - {e}")
