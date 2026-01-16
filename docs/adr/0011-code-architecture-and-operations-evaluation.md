# 0011 – Code Architecture and Operations Evaluation

*Status:* Accepted

## Context

The code review workflow relies on specialized agents. A clear, shared definition of the architecture and operations agent ensures consistent reviews and actionable feedback across runs.

## Decision

Define the responsibilities and evaluation criteria for the **code_architecture_and_operations** agent.

## Rationale

* **Consistency:** Reviews focus on architectural boundaries and operational readiness.
* **Risk control:** Operational gaps are highlighted before deployment.
* **Alignment:** Teams interpret findings in the same way.

## Consequences

* Reviews must cover architecture structure, deployment behavior, and runtime stability.
* Findings are expected to include operational risks and remediation guidance.
