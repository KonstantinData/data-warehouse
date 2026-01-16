# 0002 – Medallion Architecture (Bronze/Silver/Gold)

*Status:* Accepted

## Context

We ingest data from heterogeneous sources with varying quality. Analytics require a clear lineage from raw input to curated outputs.

## Decision

Adopt the Medallion architecture:

* **Bronze:** Raw, immutable ingested data.
* **Silver:** Cleaned, normalized, and validated data.
* **Gold:** Business-ready datasets for analytics and reporting.

## Rationale

* **Traceability:** Each transformation stage is explicit and reviewable.
* **Quality control:** Issues can be isolated at the layer where they occur.
* **Scalability:** New sources can be added without destabilizing analytics.

## Consequences

* Additional storage due to layered datasets.
* Clear ownership of quality checks per layer.
