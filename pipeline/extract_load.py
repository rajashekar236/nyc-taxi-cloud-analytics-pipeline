"""Step 1 - Extract & Load.

Download NYC Yellow Taxi files from the TLC's public site, normalize them,
store a copy in Cloud Storage (the "data lake"), and load each month into its
own raw BigQuery table: taxi_raw.yellow_trips_YYYYMM.

One table per month makes reloads idempotent (WRITE_TRUNCATE replaces just
that month) without needing DML, which the free BigQuery sandbox doesn't allow.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
from google.cloud import bigquery

from pipeline import bq as bqh
from pipeline.config import settings
from pipeline.normalize import normalize_trips, normalize_zones

TRIPS_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"
ZONES_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"


def download(url: str, dest: Path) -> Path:
    if dest.exists():
        print(f"  cached  {dest.name}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  download {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.replace(dest)
    return dest


def write_parquet(df: pd.DataFrame, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False, coerce_timestamps="us", allow_truncated_timestamps=True)
    return dest


def upload_to_gcs(local: Path, blob_name: str) -> str:
    from google.cloud import storage  # only needed when a bucket is configured

    gcs = storage.Client(project=settings.project_id)
    blob = gcs.bucket(settings.bucket).blob(blob_name)
    blob.upload_from_filename(str(local))
    uri = f"gs://{settings.bucket}/{blob_name}"
    print(f"  uploaded {uri}")
    return uri


def load_parquet(bq: bigquery.Client, local: Path, blob_name: str, table_id: str) -> int:
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    if settings.bucket:
        uri = upload_to_gcs(local, blob_name)
        job = bq.load_table_from_uri(uri, table_id, job_config=job_config)
    else:
        with open(local, "rb") as f:
            job = bq.load_table_from_file(f, table_id, job_config=job_config)
    job.result()
    rows = bq.get_table(table_id).num_rows
    print(f"  loaded  {rows:,} rows -> {table_id}")
    return rows


def load_month(bq: bigquery.Client, month: str) -> int:
    raw = download(TRIPS_URL.format(month=month), settings.data_dir / "raw" / f"yellow_tripdata_{month}.parquet")
    df = normalize_trips(pd.read_parquet(raw), month)
    clean = write_parquet(df, settings.data_dir / "clean" / f"yellow_trips_{month}.parquet")
    table_id = f"{settings.project_id}.{settings.raw_dataset}.yellow_trips_{month.replace('-', '')}"
    return load_parquet(bq, clean, f"raw/yellow/yellow_trips_{month}.parquet", table_id)


def load_zones(bq: bigquery.Client) -> int:
    raw = download(ZONES_URL, settings.data_dir / "raw" / "taxi_zone_lookup.csv")
    # keep_default_na=False: the file uses the literal text "N/A" for out-of-city
    # zones, which pandas would otherwise turn into blanks.
    df = normalize_zones(pd.read_csv(raw, keep_default_na=False))
    clean = write_parquet(df, settings.data_dir / "clean" / "taxi_zones.parquet")
    table_id = f"{settings.project_id}.{settings.raw_dataset}.taxi_zones"
    return load_parquet(bq, clean, "raw/reference/taxi_zones.parquet", table_id)


def main() -> None:
    bq = bqh.client()
    bqh.ensure_datasets(bq)
    print("Extract & load")
    load_zones(bq)
    total = sum(load_month(bq, m) for m in settings.months)
    print(f"Done: {total:,} trip rows across {len(settings.months)} month(s).")


if __name__ == "__main__":
    main()
