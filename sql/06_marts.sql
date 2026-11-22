-- Pre-aggregated tables for Power BI. Small, fast to import, cheap to refresh.
CREATE OR REPLACE TABLE `${project}.${dataset}.mart_daily_kpis` AS
SELECT
  f.pickup_date_key                                   AS date_key,
  COUNT(*)                                            AS trips,
  SUM(f.total_amount)                                 AS revenue,
  AVG(f.fare_amount)                                  AS avg_fare,
  AVG(f.trip_distance)                                AS avg_distance_mi,
  AVG(f.trip_minutes)                                 AS avg_minutes,
  COUNTIF(f.payment_type_key = 1)                     AS card_trips,
  SAFE_DIVIDE(SUM(IF(f.payment_type_key = 1, f.tip_amount, 0)),
              SUM(IF(f.payment_type_key = 1, f.fare_amount, 0))) AS card_tip_rate
FROM `${project}.${dataset}.fact_trips` f
GROUP BY date_key;

CREATE OR REPLACE TABLE `${project}.${dataset}.mart_zone_hour_kpis` AS
SELECT
  z.borough,
  z.zone_name,
  d.day_name,
  d.day_of_week,
  d.is_weekend,
  f.pickup_hour,
  COUNT(*)                     AS trips,
  SUM(f.total_amount)          AS revenue,
  AVG(f.trip_minutes)          AS avg_minutes,
  AVG(f.tip_pct)               AS avg_card_tip_pct
FROM `${project}.${dataset}.fact_trips` f
JOIN `${project}.${dataset}.dim_zone` z ON z.zone_key = f.pickup_zone_key
JOIN `${project}.${dataset}.dim_date` d ON d.date_key = f.pickup_date_key
GROUP BY 1, 2, 3, 4, 5, 6;
