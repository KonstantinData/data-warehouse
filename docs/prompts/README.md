# Prompt Controls

## Scope
- Defines how prompts in `docs/prompts/` are governed and used by agents.
- Does not describe model behavior or runtime configuration.

## Guarantees
- Prompts are versioned control documents for agent behavior.
- Prompt text is reviewed and change-controlled like code.
- Prompts do not store outputs or run logs.

## Non-goals
- Serving as a source of truth for business logic.
- Explaining LLM internals or performance characteristics.

## Role in the System
- Prompts provide deterministic input for agent workflows executed by `src/agents/`.
- Prompts codify decisions about task structure, validations, and output formats.

## Separation of Concerns
- **System prompts:** global constraints and safety rules (owned by maintainers).
- **Working prompts:** task-specific instructions used by individual agents.
- Agents must not embed system-level policy inside working prompts.

## Determinism and Audit Limitations
- Prompt text is deterministic; model outputs are not.
- Audits rely on prompt versioning plus stored outputs in `artifacts/` and `tmp/`.

## Outputs and Storage
- Agent outputs are written under `artifacts/` (authoritative) or `tmp/` (ephemeral).
- Prompts do not store outputs or execution logs.

## Ownership and Responsibilities
- Repository maintainers approve prompt changes.
- Agent owners document required inputs/outputs and validate expected formats.

## Links
- **Upstream:** ADR governance: `docs/adr/README.md`.
- **Downstream:** Agent contracts: `src/agents/README.md`.
