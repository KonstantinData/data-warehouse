# 0003 – Run ID & Artifact Layout

*Status:* Accepted

## Context

Pipeline executions generate logs, outputs, and metadata. Without a consistent structure, troubleshooting and audits become expensive and unreliable.

## Decision

Each pipeline execution receives a unique **Run ID**. Artifacts are stored in a consistent directory structure keyed by Run ID, date, and pipeline name.

## Rationale

* **Auditability:** Results can be traced to a specific run.
* **Operational efficiency:** Logs and outputs are discoverable quickly.
* **Compliance readiness:** Supports retention and audit requirements.

## Consequences

* All jobs must follow naming and storage conventions.
* Improves long-term observability and SLA reporting.
