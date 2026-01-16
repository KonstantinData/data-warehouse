# 0005 – Incremental Ingestion & State Management

*Status:* Accepted

## Context

Full reloads are costly and slow. Most sources provide changes since the last successful run.

## Decision

Implement **incremental ingestion** backed by persisted state (e.g., timestamps or checkpoints).

## Rationale

* **Cost efficiency:** Less data processed per run.
* **Freshness:** Faster updates for reporting and downstream consumers.
* **Stability:** Shorter runtimes reduce operational risk.

## Consequences

* Additional state storage and lifecycle management.
* Robust error handling is required to avoid data gaps.
