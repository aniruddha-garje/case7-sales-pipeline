# pipeline/run_pipeline.py
# Main entry point. Orchestrates: ingest → quality checks → transform → summary.
# Run: python pipeline/run_pipeline.py

import os
import sys

# Ensure project root is on path so pipeline/ imports work
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import duckdb
from pipeline.ingest import ingest_all
from pipeline.quality_checks import run_all_checks
from pipeline.transform import transform_all

DB_PATH = os.path.join(ROOT, "output", "sales.duckdb")
DATA_DIR = os.path.join(ROOT, "datasets")


def main():
    print("=" * 60)
    print("SALES DATA PIPELINE — Starting")
    print("=" * 60)

    # TODO: implement in Phase 5
    raise NotImplementedError("Implement in Phase 5")


if __name__ == "__main__":
    main()
