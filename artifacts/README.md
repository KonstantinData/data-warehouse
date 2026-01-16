# Artifacts: Output Contract

## Scope
- Defines the artifact model, layout, and lifecycle for `artifacts/`.
- Does not describe how artifacts are produced; see runner and ADR documentation.

## Guarantees
- Artifacts are immutable, run-scoped outputs under `artifacts/<layer>/<run_id>/...`.
- `run_id` ties outputs to a single execution and is never reused.
- Artifacts are outputs only; they are not used as inputs for business logic.

## Non-goals
- Storing raw input data (see `raw/`).
- Describing layer transformation logic (see `src/` and ADRs).

## Artifact Types and Purpose
- **Layer outputs:** Bronze, Silver, Gold run directories.
- **Orchestrator outputs:** execution logs and summary reports.
- **Cross-layer reports:** consolidated diagnostics and rollups.
- **Ephemeral artifacts:** layer-local temporary outputs (allowed only under `tmp/`).

## Directory Layout Rules
```
artifacts/
├── bronze/<run_id>/
│   ├── data/
│   └── reports/
├── silver/<run_id>/
│   ├── data/
│   ├── reports/
│   └── tmp/        # ephemeral, non-authoritative
├── gold/
│   ├── planning/<run_id>/
│   │   ├── data/
│   │   └── reports/
│   └── marts/<run_id>/
│       ├── _meta/
│       ├── data/
│       ├── reports/
│       └── run_log.txt
├── orchestrator/<run_id>/
│   └── logs/
└── reports/<run_id>/
    └── summary_report.*
```

## Retention Policy
- Retain artifacts for audit and reproducibility until explicitly purged.
- Purges must be documented and repeatable (automated or runbook-driven).

## Versioning Strategy
- `run_id` is the version boundary for outputs.
- Re-runs create a new `run_id`; overwriting prior runs is prohibited.

## Relationship to `run_id`
- `run_id` must uniquely identify a single execution context.
- `run_id` links to the provenance of code, configuration, and inputs.

## Reproducible vs. Ephemeral
- **Reproducible:** `data/`, `reports/`, `_meta/`, and `run_log.txt` for a run.
- **Ephemeral:** `tmp/` directories (must be safe to delete at any time).

## Ownership and Responsibilities
- Repository maintainers own artifact policy and retention enforcement.
- Pipeline operators own cleanup automation and verification.

## Links
- **Upstream:** ADRs for run_id and artifact policy: `docs/adr/0003-run-id-and-artifact-layout.md`, `docs/adr/0010-artifacts-versioning-policy.md`.
- **Downstream:** Layer contracts: `bronze/README.md`, `silver/README.md`, `gold/README.md`.
