-- Staging: combine monthly raw tables, fix types, remove exact duplicates,
-- derive trip duration, and tag (not drop) every row that fails a quality rule.
-- Tagging instead of dropping lets us report exactly what was excluded and why.
-- Clustered, not partitioned: the BigQuery sandbox deletes partitions older than
-- 60 days, and this historical data is older than that.
-- Drop first, because BigQuery can't replace a table with a different partitioning spec.
DROP TABLE IF EXISTS `${project}.${dataset}.stg_trips`;

CREATE OR REPLACE TABLE `${project}.${dataset}.stg_trips`
CLUSTER BY pu_location_id
AS
WITH unioned AS (
  SELECT
    * EXCEPT (pickup_ts, dropoff_ts),
    -- Raw files hold NY wall-clock time stored as if UTC, so convert back to DATETIME.
    CAST(pickup_ts  AS DATETIME) AS pickup_dt,
    CAST(dropoff_ts AS DATETIME) AS dropoff_dt
  FROM `${project}.${raw_dataset}.yellow_trips_*`
),
deduped AS (
  SELECT *
  FROM unioned
  QUALIFY ROW_NUMBER() OVER (
    -- BigQuery can't partition by FLOAT64, so compare the decimal columns as text.
    PARTITION BY vendor_id, pickup_dt, dropoff_dt, pu_location_id, do_location_id,
                 CAST(trip_distance AS STRING), CAST(total_amount AS STRING)
    ORDER BY payment_type
  ) = 1
)
SELECT
  GENERATE_UUID() AS trip_id,
  source_month,
  vendor_id,
  pickup_dt,
  dropoff_dt,
  DATETIME_DIFF(dropoff_dt, pickup_dt, SECOND) / 60.0 AS trip_minutes,
  pu_location_id,
  do_location_id,
  passenger_count,
  trip_distance,
  ratecode_id,
  payment_type,
  store_and_fwd_flag,
  fare_amount,
  extra,
  mta_tax,
  tip_amount,
  tolls_amount,
  improvement_surcharge,
  congestion_surcharge,
  airport_fee,
  total_amount,
  CASE
    WHEN pickup_dt IS NULL OR dropoff_dt IS NULL                  THEN 'missing_timestamp'
    WHEN FORMAT_DATETIME('%Y-%m', pickup_dt) != source_month      THEN 'out_of_period'
    WHEN dropoff_dt <= pickup_dt                                  THEN 'non_positive_duration'
    WHEN DATETIME_DIFF(dropoff_dt, pickup_dt, MINUTE) > 360       THEN 'duration_over_6h'
    WHEN trip_distance IS NULL OR trip_distance <= 0              THEN 'zero_distance'
    WHEN trip_distance > 200                                      THEN 'distance_over_200mi'
    WHEN fare_amount < 0 OR total_amount < 0                      THEN 'negative_amount'
    WHEN pu_location_id IS NULL OR do_location_id IS NULL         THEN 'missing_location'
    ELSE NULL
  END AS dq_issue
FROM deduped;
