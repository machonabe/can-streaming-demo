-- ============================================================
-- RisingWave Pipeline: Kinesis -> MV (CAN Decode) -> Iceberg Sink
-- Auto-generated from Terraform template
-- ============================================================

-- 1. Kinesis Source
CREATE SOURCE IF NOT EXISTS kinesis_can_source (
    payload BYTEA,
    processed_at TIMESTAMPTZ AS proctime()
)
WITH (
    connector = 'kinesis',
    stream     = '${kinesis_stream_name}',
    aws.region = '${aws_region}',
    scan.startup.mode = 'earliest'
)
FORMAT PLAIN ENCODE BYTES;

-- 2. CAN Binary Decode Materialized View
CREATE MATERIALIZED VIEW IF NOT EXISTS can_frames_decoded AS
SELECT
    -- Timestamp (first 8 bytes)
    (get_byte(payload, 0)::BIGINT << 56) |
    (get_byte(payload, 1)::BIGINT << 48) |
    (get_byte(payload, 2)::BIGINT << 40) |
    (get_byte(payload, 3)::BIGINT << 32) |
    (get_byte(payload, 4)::BIGINT << 24) |
    (get_byte(payload, 5)::BIGINT << 16) |
    (get_byte(payload, 6)::BIGINT << 8)  |
    get_byte(payload, 7)::BIGINT
        AS ts_ms,

    -- CAN ID (bytes 8-9)
    ((get_byte(payload, 8)::INT << 8) | get_byte(payload, 9)::INT)
        AS can_id,

    to_hex((get_byte(payload, 8)::INT << 8) | get_byte(payload, 9)::INT)
        AS can_id_hex,

    CASE ((get_byte(payload, 8)::INT << 8) | get_byte(payload, 9)::INT)
        WHEN 176  THEN 'SPEED'
        WHEN 192  THEN 'RPM'
        WHEN 416  THEN 'FUEL'
        WHEN 768  THEN 'GPS'
        WHEN 1024 THEN 'ACCEL'
        WHEN 1280 THEN 'BATTERY'
        ELSE 'UNKNOWN'
    END AS sensor_type,

    encode(substring(payload from 12 for 8), 'hex') AS data_hex,

    CASE ((get_byte(payload, 8)::INT << 8) | get_byte(payload, 9)::INT)
        WHEN 176 THEN
            ROUND(((get_byte(payload, 11)::INT << 8) |
                    get_byte(payload, 12)::INT)::NUMERIC / 100.0, 2)::TEXT
        ELSE NULL
    END AS speed_kmh,

    CASE ((get_byte(payload, 8)::INT << 8) | get_byte(payload, 9)::INT)
        WHEN 192 THEN
            ROUND(((get_byte(payload, 11)::INT << 8) |
                    get_byte(payload, 12)::INT)::NUMERIC / 4.0, 0)::TEXT
        ELSE NULL
    END AS rpm,

    CASE ((get_byte(payload, 8)::INT << 8) | get_byte(payload, 9)::INT)
        WHEN 416 THEN
            ROUND(get_byte(payload, 11)::NUMERIC / 2.55, 1)::TEXT
        ELSE NULL
    END AS fuel_pct,

    CASE ((get_byte(payload, 8)::INT << 8) | get_byte(payload, 9)::INT)
        WHEN 768 THEN
            ROUND(
                ((get_byte(payload, 11)::BIGINT << 24) |
                 (get_byte(payload, 12)::BIGINT << 16) |
                 (get_byte(payload, 13)::BIGINT << 8)  |
                  get_byte(payload, 14)::BIGINT
                )::NUMERIC / 1e5 - 90, 5
            )::TEXT
        ELSE NULL
    END AS latitude,

    CASE ((get_byte(payload, 8)::INT << 8) | get_byte(payload, 9)::INT)
        WHEN 768 THEN
            ROUND(
                ((get_byte(payload, 15)::BIGINT << 24) |
                 (get_byte(payload, 16)::BIGINT << 16) |
                 (get_byte(payload, 17)::BIGINT << 8)  |
                  get_byte(payload, 18)::BIGINT
                )::NUMERIC / 1e5 - 180, 5
            )::TEXT
        ELSE NULL
    END AS longitude,

    to_hex(get_byte(payload, 19)) AS crc_hex,

    processed_at

FROM kinesis_can_source;

-- 3. 1-Minute Aggregation Materialized View
CREATE MATERIALIZED VIEW IF NOT EXISTS vehicle_summary_1min AS
SELECT
    window_start,
    window_end,
    sensor_type,
    COUNT(*)                        AS frame_count,
    AVG(speed_kmh::NUMERIC)         AS avg_speed_kmh,
    MAX(speed_kmh::NUMERIC)         AS max_speed_kmh,
    AVG(rpm::NUMERIC)               AS avg_rpm,
    MIN(fuel_pct::NUMERIC)          AS min_fuel_pct
FROM TUMBLE(
    can_frames_decoded,
    processed_at,
    INTERVAL '1 MINUTE'
)
WHERE sensor_type IN ('SPEED', 'RPM', 'FUEL')
GROUP BY window_start, window_end, sensor_type;

-- 4. Iceberg Sink (decoded - append-only)
CREATE SINK IF NOT EXISTS iceberg_sink_decoded
FROM can_frames_decoded
WITH (
    connector             = 'iceberg',
    type                  = 'append-only',
    catalog.type          = 'storage',
    warehouse.path        = 's3://${s3_bucket}/${s3_prefix}',
    database.name         = '${uc_schema_name}',
    table.name            = 'can_frames_decoded',
    s3.region             = '${aws_region}',
    s3.endpoint           = 'https://s3.${aws_region}.amazonaws.com',
    create_table_if_not_exists = 'true',
    commit_checkpoint_interval = '10'
);

-- 5. Iceberg Sink (summary - upsert)
CREATE SINK IF NOT EXISTS iceberg_sink_summary
FROM vehicle_summary_1min
WITH (
    connector             = 'iceberg',
    type                  = 'upsert',
    primary_key           = 'window_start,sensor_type',
    catalog.type          = 'storage',
    warehouse.path        = 's3://${s3_bucket}/${s3_prefix}',
    database.name         = '${uc_schema_name}',
    table.name            = 'vehicle_summary_1min',
    s3.region             = '${aws_region}',
    s3.endpoint           = 'https://s3.${aws_region}.amazonaws.com',
    create_table_if_not_exists = 'true',
    commit_checkpoint_interval = '20'
);
