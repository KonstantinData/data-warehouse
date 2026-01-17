from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd


def _fsync_directory(directory: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        fd = os.open(directory, os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write_bytes(data: bytes, target: Path | str) -> None:
    path = Path(target)
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        with open(tmp_path, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def atomic_write_text(data: str, target: Path | str, encoding: str = "utf-8", newline: Optional[str] = None) -> None:
    path = Path(target)
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        with open(tmp_path, "w", encoding=encoding, newline=newline) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def atomic_to_csv(df: pd.DataFrame, target: Path | str, **kwargs: Any) -> None:
    path = Path(target)
    tmp_path = path.with_name(f".{path.name}.tmp")
    encoding = kwargs.pop("encoding", "utf-8")
    newline = kwargs.pop("newline", "")
    try:
        with open(tmp_path, "w", encoding=encoding, newline=newline) as handle:
            df.to_csv(handle, **kwargs)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
