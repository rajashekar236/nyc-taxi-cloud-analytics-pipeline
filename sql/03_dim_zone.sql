-- Zone dimension. Used twice by the fact table (pickup zone and dropoff zone).
CREATE OR REPLACE TABLE `${project}.${dataset}.dim_zone` AS
SELECT
  location_id                     AS zone_key,
  -- The source file uses "N/A" for trips that end outside the city.
  IF(borough = 'N/A', 'Outside NYC', borough)  AS borough,
  IF(zone = 'N/A', 'Unknown', zone)            AS zone_name,
  service_zone,
  location_id IN (1, 132, 138)    AS is_airport   -- Newark, JFK, LaGuardia
FROM `${project}.${raw_dataset}.taxi_zones`;
