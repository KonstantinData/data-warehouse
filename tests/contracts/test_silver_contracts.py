from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.assertions import assert_dir_contains_files, assert_exists, assert_nonempty_file
from tests.helpers.io import read_csv_rows


@pytest.mark.contract
def test_silver_contracts(
    run_bronze: str,
    run_silver: str,
    artifact_roots: dict,
) -> None:
    bronze_root = artifact_roots["bronze_root"]
    silver_root = artifact_roots["silver_root"]

    bronze_run_id = run_bronze
    silver_run_id = run_silver

    bronze_data_dir = bronze_root / bronze_run_id / "data"
    silver_data_dir = silver_root / silver_run_id / "data"
    silver_report_dir = silver_root / silver_run_id / "reports"

    assert_exists(silver_data_dir)
    assert_exists(silver_report_dir)

    assert_dir_contains_files(silver_data_dir, {"metadata.yaml", "run_log.txt"})
    assert_nonempty_file(silver_report_dir / "elt_report.html")

    bronze_csvs = {p.name for p in bronze_data_dir.glob("*.csv")}
    silver_csvs = {p.name for p in silver_data_dir.glob("*.csv")}
    assert bronze_csvs.issubset(silver_csvs)

    bronze_rows = read_csv_rows(bronze_data_dir / "cst_info.csv")
    silver_rows = read_csv_rows(silver_data_dir / "cst_info.csv")
    bronze_first = next(r for r in bronze_rows if r.get("cst_id") == "1")
    silver_first = next(r for r in silver_rows if r.get("cst_id") == "1")
    assert bronze_first["cst_firstname"].startswith(" ")
    assert silver_first["cst_firstname"] == "Alice"
