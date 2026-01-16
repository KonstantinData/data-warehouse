# 0015 – Code Quality Agent Run Evaluation

*Status:* Accepted

## Context

The multi-agent run coordinates specialized reviewers and records artifacts. Clear expectations ensure traceability, reproducibility, and dependable audit trails.

## Decision

Define the responsibilities and evaluation criteria for the **code_quality_agents** run.

## Rationale

* **Traceability:** Inputs, outputs, and logs must be consistently stored.
* **Reliability:** Failures should be captured without losing context.
* **Reproducibility:** Run IDs and prompt configurations must be linked to results.

## Consequences

* Runs must persist agent outputs, logs, and timing metrics.
* Audit artifacts become a required part of each execution.
