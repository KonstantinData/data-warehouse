# Prompt Analysis Outputs (Ephemeral)

## Scope
- Defines the policy for prompt analysis outputs under `tmp/prompt_analysis/`.
- Does not cover authoritative prompt artifacts or run outputs.

## Guarantees
- Outputs here are non-versioned and non-authoritative.
- Contents are safe to delete at any time.

## Non-goals
- Retaining audit evidence or system-of-record data.
- Acting as an input dependency for pipeline logic.

## Lifecycle and Cleanup
- Outputs are short-lived diagnostics from local prompt experiments.
- Clean up after each investigation or on a fixed schedule.

## Relationship to Reproducibility
- No reproducibility guarantees apply to this directory.
- Promote validated findings to ADRs or documentation when needed.

## Why These Outputs Exist
- Enable quick, local inspection of prompt behaviors without affecting artifacts.

## Rule
- No business logic may depend on `tmp/prompt_analysis/` outputs.

## Links
- **Upstream:** Prompt controls: `docs/prompts/README.md`.
- **Downstream:** Ephemeral policy: `tmp/README.md`.
