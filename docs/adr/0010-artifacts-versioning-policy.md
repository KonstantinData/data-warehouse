# 0010 – Artifact Versioning Policy

*Status:* Accepted

## Context

Artifacts (outputs, reports, models) evolve over time. Without versioning, results cannot be reproduced or audited reliably.

## Decision

All artifacts are versioned. Each version includes metadata for source, Run ID, date, and pipeline version.

## Rationale

* **Reproducibility:** Results can be explained and recreated.
* **Auditability:** Historical decisions remain verifiable.
* **Trust:** Consistent data snapshots support confident decision-making.

## Consequences

* Higher storage usage, balanced by stronger governance.
* Requires defined retention and archival policies.
