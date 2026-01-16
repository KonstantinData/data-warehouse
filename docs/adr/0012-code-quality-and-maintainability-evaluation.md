# 0012 – Code Quality and Maintainability Evaluation

*Status:* Accepted

## Context

The code quality workflow needs a stable definition for how maintainability and readability are assessed so that recommendations are comparable across agents and runs.

## Decision

Define the responsibilities and evaluation criteria for the **code_quality_and_maintainability** agent.

## Rationale

* **Clarity:** Findings emphasize readability, structure, and long-term maintenance.
* **Actionability:** Recommendations focus on concrete refactors and test coverage.
* **Continuity:** Similar issues are assessed using the same criteria.

## Consequences

* Reviews must assess naming, modularity, complexity, and test support.
* Outputs should prioritize issues that reduce maintenance cost over time.
