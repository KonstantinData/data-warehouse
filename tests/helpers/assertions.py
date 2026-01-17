from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from .io import read_csv_header, read_csv_rows


def assert_exists(path: Path) -> None:
    assert path.exists(), f"Expected path to exist: {path}"


def assert_nonempty_file(path: Path) -> None:
    assert path.exists(), f"Expected file to exist: {path}"
    assert path.is_file(), f"Expected file to be a regular file: {path}"
    assert path.stat().st_size > 0, f"Expected file to be non-empty: {path}"


def assert_dir_contains_files(dir_path: Path, filenames_set: Iterable[str]) -> None:
    missing = {name for name in filenames_set if not (dir_path / name).exists()}
    assert not missing, f"Directory {dir_path} missing files: {sorted(missing)}"


def assert_yaml_has_fields(yaml_dict: dict, dotted_field_paths_list: Sequence[str]) -> None:
    for dotted_path in dotted_field_paths_list:
        current = yaml_dict
        for part in dotted_path.split("."):
            assert isinstance(current, dict), f"Expected dict while traversing {dotted_path}"
            assert part in current, f"Missing field '{part}' in path '{dotted_path}'"
            current = current[part]


def assert_csv_has_columns(csv_path: Path, required_cols_list: Sequence[str]) -> None:
    header = read_csv_header(csv_path)
    missing = [col for col in required_cols_list if col not in header]
    assert not missing, f"CSV {csv_path} missing columns: {missing}"


def assert_csv_rowcount_at_least(csv_path: Path, n: int) -> None:
    rows = read_csv_rows(csv_path)
    assert len(rows) >= n, f"CSV {csv_path} has {len(rows)} rows, expected at least {n}"


def assert_csv_unique_on(csv_path: Path, key_cols_list: Sequence[str]) -> None:
    rows = read_csv_rows(csv_path)
    seen = set()
    duplicates = []
    for row in rows:
        key = tuple(row.get(col) for col in key_cols_list)
        if key in seen:
            duplicates.append(key)
        else:
            seen.add(key)
    assert not duplicates, f"CSV {csv_path} has duplicate keys on {key_cols_list}: {duplicates}"
