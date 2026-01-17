from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.assertions import assert_csv_unique_on, assert_dir_contains_files, assert_exists, assert_nonempty_file
from tests.helpers.io import read_csv_rows


@pytest.mark.contract
def test_gold_contracts(
    run_bronze: str,
    run_silver: str,
    run_gold: str,
    artifact_roots: dict,
) -> None:
    gold_root = artifact_roots["gold_root"]
    gold_run_id = run_gold

    gold_dir = gold_root / gold_run_id
    data_dir = gold_dir / "data"
    reports_dir = gold_dir / "reports"
    run_log = gold_dir / "run_log.txt"

    assert_exists(data_dir)
    assert_exists(run_log)
    if reports_dir.exists():
        assert_nonempty_file(reports_dir / "gold_report.html")

    expected_files = {
        "gold_dim_customer.csv",
        "gold_dim_product.csv",
        "gold_dim_location.csv",
        "gold_fact_sales.csv",
        "gold_agg_exec_kpis.csv",
        "gold_agg_product_performance.csv",
        "gold_agg_geo_performance.csv",
        "gold_wide_sales_enriched.csv",
    }
    assert_dir_contains_files(data_dir, expected_files)

    assert_csv_unique_on(data_dir / "gold_dim_customer.csv", ["cst_key"])

    dim_customers = read_csv_rows(data_dir / "gold_dim_customer.csv")
    dim_products = read_csv_rows(data_dir / "gold_dim_product.csv")
    fact_sales = read_csv_rows(data_dir / "gold_fact_sales.csv")

    customer_ids = {row.get("cst_id") for row in dim_customers}
    product_ids = {row.get("prd_key") for row in dim_products}

    for row in fact_sales:
        assert row.get("sls_cust_id") in customer_ids
        assert row.get("sls_prd_key") in product_ids
