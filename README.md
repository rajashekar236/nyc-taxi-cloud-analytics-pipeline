# NYC Taxi Cloud Analytics Pipeline

An end-to-end **ELT pipeline on Google Cloud** that loads millions of NYC Yellow Taxi
trips into a **BigQuery star-schema data warehouse**, runs **automated data quality
checks**, tests hypotheses about rider tipping with **statistical analysis**, and serves a
**Power BI** dashboard.

**Stack:** Python (pandas, SciPy, statsmodels) · Google Cloud (BigQuery, SQL) · Power BI (DAX)

![Executive overview dashboard](docs/dashboard_overview.png)

---

## Architecture

```mermaid
flowchart LR
    A[NYC TLC public files<br/>Parquet, ~3M rows/month] -->|Python: download + normalize schema| B[Cloud Storage<br/>optional raw data lake]
    B -->|Load jobs| C[BigQuery taxi_raw<br/>one table per month]
    C -->|SQL transforms| D[stg_trips<br/>dedupe + quality tags]
    D --> E[Star schema<br/>fact_trips + 4 dimensions]
    E --> F[Marts<br/>daily + zone/hour KPIs]
    E --> G[Data quality checks<br/>dq_results]
    E --> H[Python statistics<br/>t-tests + regression]
    F --> I[Power BI dashboard]
    G --> I
```

## Data model

```mermaid
erDiagram
    fact_trips }o--|| dim_date : pickup_date_key
    fact_trips }o--|| dim_zone : pickup_zone_key
    fact_trips }o--|| dim_zone : dropoff_zone_key
    fact_trips }o--|| dim_payment_type : payment_type_key
    fact_trips }o--|| dim_rate_code : rate_code_key
    fact_trips {
        string trip_id PK
        int pickup_date_key FK
        int pickup_hour
        int pickup_zone_key FK
        int dropoff_zone_key FK
        int payment_type_key FK
        float trip_distance
        float trip_minutes
        float fare_amount
        float tip_amount
        float total_amount
        float tip_pct
    }
```

`fact_trips` is clustered by pickup date, zone and payment type, so typical dashboard
queries read only the blocks they need. It is deliberately *not* partitioned: the
BigQuery sandbox deletes partitions older than 60 days, which would wipe out this
historical data. On a billed project, monthly partitioning would be the next step.

## Design decisions

| Decision | Why |
|---|---|
| **ELT, not ETL** | Python only normalizes schema; all business logic is version-controlled SQL running inside BigQuery, which scales without extra infrastructure. |
| **Schema normalization on ingest** | The TLC renames and retypes columns between years (`Airport_fee` vs `airport_fee`, float vs int). Normalizing first keeps monthly tables compatible. |
| **One raw table per month** | Reloading a month replaces only that month (idempotent), with no DML needed. |
| **Tag bad rows, don't silently drop them** | Each staging row gets a `dq_issue` reason, so excluded data is fully accounted for and reported. |
| **Bytes-billed guardrail** | Every query has a hard scan limit (`MAX_BYTES_BILLED`), so a bad query fails instead of costing money. |
| **Effect sizes, not just p-values** | With millions of rows nearly everything is "significant". Cohen's d shows whether a difference actually matters. |

## Results

Run on January–March 2024. Full outputs are in [`reports/`](reports/).

- **Volume:** 9.55M raw trips loaded → **9.21M clean trips** in the star schema
- **Data quality:** all 9 error-level checks pass; **3.64%** of rows excluded by 8 rules,
  each with a recorded reason (top issues: zero distance 2.23%, negative amounts / refunds 1.32%)
- **Weekend effect is real but negligible:** weekend riders tip 0.79 pts less (p < 0.001),
  but Cohen's d = 0.07. Statistically significant, not practically meaningful.
- **Airport trips reverse once you control for trip length:** on average they tip 3.8 pts
  *less*, but holding distance and duration constant they tip **6.8 pts more**. The raw
  gap comes from airport trips being long, and tip % falls as trips get longer.
- **Location matters most:** compared with Manhattan pickups, tips are 13.6 pts lower for
  Bronx pickups and 10.2 pts lower for Brooklyn (regression, n = 717,661, robust SEs)
- **Weekday evening rush tips highest** (+2.1 pts vs midday). See `reports/tip_pct_by_hour.png`.
- **Dashboard:** 4-page Power BI report (Executive Overview, When People Ride, Where People
  Ride, Data Quality) on the star schema, with 11 DAX measures including time intelligence
  (month-over-month) and a role-playing zone dimension (`USERELATIONSHIP` for dropoffs)

## Dashboard

**When people ride:** demand by day and hour, and how tipping changes through the day

![When people ride](docs/dashboard_when.png)

**Where people ride:** top pickup and dropoff zones, and airport vs non-airport trips

![Where people ride](docs/dashboard_where.png)

**Data quality:** results of the latest pipeline run's automated checks

![Data quality](docs/dashboard_quality.png)

---

## Project layout

```
pipeline/    extract_load.py    download, normalize schema, load into BigQuery
             transform.py       runs the sql/ files in order
             data_quality.py    11 automated checks -> dq_results table
sql/         01 staging · 02-04 dimensions · 05 fact · 06 marts
analysis/    stats_analysis.py  hypothesis tests + regression
reports/     results from the latest run (quality checks, statistics, charts)
dashboard/   NYC_Taxi_Dashboard.pbix (open in Power BI Desktop)
docs/        dashboard screenshots + Power BI build guide
tests/       offline unit tests
```

<details>
<summary><b>Run it yourself</b> (about 15 minutes, free BigQuery sandbox)</summary>

<br>

**You need:** Python 3.12, the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install),
and a Google Cloud project. The free [BigQuery sandbox](https://cloud.google.com/bigquery/docs/sandbox)
works without a billing account (note that sandbox tables expire after 60 days).

**1. Sign in to Google Cloud**

```
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR-PROJECT-ID
```

**2. Install**

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `GCP_PROJECT_ID`. Leave `GCS_BUCKET` empty on the sandbox.
(On macOS/Linux, use `python3.12`, `.venv/bin/python` and `cp`.)

**3. Run**

```
.venv\Scripts\python -m pytest -q          # offline tests, no cloud needed
.venv\Scripts\python run_pipeline.py       # load -> transform -> quality checks -> analysis
```

Run individual steps with `--steps`, for example `run_pipeline.py --steps transform dq`.

**4. Dashboard:** open `dashboard/NYC_Taxi_Dashboard.pbix`, or rebuild it with
[docs/powerbi_guide.md](docs/powerbi_guide.md).

</details>

## Next steps

- Schedule the pipeline with **Cloud Composer (Airflow)**, using one task per step.
- Move transforms to **dbt** for lineage graphs and built-in tests.
- Stream new data with **Dataflow** instead of monthly batch loads.
