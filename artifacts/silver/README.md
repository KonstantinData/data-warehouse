# Silver Layer Contract

## Scope
- Defines the Silver layer output contract and invariants.
- Does not describe transformation implementation; see `src/runs/load_2_silver_layer.py` and ADRs.

## Guarantees
- Silver outputs are standardized representations of Bronze inputs.
- Each run writes to a unique `run_id` directory under `artifacts/silver/`.
- Output schemas are stable and documented in layer reports.

## Non-goals
- Business aggregation or dimensional modeling.
- Fixing upstream data capture issues in source systems.

## Layer Responsibility
- Normalize and type Bronze data while preserving row-level fidelity.
- Enforce consistent schemas suitable for downstream Gold models.

## Input Contract
- **Expected inputs:** a single Bronze `run_id` directory under `artifacts/bronze/`.
- **Assumptions/invariants:** Bronze metadata and data snapshots are complete.
- **Missing/invalid data:** the run must fail fast and log the violating dataset.

## Output Contract
- **Guarantees:** standardized `data/` outputs plus validation `reports/` per run.
- **Downstream stability:** column names and types remain stable absent an ADR.

## Quality Gates
- Schema validation against expected field sets.
- Null/invalid value checks with thresholds defined in reports.
- **Failure behavior:** block the run on contract violations.

## Idempotency & Re-runs
- Re-runs create a new `run_id`; no in-place mutation.
- Backfills target a specific Bronze `run_id` and are isolated by output `run_id`.

## Links
- **Upstream:** Bronze layer contract: `artifacts/bronze/README.md`.
- **Downstream:** Gold layer contract: `artifacts/gold/README.md`.
- **Reference:** ADRs: `docs/adr/0002-medallion-architecture-bronze-silver-gold.md`, `docs/adr/0003-run-id-and-artifact-layout.md`.
