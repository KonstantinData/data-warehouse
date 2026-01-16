# Temporary Outputs (Non-Authoritative)

## Scope
- Defines the policy for ephemeral outputs stored under `tmp/`.
- Does not cover authoritative run artifacts (see `artifacts/`).

## Guarantees
- `tmp/` contents are non-versioned and non-authoritative.
- `tmp/` outputs may be deleted at any time without impacting system correctness.

## Non-goals
- Storing reproducible artifacts or system-of-record data.
- Serving as an input dependency for business logic.

## Lifecycle and Cleanup
- Outputs are short-lived and should be cleaned regularly.
- Automated cleanup is preferred over manual deletion.

## Relationship to Reproducibility
- `tmp/` outputs are excluded from reproducibility guarantees.
- Any insight required for audit must be promoted to `artifacts/` or documentation.

## Why This Exists
- Supports ad-hoc analysis, prompt experimentation, and debugging without polluting artifacts.

## Rule
- No business logic may depend on `tmp/` outputs.

## Links
- **Upstream:** Prompt and agent controls: `docs/prompts/README.md`, `src/agents/README.md`.
- **Downstream:** Authoritative outputs: `artifacts/README.md`.
