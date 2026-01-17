from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from src.runs import load_2_silver_layer as silver


@pytest.mark.unit
def test_run_id_re_accepts_valid() -> None:
    assert silver.RUN_ID_RE.match("20240102_030405_#abcdef12")


@pytest.mark.unit
def test_run_id_re_rejects_invalid() -> None:
    assert silver.RUN_ID_RE.match("20240102-030405-abcdef12") is None


@pytest.mark.unit
def test_make_silver_run_id_copies_suffix() -> None:
    bronze_run_id = "20240102_030405_#abcdef12"
    now = datetime(2024, 2, 1, 1, 2, 3, tzinfo=timezone.utc)
    silver_run_id = silver.make_silver_run_id_from_bronze(bronze_run_id, now=now)
    assert silver_run_id == "20240201_010203_#abcdef12"


@pytest.mark.unit
def test_base_silver_cleaning_trims_and_nulls() -> None:
    df = pd.DataFrame({"name": ["  Alice ", ""], "age": [1, 2]})
    cleaned = silver.base_silver_cleaning(df)
    assert cleaned.loc[0, "name"] == "Alice"
    assert pd.isna(cleaned.loc[1, "name"])
