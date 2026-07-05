"""Ingest Malaysian open data (data.gov.my Data Catalogue API) into data/raw/.

Each dataset is saved as gzipped JSON exactly as returned by the API (bronze /
raw layer -- no transformation on ingest). If the API is unreachable, the
committed snapshot in data/raw/ is kept so the rest of the pipeline still runs
offline.

Usage:
    python src/ingest.py            # refresh all datasets
    python src/ingest.py fuelprice  # refresh one dataset
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

import requests

API_URL = "https://api.data.gov.my/data-catalogue/?id={dataset_id}"

DATASETS = {
    "fuelprice": "Weekly retail fuel prices (RON95 / RON97 / diesel), 2017-present",
    "cpi_headline": "Monthly national CPI by COICOP division, 1980-present",
    "cpi_state": "Monthly CPI by state and COICOP division, 2010-present",
}

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"


def fetch(dataset_id: str, retries: int = 3, timeout: int = 120) -> list[dict]:
    """Fetch a full dataset from the Data Catalogue API with basic retry."""
    url = API_URL.format(dataset_id=dataset_id)
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "malaysia-open-data-pipeline"},
            )
            resp.raise_for_status()
            rows = resp.json()
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"unexpected payload for {dataset_id!r}")
            return rows
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def save_raw(dataset_id: str, rows: list[dict]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{dataset_id}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return path


def main(only: str | None = None) -> None:
    targets = [only] if only else list(DATASETS)
    for dataset_id in targets:
        if dataset_id not in DATASETS:
            sys.exit(f"unknown dataset {dataset_id!r}; choose from {list(DATASETS)}")
        snapshot = RAW_DIR / f"{dataset_id}.json.gz"
        try:
            rows = fetch(dataset_id)
            path = save_raw(dataset_id, rows)
            print(f"[ingest] {dataset_id}: {len(rows):,} rows -> {path.relative_to(REPO_ROOT)}")
        except Exception as exc:
            if snapshot.exists():
                print(f"[ingest] {dataset_id}: API unavailable ({exc}); using committed snapshot")
            else:
                raise


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
