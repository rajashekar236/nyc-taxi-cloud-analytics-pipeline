"""Step 2 - Transform (the "T" in ELT).

Runs every file in sql/ in name order. Each file may hold several statements
separated by semicolons. All SQL runs inside BigQuery; Python only orchestrates.
"""
from __future__ import annotations

from pipeline import bq as bqh
from pipeline.config import settings


def statements(sql: str) -> list[str]:
    parts = [p.strip() for p in sql.split(";")]
    # Drop chunks that are empty or only comments.
    return [p for p in parts
            if any(line.strip() and not line.strip().startswith("--") for line in p.splitlines())]


def main() -> None:
    bq = bqh.client()
    bqh.ensure_datasets(bq)
    print("Transform")
    for path in sorted(settings.sql_dir.glob("*.sql")):
        for i, stmt in enumerate(statements(path.read_text(encoding="utf-8")), start=1):
            print(f"  {path.name} [{i}]")
            bqh.run(bq, stmt)
    print("Done: star schema and marts built in "
          f"{settings.project_id}.{settings.dataset}")


if __name__ == "__main__":
    main()
