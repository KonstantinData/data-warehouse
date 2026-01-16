# 0004 – Orchestrator as Single Entry Point

*Status:* Accepted

## Context

Ad-hoc pipeline execution leads to inconsistent scheduling, unclear ownership, and uneven observability.

## Decision

A centralized **orchestrator** is the single entry point for all pipeline runs. It owns scheduling, dependencies, and execution ordering.

## Rationale

* **Predictability:** Consistent run windows and dependency management.
* **Accountability:** One system is responsible for execution and monitoring.
* **Scalability:** New jobs are integrated through a standard process.

## Consequences

* Initial setup and governance of orchestration infrastructure.
* Unified operational rules across all pipelines.
