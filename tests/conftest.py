from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

import pytest

from tests.helpers.io import copy_tree

RUN_ID_RE = re.compile(r"^\d{8}_\d{6}_#[0-9a-fA-F]{6,32}$")


def _latest_run_id(root: Path) -> str:
    if not root.exists():
        raise FileNotFoundError(f"Run root does not exist: {root}")
    run_ids = [p.name for p in root.iterdir() if p.is_dir() and RUN_ID_RE.match(p.name)]
    if not run_ids:
        raise FileNotFoundError(f"No run IDs found under: {root}")
    return sorted(run_ids)[-1]


def _run_command(cmd: list[str], cwd: Path, env: Dict[str, str] | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        msg = (
            f"Command failed: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        raise AssertionError(msg)


@pytest.fixture()
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture()
def fixture_raw_root(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "raw"


@pytest.fixture()
def prepared_raw_dirs(tmp_path: Path, fixture_raw_root: Path) -> Tuple[Path, Path]:
    raw_root = tmp_path / "raw"
    raw_crm_dir = raw_root / "source_crm"
    raw_erp_dir = raw_root / "source_erp"
    copy_tree(fixture_raw_root / "source_crm", raw_crm_dir)
    copy_tree(fixture_raw_root / "source_erp", raw_erp_dir)
    return raw_crm_dir, raw_erp_dir


@pytest.fixture()
def artifact_roots(tmp_path: Path) -> Dict[str, Path]:
    return {
        "bronze_root": tmp_path / "artifacts" / "bronze",
        "silver_root": tmp_path / "artifacts" / "silver",
        "gold_root": tmp_path / "artifacts" / "gold" / "marts",
    }


@pytest.fixture()
def run_bronze(prepared_raw_dirs: Tuple[Path, Path], artifact_roots: Dict[str, Path], repo_root: Path) -> str:
    raw_crm_dir, raw_erp_dir = prepared_raw_dirs
    bronze_root = artifact_roots["bronze_root"]
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
    _run_command(cmd, cwd=repo_root)
    return _latest_run_id(bronze_root)


@pytest.fixture()
def run_silver(run_bronze: str, artifact_roots: Dict[str, Path], repo_root: Path) -> str:
    bronze_root = artifact_roots["bronze_root"]
    silver_root = artifact_roots["silver_root"]
    env = os.environ.copy()
    env.update({
        "BRONZE_ROOT": str(bronze_root),
        "SILVER_ROOT": str(silver_root),
    })
    cmd = [
        sys.executable,
        "src/runs/load_2_silver_layer.py",
        run_bronze,
    ]
    _run_command(cmd, cwd=repo_root, env=env)
    return _latest_run_id(silver_root)


@pytest.fixture()
def run_gold(run_silver: str, artifact_roots: Dict[str, Path], repo_root: Path) -> str:
    silver_root = artifact_roots["silver_root"]
    gold_root = artifact_roots["gold_root"]
    gold_root.mkdir(parents=True, exist_ok=True)
    gold_root_override = repo_root / ".pytest_gold_root"
    if gold_root_override.exists() or gold_root_override.is_symlink():
        if gold_root_override.is_symlink() or gold_root_override.is_file():
            gold_root_override.unlink()
        else:
            raise RuntimeError(f"Gold root override already exists and is not a symlink: {gold_root_override}")
    gold_root_override.parent.mkdir(parents=True, exist_ok=True)
    gold_root_override.symlink_to(gold_root)
    env = os.environ.copy()
    env.update({
        "SILVER_ROOT": str(silver_root),
        "SILVER_ROOT_OVERRIDE": str(silver_root),
        "GOLD_ROOT_OVERRIDE": str(gold_root_override),
    })
    cmd = [
        sys.executable,
        "src/runs/load_3_gold_layer.py",
        run_silver,
    ]
    try:
        _run_command(cmd, cwd=repo_root, env=env)
    finally:
        if gold_root_override.is_symlink():
            gold_root_override.unlink()
    return _latest_run_id(gold_root)
