"""Offline tests: no Google Cloud account needed. Run with `pytest -q`."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.stats_analysis import run_analysis
from pipeline.normalize import OUTPUT_COLUMNS, normalize_trips, normalize_zones
from pipeline.transform import statements


def test_normalize_handles_schema_drift():
    # Mimics a 2024 file: capitalized Airport_fee, float passenger_count, missing a column.
    raw = pd.DataFrame({
        "VendorID": [1, 2],
        "tpep_pickup_datetime": pd.to_datetime(["2024-01-01 08:00", "2024-01-02 09:30"]),
        "tpep_dropoff_datetime": pd.to_datetime(["2024-01-01 08:20", "2024-01-02 09:45"]),
        "passenger_count": [1.0, np.nan],
        "trip_distance": [2.5, 1.1],
        "RatecodeID": [1.0, 1.0],
        "store_and_fwd_flag": ["N", "N"],
        "PULocationID": [132, 236],
        "DOLocationID": [236, 237],
        "payment_type": [1, 2],
        "fare_amount": [15.0, 8.0],
        "tip_amount": [3.0, 0.0],
        "total_amount": [20.0, 10.0],
        "Airport_fee": [1.75, 0.0],
        # extra, mta_tax, tolls, surcharges deliberately missing
    })
    out = normalize_trips(raw, "2024-01")
    assert list(out.columns) == OUTPUT_COLUMNS
    assert out["airport_fee"].tolist() == [1.75, 0.0]
    assert str(out["passenger_count"].dtype) == "Int64"
    assert out["passenger_count"].isna().tolist() == [False, True]
    assert out["tolls_amount"].isna().all()
    assert (out["source_month"] == "2024-01").all()


def test_normalize_zones():
    raw = pd.DataFrame({"LocationID": [1, 132], "Borough": ["EWR", "Queens"],
                        "Zone": ["Newark Airport", "JFK Airport"], "service_zone": ["EWR", "Airports"]})
    out = normalize_zones(raw)
    assert list(out.columns) == ["location_id", "borough", "zone", "service_zone"]


def test_sql_statement_splitting():
    sql = "-- header\nCREATE TABLE a AS SELECT 1;\n\nCREATE TABLE b AS SELECT 2;\n-- trailing comment\n"
    assert len(statements(sql)) == 2


def test_stats_on_synthetic_data(tmp_path):
    rng = np.random.default_rng(42)
    n = 20_000
    weekend = rng.random(n) < 0.3
    airport = rng.random(n) < 0.1
    tip = np.clip(0.18 + 0.02 * weekend - 0.03 * airport + rng.normal(0, 0.06, n), 0, 1)
    df = pd.DataFrame({
        "tip_pct": tip,
        "trip_distance": rng.gamma(2, 1.5, n),
        "trip_minutes": rng.gamma(3, 5, n),
        "pickup_hour": rng.integers(0, 24, n),
        "is_weekend": weekend,
        "is_airport": airport,
        "pickup_borough": rng.choice(["Manhattan", "Queens", "Brooklyn"], n, p=[0.8, 0.15, 0.05]),
    })
    report = run_analysis(df, tmp_path)
    assert "+2." in report                    # weekend effect of ~+2 points is recovered
    assert (tmp_path / "stats_results.md").exists()
    assert (tmp_path / "tip_pct_by_hour.png").exists()
