"""Central configuration, read from environment variables / a .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _months(raw: str) -> list[str]:
    months = [m.strip() for m in raw.split(",") if m.strip()]
    for m in months:
        if len(m) != 7 or m[4] != "-":
            raise ValueError(f"MONTHS entries must look like 2024-01, got {m!r}")
    return months


@dataclass(frozen=True)
class Settings:
    project_id: str = field(default_factory=lambda: os.environ.get("GCP_PROJECT_ID", ""))
    location: str = field(default_factory=lambda: os.environ.get("BQ_LOCATION", "US"))
    bucket: str = field(default_factory=lambda: os.environ.get("GCS_BUCKET", "").strip())
    raw_dataset: str = field(default_factory=lambda: os.environ.get("BQ_RAW_DATASET", "taxi_raw"))
    dataset: str = field(default_factory=lambda: os.environ.get("BQ_DATASET", "taxi_analytics"))
    months: list[str] = field(
        default_factory=lambda: _months(os.environ.get("MONTHS", "2024-01,2024-02,2024-03"))
    )
    max_bytes_billed: int = field(
        default_factory=lambda: int(os.environ.get("MAX_BYTES_BILLED", "20000000000"))
    )

    data_dir: Path = PROJECT_ROOT / "data"
    sql_dir: Path = PROJECT_ROOT / "sql"
    reports_dir: Path = PROJECT_ROOT / "reports"

    def require_project(self) -> None:
        if not self.project_id or self.project_id == "your-project-id":
            raise SystemExit("Set GCP_PROJECT_ID in your .env file first (see .env.example).")


settings = Settings()
