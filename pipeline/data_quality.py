"""Step 3 - Automated data quality checks.

Every check is a SQL query returning one number. Results are printed, saved to
reports/, and appended to a BigQuery table (dq_results) so data quality can be
tracked over time and shown on a Power BI page. The step exits non-zero if any
"error" check fails, so a scheduler would stop before bad data reaches reports.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
from google.cloud import bigquery

from pipeline import bq as bqh
from pipeline.config import settings

D = "`${project}.${dataset}"
R = "`${project}.${raw_dataset}"


@dataclass
class Check:
    name: str
    severity: str          # "error" stops the pipeline, "warn" only reports
    sql: str               # returns a single number
    passes: callable       # value -> bool
    rule: str              # human-readable rule, shown in reports


def checks() -> list[Check]:
    months = ", ".join(f"'{m}'" for m in settings.months)
    return [
        Check("fact_has_rows", "error",
              f"SELECT COUNT(*) FROM {D}.fact_trips`",
              lambda v: v > 0, "fact_trips is not empty"),
        Check("raw_to_staging_reconciles", "error",
              f"""SELECT (SELECT COUNT(*) FROM {R}.yellow_trips_*`)
                       - (SELECT COUNT(*) FROM {D}.stg_trips`)""",
              lambda v: v >= 0, "staging never has more rows than raw (difference = duplicates removed)"),
        Check("staging_to_fact_reconciles", "error",
              f"""SELECT (SELECT COUNTIF(dq_issue IS NULL) FROM {D}.stg_trips`)
                       - (SELECT COUNT(*) FROM {D}.fact_trips`)""",
              lambda v: v == 0, "every clean staging row lands in fact_trips exactly once"),
        Check("duplicate_trip_ids", "error",
              f"SELECT COUNT(*) - COUNT(DISTINCT trip_id) FROM {D}.fact_trips`",
              lambda v: v == 0, "trip_id is unique"),
        Check("null_keys", "error",
              f"""SELECT COUNTIF(pickup_date_key IS NULL OR pickup_zone_key IS NULL
                                 OR dropoff_zone_key IS NULL) FROM {D}.fact_trips`""",
              lambda v: v == 0, "no NULL foreign keys"),
        Check("orphan_zones", "error",
              f"""SELECT COUNT(*) FROM {D}.fact_trips` f
                  LEFT JOIN {D}.dim_zone` p ON p.zone_key = f.pickup_zone_key
                  LEFT JOIN {D}.dim_zone` d ON d.zone_key = f.dropoff_zone_key
                  WHERE p.zone_key IS NULL OR d.zone_key IS NULL""",
              lambda v: v == 0, "every zone key exists in dim_zone"),
        Check("orphan_payment_types", "error",
              f"""SELECT COUNT(*) FROM {D}.fact_trips` f
                  LEFT JOIN {D}.dim_payment_type` p USING (payment_type_key)
                  WHERE p.payment_type_name IS NULL""",
              lambda v: v == 0, "every payment type exists in dim_payment_type"),
        Check("orphan_dates", "error",
              f"""SELECT COUNT(*) FROM {D}.fact_trips` f
                  LEFT JOIN {D}.dim_date` d ON d.date_key = f.pickup_date_key
                  WHERE d.date_key IS NULL""",
              lambda v: v == 0, "every pickup date exists in dim_date"),
        Check("all_months_present", "error",
              f"""SELECT COUNT(*) FROM UNNEST([{months}]) m
                  WHERE m NOT IN (SELECT DISTINCT FORMAT_DATETIME('%Y-%m', pickup_dt)
                                  FROM {D}.fact_trips`)""",
              lambda v: v == 0, "every configured month has data"),
        Check("excluded_row_pct", "warn",
              f"SELECT ROUND(100 * SAFE_DIVIDE(COUNTIF(dq_issue IS NOT NULL), COUNT(*)), 2) FROM {D}.stg_trips`",
              lambda v: v is not None and v <= 10, "no more than 10% of rows fail quality rules"),
        Check("tip_exceeds_fare_pct", "warn",
              f"""SELECT ROUND(100 * COUNTIF(tip_pct > 1) / NULLIF(COUNTIF(tip_pct IS NOT NULL), 0), 2)
                  FROM {D}.fact_trips`""",
              lambda v: v is None or v <= 2, "no more than 2% of card trips tip over 100% of fare"),
    ]


def issue_breakdown(bq: bigquery.Client) -> pd.DataFrame:
    return bqh.to_df(bq, f"""
        SELECT COALESCE(dq_issue, 'clean') AS dq_issue, COUNT(*) AS row_count,
               ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
        FROM {D}.stg_trips` GROUP BY 1 ORDER BY row_count DESC""")


def main() -> None:
    bq = bqh.client()
    run_at = datetime.now(timezone.utc)
    print("Data quality")

    results = []
    for c in checks():
        print(f"  {c.name}")
        value = bqh.scalar(bq, c.sql)
        value = float(value) if value is not None else None
        ok = bool(c.passes(value))
        results.append({"run_at": run_at, "check_name": c.name, "severity": c.severity,
                        "rule": c.rule, "value": value, "passed": ok})

    df = pd.DataFrame(results)
    breakdown = issue_breakdown(bq)

    settings.reports_dir.mkdir(exist_ok=True)
    df.to_csv(settings.reports_dir / "dq_results.csv", index=False)
    breakdown.to_csv(settings.reports_dir / "dq_issue_breakdown.csv", index=False)

    bq.load_table_from_dataframe(
        df, f"{settings.project_id}.{settings.dataset}.dq_results",
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"),
    ).result()

    print("\n" + df[["check_name", "severity", "value", "passed"]].to_string(index=False))
    print("\nRows by quality issue:\n" + breakdown.to_string(index=False))

    failed = df[(~df.passed) & (df.severity == "error")]
    if not failed.empty:
        print(f"\nFAILED: {', '.join(failed.check_name)}")
        sys.exit(1)
    print("\nAll error-level checks passed.")


if __name__ == "__main__":
    main()
