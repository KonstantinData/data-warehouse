from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import List, Dict

import yaml


def read_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def read_csv_header(path: Path) -> List[str]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        return next(reader, [])


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def copy_tree(src_dir: Path, dst_dir: Path) -> None:
    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
