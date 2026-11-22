"""Normalize raw NYC TLC files to one stable schema.

The TLC changes column names and types between years (e.g. `Airport_fee` vs
`airport_fee`, float vs int passenger counts, new fee columns in 2025). If we
loaded the files as-is, monthly tables would not line up. This module maps every
file onto the same schema before it reaches Cloud Storage or BigQuery.

Kept free of any Google Cloud imports so it can be unit-tested offline.
"""
from __future__ import annotations

import pandas as pd

# Source column (lower-cased) -> our column name
RENAME = {
    "vendorid": "vendor_id",
    "tpep_pickup_datetime": "pickup_ts",
    "tpep_dropoff_datetime": "dropoff_ts",
    "passenger_count": "passenger_count",
    "trip_distance": "trip_distance",
    "ratecodeid": "ratecode_id",
    "store_and_fwd_flag": "store_and_fwd_flag",
    "pulocationid": "pu_location_id",
    "dolocationid": "do_location_id",
    "payment_type": "payment_type",
    "fare_amount": "fare_amount",
    "extra": "extra",
    "mta_tax": "mta_tax",
    "tip_amount": "tip_amount",
    "tolls_amount": "tolls_amount",
    "improvement_surcharge": "improvement_surcharge",
    "total_amount": "total_amount",
    "congestion_surcharge": "congestion_surcharge",
    "airport_fee": "airport_fee",
}

INT_COLS = ["vendor_id", "passenger_count", "ratecode_id", "pu_location_id",
            "do_location_id", "payment_type"]
FLOAT_COLS = ["trip_distance", "fare_amount", "extra", "mta_tax", "tip_amount",
              "tolls_amount", "improvement_surcharge", "total_amount",
              "congestion_surcharge", "airport_fee"]
TS_COLS = ["pickup_ts", "dropoff_ts"]
STR_COLS = ["store_and_fwd_flag"]

OUTPUT_COLUMNS = (["vendor_id", "pickup_ts", "dropoff_ts"]
                  + [c for c in INT_COLS if c != "vendor_id"]
                  + FLOAT_COLS + STR_COLS + ["source_month"])


def normalize_trips(df: pd.DataFrame, source_month: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns=RENAME)

    for col in INT_COLS:
        values = (pd.to_numeric(df[col], errors="coerce") if col in df
                  else pd.Series(float("nan"), index=df.index))
        df[col] = values.round().astype("Int64")
    for col in FLOAT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64") if col in df else float("nan")
    for col in TS_COLS:
        # TLC timestamps are New York wall-clock time with no timezone.
        df[col] = pd.to_datetime(df[col], errors="coerce").astype("datetime64[us]")
    for col in STR_COLS:
        df[col] = df[col].astype("string") if col in df else pd.Series(pd.NA, index=df.index, dtype="string")

    df["source_month"] = source_month
    return df[OUTPUT_COLUMNS]


def normalize_zones(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        "LocationID": "location_id",
        "Borough": "borough",
        "Zone": "zone",
        "service_zone": "service_zone",
    })
    df["location_id"] = pd.to_numeric(df["location_id"]).astype("Int64")
    for col in ("borough", "zone", "service_zone"):
        df[col] = df[col].astype("string")
    return df[["location_id", "borough", "zone", "service_zone"]]
