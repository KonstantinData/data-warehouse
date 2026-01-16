# Bronze Layer Contract

## Scope
- Defines the Bronze layer output contract and invariants.
- Does not describe ingestion implementation; see `src/runs/load_1_bronze_layer.py` and ADRs.

## Guarantees
- Bronze outputs are immutable snapshots of raw inputs.
- Each run writes to a unique `run_id` directory under `artifacts/bronze/`.
- Output metadata is sufficient to audit source file lineage and checksums.

## Non-goals
- Data cleansing, normalization, or schema standardization.
- Business logic or aggregation.

## Layer Responsibility
- Preserve raw inputs as audit-ready snapshots with minimal transformation.
- Provide traceable metadata for downstream layers.

## Input Contract
- **Expected inputs:** raw CSV sources from `raw/source_crm` and `raw/source_erp`.
- **Assumptions/invariants:** source files are immutable for the duration of a run.
- **Missing/invalid data:** the run must fail fast with a recorded error in logs.

## Output Contract
- **Guarantees:** immutable `data/` snapshots plus `reports/` metadata per run.
- **Downstream stability:** file naming and metadata fields are stable across runs.

## Quality Gates
- File discovery is explicit and logged.
- Checksums and row counts are recorded in metadata.
- **Failure behavior:** block the run on missing or unreadable inputs.

## Idempotency & Re-runs
- Re-runs create a new `run_id` and do not overwrite prior outputs.
- Backfills use historical inputs and are isolated by `run_id`.

## Links
- **Upstream:** Raw data contract: `raw/README.md`.
- **Downstream:** Silver layer contract: `artifacts/silver/README.md`.
- **Reference:** ADRs: `docs/adr/0002-medallion-architecture-bronze-silver-gold.md`, `docs/adr/0003-run-id-and-artifact-layout.md`.
