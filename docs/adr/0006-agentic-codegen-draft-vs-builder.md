# 0006 – Agentic Codegen: Draft vs. Builder

*Status:* Accepted

## Context

Automated code generation accelerates delivery but introduces risk if unverified output reaches production.

## Decision

Separate **Draft** outputs (suggestions) from **Builder** outputs (validated code). Only Builder outputs are eligible for integration.

## Rationale

* **Quality assurance:** Suggestions are reviewed before adoption.
* **Traceability:** Changes are clearly attributable and auditable.
* **Speed with safety:** Drafts accelerate ideation, Builder ensures stability.

## Consequences

* Adds a formal review gate.
* Establishes clear roles between experimentation and production delivery.
