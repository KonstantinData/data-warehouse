# Agent Control Contracts

## Scope
- Defines control logic responsibilities for agents in `src/agents/`.
- Does not describe model behavior or pipeline implementation details.

## Guarantees
- Agents implement control flow and decision logic for the ELT pipeline.
- Agent outputs are written to `artifacts/` (authoritative) or `tmp/` (ephemeral).
- Agent interfaces are stable and documented in runner contracts.

## Non-goals
- Defining system-of-record data outputs (those are in `artifacts/`).
- Acting as the source of architectural truth (see ADRs).

## Role in the System
- Agents execute structured planning and build steps as invoked by runners.
- Agents coordinate inputs, validations, and output formatting for downstream runs.

## Separation of Concerns
- **System prompts:** global governance and safety constraints (owned centrally).
- **Working prompts:** agent-specific task instructions (owned by agent maintainers).
- Agent code must not override system-level constraints.

## Determinism and Audit Limitations
- Agent control flow is deterministic; model outputs can be nondeterministic.
- Auditability depends on prompt versioning plus persisted outputs and logs.

## Output Locations
- Authoritative outputs: `artifacts/` run directories.
- Ephemeral outputs: `tmp/` and `tmp/prompt_analysis/`.

## Ownership and Responsibilities
- Agent maintainers own prompt alignment and output validation.
- Repository maintainers approve changes that alter agent contracts.

## Links
- **Upstream:** Prompt controls: `docs/prompts/README.md`.
- **Downstream:** Runner entry points: `src/runs/` and `artifacts/README.md`.
