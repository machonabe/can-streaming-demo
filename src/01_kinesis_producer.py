# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # 01. CAN Data Generation -> Kinesis
# MAGIC
# MAGIC ## Overview
# MAGIC Generates simulated Honda CAN bus binary data and sends it to AWS Kinesis.
# MAGIC
# MAGIC ## Scale
# MAGIC - 1 frame = 20B (8B timestamp + 12B CAN frame)
# MAGIC - 6 sensors x 10Hz x 1M vehicles x 86,400s = **~1TB/day**
# MAGIC - Demo uses reduced vehicle count and duration
# MAGIC
# MAGIC ## CAN Frame Structure
# MAGIC | Offset | Size | Field |
# MAGIC |--------|------|-------|
# MAGIC | 0-7    | 8B   | Timestamp (ms) |
# MAGIC | 8-9    | 2B   | CAN ID |
# MAGIC | 10     | 1B   | DLC (data length) |
# MAGIC | 11-18  | 8B   | DATA |
# MAGIC | 19     | 1B   | CRC (XOR) |

# COMMAND ----------

# MAGIC %run ./00_setup

# COMMAND ----------

import struct
import time
import random
import math
import json
import boto3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# COMMAND ----------

# MAGIC %md
# MAGIC ## CAN ID Definitions and Encoders

# COMMAND ----------

CAN_IDS = {
    "SPEED":   0x0B0,
    "RPM":     0x0C0,
    "FUEL":    0x1A0,
    "GPS":     0x300,
    "ACCEL":   0x400,
    "BATTERY": 0x500,
}


def build_can_frame(can_id: int, data: bytes) -> bytes:
    """Build a 12-byte CAN frame: [ID:2][DLC:1][DATA:8][CRC:1]"""
    assert len(data) <= 8
    data_padded = data.ljust(8, b'\x00')
    header = struct.pack(">HB", can_id, 8)
    frame = header + data_padded
    crc = 0
    for b in frame:
        crc ^= b
    return frame + bytes([crc])


def encode_speed(kmh: float) -> bytes:
    return struct.pack(">H6x", int(kmh * 100))


def encode_rpm(rpm: float) -> bytes:
    return struct.pack(">H6x", int(rpm * 4))


def encode_fuel(pct: float) -> bytes:
    return struct.pack(">B7x", int(pct * 2.55))


def encode_gps(lat: float, lon: float) -> bytes:
    lat_raw = int((lat + 90) * 1e5)
    lon_raw = int((lon + 180) * 1e5)
    return struct.pack(">II", lat_raw, lon_raw)


def encode_accel(x: float, y: float, z: float) -> bytes:
    return struct.pack(">hhh2x",
                       int((x + 8) * 1000),
                       int((y + 8) * 1000),
                       int((z + 8) * 1000))


def encode_battery(voltage: float, soc: float) -> bytes:
    return struct.pack(">HB5x", int(voltage * 100), int(soc))

# COMMAND ----------

# MAGIC %md
# MAGIC ## CAN Record Generator

# COMMAND ----------

def generate_can_record(vin: str, state: dict) -> list:
    """Generate all sensor frames for one vehicle at one timestep."""
    ts = int(time.time() * 1000)
    ts_bytes = struct.pack(">Q", ts)

    # Random walk state updates
    state["speed"] = max(0, min(180, state["speed"] + random.gauss(0, 2)))
    state["rpm"] = max(700, min(7000, state["rpm"] + random.gauss(0, 100)))
    state["fuel"] = max(0, state["fuel"] - 0.0001)
    state["lat"] += random.gauss(0, 0.0001)
    state["lon"] += random.gauss(0, 0.0001)
    state["battery"] = 12.4 + random.gauss(0, 0.1)
    state["soc"] = max(0, state["soc"] - 0.001)

    frames = [
        (CAN_IDS["SPEED"],   encode_speed(state["speed"])),
        (CAN_IDS["RPM"],     encode_rpm(state["rpm"])),
        (CAN_IDS["FUEL"],    encode_fuel(state["fuel"])),
        (CAN_IDS["GPS"],     encode_gps(state["lat"], state["lon"])),
        (CAN_IDS["ACCEL"],   encode_accel(
            random.gauss(0, 0.5),
            random.gauss(0, 0.5),
            9.8 + random.gauss(0, 0.1))),
        (CAN_IDS["BATTERY"], encode_battery(state["battery"], state["soc"])),
    ]

    records = []
    for can_id, data in frames:
        frame_bytes = ts_bytes + build_can_frame(can_id, data)
        records.append({
            "Data": frame_bytes,
            "PartitionKey": vin,
        })
    return records

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Kinesis Stream (if not exists)

# COMMAND ----------

kinesis_kwargs = {"region_name": config["aws_region"]}
if aws_access_key and aws_secret_key:
    kinesis_kwargs["aws_access_key_id"] = aws_access_key
    kinesis_kwargs["aws_secret_access_key"] = aws_secret_key
    if aws_session_token:
        kinesis_kwargs["aws_session_token"] = aws_session_token

kinesis = boto3.client("kinesis", **kinesis_kwargs)

try:
    kinesis.create_stream(
        StreamName=config["kinesis_stream_name"],
        ShardCount=config["kinesis_shard_count"]
    )
    print(f"Kinesis stream created: {config['kinesis_stream_name']}")
    waiter = kinesis.get_waiter("stream_exists")
    waiter.wait(
        StreamName=config["kinesis_stream_name"],
        WaiterConfig={"Delay": 5, "MaxAttempts": 12}
    )
    print("  Stream is now ACTIVE")
except kinesis.exceptions.ResourceInUseException:
    print(f"Using existing stream: {config['kinesis_stream_name']}")
except Exception as e:
    print(f"ERROR creating Kinesis stream: {e}")
    raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo Producer (multi-threaded)
# MAGIC Adjust `DEMO_VEHICLES` and `DEMO_DURATION_SEC` for your scale.

# COMMAND ----------

DEMO_VEHICLES = 1000
DEMO_DURATION_SEC = 300

# Initialize vehicles with random state
vehicles = {}
for i in range(DEMO_VEHICLES):
    vin = f"1HGBH41JXMN{i:06d}"
    vehicles[vin] = {
        "speed": random.uniform(0, 120),
        "rpm": random.uniform(700, 3000),
        "fuel": random.uniform(20, 100),
        "lat": 35.681 + random.gauss(0, 0.5),
        "lon": 139.767 + random.gauss(0, 0.5),
        "battery": 12.4,
        "soc": random.uniform(60, 100),
    }

print(f"Vehicles initialized: {DEMO_VEHICLES}")


def produce_batch(vin_batch: list):
    """Put a batch of records to Kinesis."""
    all_records = []
    for vin in vin_batch:
        all_records.extend(generate_can_record(vin, vehicles[vin]))

    for i in range(0, len(all_records), 500):
        chunk = all_records[i:i + 500]
        try:
            resp = kinesis.put_records(
                StreamName=config["kinesis_stream_name"],
                Records=chunk
            )
            failed = resp.get("FailedRecordCount", 0)
            if failed > 0:
                print(f"  WARNING: {failed} records failed to PUT")
        except Exception as e:
            print(f"  ERROR: PutRecords failed: {e}")

# COMMAND ----------

start = time.time()
total_records = 0

print(f"Producer started: {DEMO_VEHICLES} vehicles x {DEMO_DURATION_SEC}s")
print(f"  Expected frames: {DEMO_VEHICLES * 6 * DEMO_DURATION_SEC * 10:,}")
print("-" * 55)

vin_list = list(vehicles.keys())

while time.time() - start < DEMO_DURATION_SEC:
    with ThreadPoolExecutor(max_workers=8) as ex:
        chunk_size = max(1, len(vin_list) // 8)
        futures = [
            ex.submit(produce_batch, vin_list[i:i + chunk_size])
            for i in range(0, len(vin_list), chunk_size)
        ]
        for f in futures:
            f.result()

    total_records += DEMO_VEHICLES * 6
    elapsed = time.time() - start
    throughput_mb = (total_records * 20) / 1024 / 1024
    print(f"  [{elapsed:>6.0f}s] Total: {total_records:>12,} records / {throughput_mb:>8.1f} MB")
    time.sleep(0.1)

print("-" * 55)
print(f"Done: {total_records:,} frames sent ({elapsed:.0f}s)")
print(f"  Avg throughput: {total_records / elapsed:,.0f} rec/sec")
