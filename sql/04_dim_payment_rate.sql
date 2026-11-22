-- Small code-lookup dimensions, from the TLC Yellow Taxi data dictionary.
CREATE OR REPLACE TABLE `${project}.${dataset}.dim_payment_type` AS
SELECT * FROM UNNEST([
  STRUCT(0 AS payment_type_key, 'Flex fare' AS payment_type_name),
  (1, 'Credit card'),
  (2, 'Cash'),
  (3, 'No charge'),
  (4, 'Dispute'),
  (5, 'Unknown'),
  (6, 'Voided trip')
]);

CREATE OR REPLACE TABLE `${project}.${dataset}.dim_rate_code` AS
SELECT * FROM UNNEST([
  STRUCT(1 AS rate_code_key, 'Standard rate' AS rate_code_name),
  (2, 'JFK'),
  (3, 'Newark'),
  (4, 'Nassau or Westchester'),
  (5, 'Negotiated fare'),
  (6, 'Group ride'),
  (99, 'Unknown')
]);
