# Gold Layer Contract

## Scope
- Defines the Gold layer output contract and invariants.
- Does not describe model implementation; see `src/runs/load_3_gold_layer.py` and ADRs.

## Guarantees
- Gold outputs are business-ready marts derived from Silver inputs.
- Each run writes to a unique `run_id` directory under `artifacts/gold/`.
- Gold outputs include lineage metadata sufficient for audit.

## Non-goals
- Source system remediation or upstream cleansing beyond Silver.
- Serving as a real-time or transactional system.

## Layer Responsibility
- Produce curated marts and aggregates for analytics and reporting.
- Preserve lineage from Silver inputs to Gold outputs.

## Input Contract
- **Expected inputs:** a single Silver `run_id` directory under `artifacts/silver/`.
- **Assumptions/invariants:** Silver schemas are stable and validated.
- **Missing/invalid data:** the run must fail fast and record schema or mapping errors.

## Output Contract
- **Guarantees:** `marts/<run_id>/data` with `_meta/` lineage and `reports/` diagnostics.
- **Downstream stability:** schema changes require an ADR and a documented migration.

## Quality Gates
- Schema validation against Gold model definitions.
- Referential integrity checks where defined.
- **Failure behavior:** block the run on failed validations.

## Idempotency & Re-runs
- Re-runs create a new `run_id` and do not overwrite marts.
- Backfills target a specific Silver `run_id` and are isolated by output `run_id`.

## Links
- **Upstream:** Silver layer contract: `artifacts/silver/README.md`.
- **Downstream:** Reporting outputs: `artifacts/reports/` (see `artifacts/README.md`).
- **Reference:** ADRs: `docs/adr/0002-medallion-architecture-bronze-silver-gold.md`, `docs/adr/0003-run-id-and-artifact-layout.md`.
