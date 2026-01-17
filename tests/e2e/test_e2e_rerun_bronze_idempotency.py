from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers.io import read_yaml

RUN_ID_RE = re.compile(r"^\d{8}_\d{6}_#[0-9a-fA-F]{6,32}$")


def _latest_run_id(root: Path) -> str:
    run_ids = [p.name for p in root.iterdir() if p.is_dir() and RUN_ID_RE.match(p.name)]
    assert run_ids, f"No run ids found in {root}"
    return sorted(run_ids)[-1]


def _run_bronze(raw_crm_dir: Path, raw_erp_dir: Path, bronze_root: Path, repo_root: Path) -> str:
    cmd = [
        sys.executable,
        "src/runs/load_1_bronze_layer.py",
        "--raw-crm",
        str(raw_crm_dir),
        "--raw-erp",
        str(raw_erp_dir),
        "--bronze-root",
        str(bronze_root),
    ]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return _latest_run_id(bronze_root)


@pytest.mark.e2e
def test_e2e_rerun_bronze_idempotency(
    prepared_raw_dirs: tuple[Path, Path],
    artifact_roots: dict,
    repo_root: Path,
) -> None:
    raw_crm_dir, raw_erp_dir = prepared_raw_dirs
    bronze_root = artifact_roots["bronze_root"]

    run_id_first = _run_bronze(raw_crm_dir, raw_erp_dir, bronze_root, repo_root)
    run_id_second = _run_bronze(raw_crm_dir, raw_erp_dir, bronze_root, repo_root)

    assert run_id_first != run_id_second

    first_data_dir = bronze_root / run_id_first / "data"
    second_data_dir = bronze_root / run_id_second / "data"

    first_csvs = {p.name for p in first_data_dir.glob("*.csv")}
    second_csvs = {p.name for p in second_data_dir.glob("*.csv")}
    assert first_csvs
    if second_csvs:
        assert first_csvs == second_csvs
    else:
        second_meta = read_yaml(second_data_dir / "metadata.yaml")
        summary = second_meta.get("summary", {})
        assert summary.get("files_skipped") == summary.get("files_total")
        assert summary.get("has_new_data") is False

    first_meta = read_yaml(first_data_dir / "metadata.yaml")
    second_meta = read_yaml(second_data_dir / "metadata.yaml")
    assert first_meta["run"]["run_id"] == run_id_first
    assert second_meta["run"]["run_id"] == run_id_second
