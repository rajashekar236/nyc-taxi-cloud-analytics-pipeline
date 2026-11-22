-- Date dimension covering every day that appears in the clean data.
CREATE OR REPLACE TABLE `${project}.${dataset}.dim_date` AS
WITH bounds AS (
  SELECT MIN(DATE(pickup_dt)) AS min_d, MAX(DATE(pickup_dt)) AS max_d
  FROM `${project}.${dataset}.stg_trips`
  WHERE dq_issue IS NULL
)
SELECT
  CAST(FORMAT_DATE('%Y%m%d', d) AS INT64)  AS date_key,
  d                                        AS full_date,
  EXTRACT(YEAR FROM d)                     AS year,
  EXTRACT(QUARTER FROM d)                  AS quarter,
  EXTRACT(MONTH FROM d)                    AS month,
  FORMAT_DATE('%B', d)                     AS month_name,
  FORMAT_DATE('%Y-%m', d)                  AS year_month,
  EXTRACT(DAY FROM d)                      AS day_of_month,
  EXTRACT(DAYOFWEEK FROM d)                AS day_of_week,   -- 1 = Sunday
  FORMAT_DATE('%A', d)                     AS day_name,
  EXTRACT(DAYOFWEEK FROM d) IN (1, 7)      AS is_weekend
FROM bounds, UNNEST(GENERATE_DATE_ARRAY(min_d, max_d)) AS d;
