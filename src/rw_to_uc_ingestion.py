# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # RisingWave -> UC Managed Iceberg Ingestion
# MAGIC
# MAGIC Pulls streaming materialized view data from RisingWave (EC2) and writes it
# MAGIC to Unity Catalog Managed Iceberg tables via batch CTAS/INSERT.

# COMMAND ----------

# MAGIC %pip install psycopg2-binary
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

import psycopg2
from pyspark.sql import SparkSession
from pyspark.sql.types import *
from pyspark.sql.functions import col, row_number
from pyspark.sql import Window
from decimal import Decimal

spark = SparkSession.builder.getOrCreate()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Ingest can_frames_decoded

# COMMAND ----------

conn = psycopg2.connect(
    host=config["rw_host"],
    port=config["rw_port"],
    user=config["rw_user"],
    dbname=config["rw_db"]
)
cur = conn.cursor()

cur.execute("""
    SELECT ts_ms, sensor_type, speed_kmh, rpm, fuel_pct,
           latitude, longitude,
           encode(substring(payload from 12 for 8), 'hex') as accel_hex,
           encode(substring(payload from 12 for 8), 'hex') as battery_hex
    FROM can_frames_decoded
""")
rows = cur.fetchall()
columns = [desc[0] for desc in cur.description]
print(f"Fetched {len(rows)} rows from can_frames_decoded")
cur.close()
conn.close()

# COMMAND ----------

schema_raw = StructType([
    StructField("ts_ms", LongType(), True),
    StructField("sensor_type", StringType(), True),
    StructField("speed_kmh", StringType(), True),
    StructField("rpm", StringType(), True),
    StructField("fuel_pct", StringType(), True),
    StructField("latitude", StringType(), True),
    StructField("longitude", StringType(), True),
    StructField("accel_hex", StringType(), True),
    StructField("battery_hex", StringType(), True),
])

df_raw = spark.createDataFrame(rows, schema=schema_raw)

# Cast numeric columns
df_raw = (df_raw
    .withColumn("speed_kmh", col("speed_kmh").cast("double"))
    .withColumn("rpm", col("rpm").cast("double"))
    .withColumn("fuel_pct", col("fuel_pct").cast("double"))
    .withColumn("latitude", col("latitude").cast("double"))
    .withColumn("longitude", col("longitude").cast("double"))
)

print(f"Raw records: {df_raw.count():,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Pivot: merge sensor rows into single wide row per timestamp
# MAGIC Each `ts_ms` has 6 rows (one per sensor). We pivot them into a single row
# MAGIC with all sensor values as columns.

# COMMAND ----------

from pyspark.sql import functions as F

# Assign row numbers within each sensor type (ordered by ts_ms)
# to pair up records across sensors
w = Window.partitionBy("sensor_type").orderBy("ts_ms")
df_numbered = df_raw.withColumn("rn", row_number().over(w))

# Pivot each sensor type
df_speed = (df_numbered.filter("sensor_type = 'SPEED'")
    .select(col("rn"), col("ts_ms"), col("speed_kmh")))
df_rpm = (df_numbered.filter("sensor_type = 'RPM'")
    .select(col("rn"), col("rpm")))
df_fuel = (df_numbered.filter("sensor_type = 'FUEL'")
    .select(col("rn"), col("fuel_pct")))
df_gps = (df_numbered.filter("sensor_type = 'GPS'")
    .select(col("rn"), col("latitude"), col("longitude")))
df_accel = (df_numbered.filter("sensor_type = 'ACCEL'")
    .select(col("rn"), col("accel_hex")))
df_battery = (df_numbered.filter("sensor_type = 'BATTERY'")
    .select(col("rn"), col("battery_hex")))

# Join all sensors on row number
df_pivoted = (df_speed
    .join(df_rpm, "rn")
    .join(df_fuel, "rn")
    .join(df_gps, "rn")
    .join(df_accel, "rn")
    .join(df_battery, "rn")
    .withColumn("event_time", (col("ts_ms") / 1000).cast("timestamp"))
    .select("ts_ms", "event_time", "speed_kmh", "rpm", "fuel_pct",
            "latitude", "longitude", "accel_hex", "battery_hex")
)

print(f"Pivoted records: {df_pivoted.count():,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Write to UC Managed Iceberg

# COMMAND ----------

target_table = f"{DB}.can_frames_decoded"

# Drop existing table and recreate as Managed Iceberg
spark.sql(f"DROP TABLE IF EXISTS {target_table}")
df_pivoted.write.format("iceberg").saveAsTable(target_table)
print(f"Wrote {df_pivoted.count():,} rows to {target_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Ingest vehicle_summary_1min

# COMMAND ----------

conn = psycopg2.connect(
    host=config["rw_host"],
    port=config["rw_port"],
    user=config["rw_user"],
    dbname=config["rw_db"]
)
cur = conn.cursor()

cur.execute("""
    SELECT window_start, window_end, sensor_type, frame_count,
           avg_speed_kmh, max_speed_kmh, avg_rpm, min_fuel_pct
    FROM vehicle_summary_1min
""")
rows_summary = cur.fetchall()
print(f"Fetched {len(rows_summary)} rows from vehicle_summary_1min")
cur.close()
conn.close()

# COMMAND ----------

schema_summary = StructType([
    StructField("window_start", TimestampType(), True),
    StructField("window_end", TimestampType(), True),
    StructField("sensor_type", StringType(), True),
    StructField("frame_count", LongType(), True),
    StructField("avg_speed_kmh", DoubleType(), True),
    StructField("max_speed_kmh", DoubleType(), True),
    StructField("avg_rpm", DoubleType(), True),
    StructField("min_fuel_pct", DoubleType(), True),
])

# Convert Decimal values to float for Spark compatibility
rows_converted = []
for row in rows_summary:
    converted = []
    for val in row:
        if isinstance(val, Decimal):
            converted.append(float(val))
        else:
            converted.append(val)
    rows_converted.append(tuple(converted))

df_summary = spark.createDataFrame(rows_converted, schema=schema_summary)

summary_target = f"{DB}.vehicle_summary_1min"
spark.sql(f"DROP TABLE IF EXISTS {summary_target}")
df_summary.write.format("iceberg").saveAsTable(summary_target)
print(f"Wrote {df_summary.count():,} rows to {summary_target}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Verification

# COMMAND ----------

print(f"=== {DB}.can_frames_decoded ===")
spark.sql(f"SELECT COUNT(*) as total FROM {DB}.can_frames_decoded").show()

print(f"=== {DB}.vehicle_summary_1min ===")
spark.sql(f"SELECT * FROM {DB}.vehicle_summary_1min ORDER BY window_start DESC").show(10)
