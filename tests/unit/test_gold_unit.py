from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from src.runs import load_3_gold_layer as gold


@pytest.mark.unit
def test_make_gold_run_id_from_silver() -> None:
    silver_run_id = "20240102_030405_#abcdef12"
    now = datetime(2024, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
    gold_run_id = gold.make_gold_run_id_from_silver(silver_run_id, now=now)
    assert gold_run_id == "20240304_050607_#abcdef12"


@pytest.mark.unit
def test_validate_required_columns_reports_missing() -> None:
    df = pd.DataFrame({"a": [1]})
    errors = gold.validate_required_columns(df, ["a", "b"], "table.csv")
    assert errors == ["table.csv missing columns: ['b']"]


@pytest.mark.unit
def test_int_to_date_handles_valid_and_invalid() -> None:
    assert gold.int_to_date(20240115) == "2024-01-15"
    assert gold.int_to_date("not-a-date") is None
