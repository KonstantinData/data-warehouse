# 0014 – Code Quality Orchestrator Evaluation

*Status:* Accepted

## Context

The orchestrator consolidates multiple agent outputs. Without a documented standard, synthesis quality and prioritization can vary.

## Decision

Define the responsibilities and evaluation criteria for the **code_quality_orchestrator**.

## Rationale

* **Coherence:** Synthesis should avoid contradictions between agents.
* **Prioritization:** Findings must be ranked by risk, effort, and impact.
* **Execution:** Outputs need to translate into clear next steps.

## Consequences

* Consolidated reports must include a prioritized action list.
* Conflicting agent findings must be reconciled explicitly.
