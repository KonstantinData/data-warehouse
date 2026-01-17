from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.runs import load_1_bronze_layer as bronze


@pytest.mark.unit
def test_build_run_id_format() -> None:
    start = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    run_id = bronze.build_run_id(None, start)
    assert run_id.startswith("20240102_030405_#")
    assert len(run_id.split("_#")[1]) == 8


@pytest.mark.unit
def test_detect_changed_mtime_and_hash() -> None:
    prev = {"file_mtime_utc": "2024-01-01T00:00:00Z", "sha256": "abc"}
    current_same = {"file_mtime_utc": "2024-01-01T00:00:00Z", "sha256": "abc"}
    current_new_hash = {"file_mtime_utc": "2024-01-01T00:00:00Z", "sha256": "def"}
    assert bronze.detect_changed(prev, current_same) is False
    assert bronze.detect_changed(prev, current_new_hash) is True


@pytest.mark.unit
def test_sha256_file_stable(tmp_path: Path) -> None:
    content = b"bronze-test"
    file_path = tmp_path / "sample.txt"
    file_path.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert bronze.sha256_file(str(file_path)) == expected
