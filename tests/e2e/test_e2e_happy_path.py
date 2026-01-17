from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.assertions import assert_csv_rowcount_at_least, assert_dir_contains_files, assert_exists


@pytest.mark.e2e
def test_e2e_happy_path(run_bronze: str, run_silver: str, run_gold: str, artifact_roots: dict) -> None:
    bronze_root = artifact_roots["bronze_root"]
    silver_root = artifact_roots["silver_root"]
    gold_root = artifact_roots["gold_root"]

    bronze_dir = bronze_root / run_bronze
    silver_dir = silver_root / run_silver
    gold_dir = gold_root / run_gold

    assert_exists(bronze_dir / "data" / "metadata.yaml")
    assert_exists(silver_dir / "data" / "metadata.yaml")
    assert_exists(gold_dir / "data")

    expected_gold_outputs = {
        "gold_dim_customer.csv",
        "gold_dim_product.csv",
        "gold_dim_location.csv",
        "gold_fact_sales.csv",
        "gold_agg_exec_kpis.csv",
        "gold_agg_product_performance.csv",
        "gold_agg_geo_performance.csv",
        "gold_wide_sales_enriched.csv",
    }
    assert_dir_contains_files(gold_dir / "data", expected_gold_outputs)

    for filename in expected_gold_outputs:
        assert_csv_rowcount_at_least(gold_dir / "data" / filename, 1)
