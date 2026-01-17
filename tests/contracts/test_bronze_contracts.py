from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.assertions import (
    assert_dir_contains_files,
    assert_exists,
    assert_nonempty_file,
    assert_yaml_has_fields,
)
from tests.helpers.io import read_yaml


@pytest.mark.contract
def test_bronze_contracts(run_bronze: str, prepared_raw_dirs: tuple[Path, Path], artifact_roots: dict) -> None:
    bronze_root = artifact_roots["bronze_root"]
    bronze_run_id = run_bronze
    data_dir = bronze_root / bronze_run_id / "data"
    report_dir = bronze_root / bronze_run_id / "reports"

    assert_exists(data_dir)
    assert_exists(report_dir)

    assert_dir_contains_files(data_dir, {"metadata.yaml", "run_log.txt"})
    assert_nonempty_file(report_dir / "elt_report.html")

    metadata = read_yaml(data_dir / "metadata.yaml")
    assert_yaml_has_fields(
        metadata,
        [
            "run.run_id",
            "run.layer",
            "run.pipeline",
            "run.started_utc",
            "sources.crm_files",
            "sources.erp_files",
        ],
    )

    raw_crm_dir, raw_erp_dir = prepared_raw_dirs
    for src_dir in [raw_crm_dir, raw_erp_dir]:
        for src_path in src_dir.glob("*.csv"):
            dest_path = data_dir / src_path.name
            assert_exists(dest_path)
            assert src_path.read_bytes() == dest_path.read_bytes()
