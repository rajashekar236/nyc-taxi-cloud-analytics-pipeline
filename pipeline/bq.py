"""Small BigQuery helpers shared by every pipeline step."""
from __future__ import annotations

from string import Template

import pandas as pd
from google.cloud import bigquery

from pipeline.config import settings


def client() -> bigquery.Client:
    settings.require_project()
    return bigquery.Client(project=settings.project_id, location=settings.location)


def ensure_datasets(bq: bigquery.Client) -> None:
    for name in (settings.raw_dataset, settings.dataset):
        ds = bigquery.Dataset(f"{settings.project_id}.{name}")
        ds.location = settings.location
        bq.create_dataset(ds, exists_ok=True)


def render(sql: str) -> str:
    """Fill ${project}, ${raw_dataset} and ${dataset} placeholders in a SQL file."""
    return Template(sql).substitute(
        project=settings.project_id,
        raw_dataset=settings.raw_dataset,
        dataset=settings.dataset,
    )


def run(bq: bigquery.Client, sql: str, params: list | None = None) -> bigquery.table.RowIterator:
    """Run a query with a hard cap on bytes scanned, so a mistake can't run up a bill."""
    config = bigquery.QueryJobConfig(
        maximum_bytes_billed=settings.max_bytes_billed,
        query_parameters=params or [],
    )
    job = bq.query(render(sql), job_config=config)
    result = job.result()
    gb = (job.total_bytes_processed or 0) / 1e9
    print(f"    scanned {gb:.2f} GB")
    return result


def scalar(bq: bigquery.Client, sql: str):
    rows = list(run(bq, sql))
    return rows[0][0] if rows else None


def to_df(bq: bigquery.Client, sql: str, params: list | None = None) -> pd.DataFrame:
    return run(bq, sql, params).to_dataframe()
