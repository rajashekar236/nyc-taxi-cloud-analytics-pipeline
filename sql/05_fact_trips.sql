-- Fact table: one row per clean trip, with foreign keys into every dimension.
-- Clustered, not partitioned (see 01_stg_trips.sql for why).
DROP TABLE IF EXISTS `${project}.${dataset}.fact_trips`;

CREATE OR REPLACE TABLE `${project}.${dataset}.fact_trips`
CLUSTER BY pickup_date_key, pickup_zone_key, payment_type_key
AS
SELECT
  trip_id,
  CAST(FORMAT_DATE('%Y%m%d', DATE(pickup_dt)) AS INT64) AS pickup_date_key,
  EXTRACT(HOUR FROM pickup_dt)                          AS pickup_hour,
  pickup_dt,
  dropoff_dt,
  pu_location_id                AS pickup_zone_key,
  do_location_id                AS dropoff_zone_key,
  COALESCE(payment_type, 5)     AS payment_type_key,
  COALESCE(ratecode_id, 99)     AS rate_code_key,
  vendor_id,
  passenger_count,
  trip_distance,
  trip_minutes,
  fare_amount,
  tip_amount,
  tolls_amount,
  congestion_surcharge,
  airport_fee,
  total_amount,
  -- Tips are only recorded for card payments, so tip % is NULL for everything else.
  IF(payment_type = 1 AND fare_amount > 0, tip_amount / fare_amount, NULL) AS tip_pct
FROM `${project}.${dataset}.stg_trips`
WHERE dq_issue IS NULL;
