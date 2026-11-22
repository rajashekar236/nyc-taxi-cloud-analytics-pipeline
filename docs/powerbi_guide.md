# Power BI dashboard guide

## 1. Connect to BigQuery

1. Open **Power BI Desktop** → **Get Data** → search **Google BigQuery** → Connect.
2. Sign in with the Google account that owns the project.
3. Expand your project → `taxi_analytics`, then select:
   - `fact_trips`, `dim_date`, `dim_zone`, `dim_payment_type`, `dim_rate_code`
   - `mart_zone_hour_kpis`, `dq_results`
4. Choose **Import**, not DirectQuery. Import is faster and doesn't run a BigQuery query
   every time someone clicks a visual.

> **Keeping the file small:** in Power Query, remove `trip_id`, `pickup_dt` and `dropoff_dt`
> from `fact_trips` before loading. You don't need them for visuals, and they're the
> largest columns.

## 2. Model (star schema)

In **Model view**, create these relationships (all many-to-one, single direction):

| From (fact_trips) | To | Active? |
|---|---|---|
| `pickup_date_key` | `dim_date[date_key]` | Yes |
| `pickup_zone_key` | `dim_zone[zone_key]` | Yes |
| `dropoff_zone_key` | `dim_zone[zone_key]` | **No** (inactive, used through `USERELATIONSHIP`) |
| `payment_type_key` | `dim_payment_type[payment_type_key]` | Yes |
| `rate_code_key` | `dim_rate_code[rate_code_key]` | Yes |

Then select `dim_date` → **Mark as date table** → `full_date`.

## 3. DAX measures

Create a blank table called `_Measures` to hold these:

```DAX
Total Trips = COUNTROWS ( fact_trips )

Total Revenue = SUM ( fact_trips[total_amount] )

Avg Fare = AVERAGE ( fact_trips[fare_amount] )

Avg Trip Minutes = AVERAGE ( fact_trips[trip_minutes] )

Card Tip Rate =
DIVIDE (
    CALCULATE ( SUM ( fact_trips[tip_amount] ),  dim_payment_type[payment_type_name] = "Credit card" ),
    CALCULATE ( SUM ( fact_trips[fare_amount] ), dim_payment_type[payment_type_name] = "Credit card" )
)

Trips Prior Month =
CALCULATE ( [Total Trips], DATEADD ( dim_date[full_date], -1, MONTH ) )

Trips MoM % = DIVIDE ( [Total Trips] - [Trips Prior Month], [Trips Prior Month] )

Airport Trip Share =
DIVIDE ( CALCULATE ( [Total Trips], dim_zone[is_airport] = TRUE () ), [Total Trips] )

Trips by Dropoff Zone =
CALCULATE ( [Total Trips], USERELATIONSHIP ( fact_trips[dropoff_zone_key], dim_zone[zone_key] ) )

DQ Checks Passed % =
VAR LatestRun = MAX ( dq_results[run_at] )
RETURN
DIVIDE (
    CALCULATE ( COUNTROWS ( dq_results ), dq_results[run_at] = LatestRun, dq_results[passed] = TRUE () ),
    CALCULATE ( COUNTROWS ( dq_results ), dq_results[run_at] = LatestRun )
)
```

## 4. Pages

**Page 1: Executive overview**
- KPI cards: Total Trips, Total Revenue, Avg Fare, Card Tip Rate, Trips MoM %
- Line chart: Total Trips by `dim_date[full_date]`
- Bar chart: Total Revenue by `dim_zone[borough]`
- Slicers: `dim_date[year_month]`, `dim_payment_type[payment_type_name]`

**Page 2: When people ride**
- Matrix heatmap: rows `dim_date[day_name]` (sort by `day_of_week`), columns `fact_trips[pickup_hour]`,
  values Total Trips, with background color conditional formatting
- Line chart: Card Tip Rate by `pickup_hour`, legend `dim_date[is_weekend]`

**Page 3: Where people ride**
- Table: top 15 `dim_zone[zone_name]` by Total Trips, with Avg Trip Minutes and Card Tip Rate
- Bar: Trips by Dropoff Zone (shows the inactive relationship working)
- Card: Airport Trip Share

**Page 4: Data quality**
- Card: DQ Checks Passed %
- Table: `dq_results` filtered to the latest `run_at`: check_name, severity, value, passed
  (conditional icon on `passed`)

This page matters for interviews. It shows the pipeline checks its own data
before anyone reports on it.

## 5. Finish

- Export a screenshot of page 1 to `docs/dashboard.png` for the README.
- Save the `.pbix`. GitHub accepts files up to 100 MB. If yours is bigger, share
  screenshots and a short screen recording instead.
