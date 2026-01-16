# Agentic ELT Data Warehouse

**Value proposition:** A local, run-based ELT system that transforms raw CRM/ERP CSV inputs into Medallion-layer artifacts for data engineers and reviewers who need reproducible, auditable pipeline outputs and lineage metadata.

**Non-goals / out of scope:**

- Production orchestration, scheduling, or deployment infrastructure
- Cloud storage integrations or external databases
- Streaming ingestion or real-time processing
- Enterprise-grade security controls beyond local environment hygiene

---

## 1. Project Overview

**What this system does (end-to-end):**

- Ingests raw CSV sources from `raw/source_crm` and `raw/source_erp` into Bronze snapshots.
- Applies deterministic cleansing/standardization into Silver outputs.
- Builds Gold marts and aggregates from Silver outputs.
- Emits run metadata and HTML reports for each layer, plus a cross-step summary report.

**Design intent:**

- Demonstrate a complete, run-based Medallion pipeline on local filesystem artifacts.
- Provide an auditable footprint (metadata, logs, reports) for each run.
- Support agent-driven drafting/building steps while keeping runnable scripts as the system of record.

**Target personas:**

- Data Engineer (implementation and extension)
- Reviewer/Architect (assessment of pipeline design and governance)
- Maintainer (operational ownership and iteration)

**Status and intended usage:**

- **Status:** In progress; functional runners exist, coverage and CI are not finalized.
- **Intended usage:** Local execution and portfolio review; not production-hardened.

---

## 2. System Architecture

**High-level flow:**

```
Raw CSV sources
   → Bronze (snapshot + metadata)
   → Silver (clean + standardized)
   → Gold (marts + aggregates)
   → Reports (per-layer + summary)
```

**Medallion responsibilities:**

- **Bronze:** immutable snapshots with file-level metadata and checksums.
- **Silver:** normalized, cleaned datasets with 1:1 table parity to Bronze inputs.
- **Gold:** business-ready dimensional and aggregate outputs.

**Run-based execution model:**

- Each layer writes to a **run_id**-scoped directory under `artifacts/`.
- Runs are **append-only**; re-runs produce a new run_id rather than overwriting outputs.
- Downstream steps default to the latest available upstream run when no run_id is supplied.

**Artifact lifecycle and storage locations:**

- Bronze: `artifacts/bronze/<run_id>/...`
- Silver: `artifacts/silver/<run_id>/...`
- Gold: `artifacts/gold/marts/<run_id>/...`
- Orchestrator logs: `artifacts/orchestrator/<run_id>/logs/...`
- Summary report: `artifacts/reports/<run_id>/summary_report.*`

**Reference diagram:** `docs/workflow_schema.jpg`

For design rationale and conventions (run_id format, layering, artifacts), see the ADR index: `docs/adr/0000-adr-index.md`.

---

## 3. Repository Structure

Curated view of key directories:

```
src/         # Runners, agents, and templates (system logic)
artifacts/   # Run outputs and reports (local filesystem)
tmp/         # Ephemeral, non-versioned analysis outputs

docs/        # Architecture docs, ADRs, prompts

tests/       # Unit/integration tests (expanding)
```

**Never commit:**

- `.env` files or any secrets
- `tmp/` outputs or prompt analysis artifacts
- Generated run outputs under `artifacts/` and local raw data under `raw/`

---

## 4. Execution Model (Single Source of Truth)

**Entry points:**

- **Bronze:** `src/runs/load_1_bronze_layer.py`
- **Silver:** `src/runs/load_2_silver_layer.py`
- **Gold:** `src/runs/load_3_gold_layer.py`
- **End-to-end orchestration:** `src/runs/orchestrator.py`

**Canonical commands:**

```bash
python src/runs/load_1_bronze_layer.py \
  --raw-crm raw/source_crm \
  --raw-erp raw/source_erp \
  --bronze-root artifacts/bronze

python src/runs/load_2_silver_layer.py <bronze_run_id>

python src/runs/load_3_gold_layer.py <silver_run_id> [gold_run_id]
```

**Expected behavior:**

- Bronze snapshots raw files and writes `metadata.yaml`, `run_log.txt`, and `elt_report.html`.
- Silver reads a specific Bronze run (or latest by default), applies standardization, and writes Silver outputs plus reports.
- Gold reads a specific Silver run (or latest by default), validates required schemas, and writes marts/aggregates plus reports.

**Idempotency and re-run behavior:**

- Each run writes to a new run_id, ensuring immutability of previous outputs.
- To re-run with a fixed run_id, pass it explicitly (Bronze: `--run-id`, Gold: optional argument).

---

## 5. Quick Start (Reproducible)

### Prerequisites

- Python **3.10+**
- `git`

### Environment setup

```bash
git clone https://github.com/KonstantinData/agentic-elt-data-warehouse.git
cd agentic-elt-data-warehouse
python -m venv .venv
source .venv/bin/activate     # macOS / Linux
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### Prepare raw data

```
raw/
├── source_crm/   # CSV inputs
└── source_erp/   # CSV inputs
```

### Minimal end-to-end run (manual)

```bash
python src/runs/load_1_bronze_layer.py
python src/runs/load_2_silver_layer.py
python src/runs/load_3_gold_layer.py
```

**Expected outputs:**

- Bronze: `artifacts/bronze/<run_id>/data` + `reports/elt_report.html`
- Silver: `artifacts/silver/<run_id>/data` + `reports/elt_report.html`
- Gold: `artifacts/gold/marts/<run_id>/data` + `reports/gold_report.html`

### End-to-end orchestration (optional)

The orchestrator executes Bronze → Silver → Gold and writes a summary report. It requires a `.env` file and valid LLM credentials unless `--skip-llm` is used.

```bash
python src/runs/orchestrator.py --skip-llm
```

Summary output:

```
artifacts/reports/<orchestrator_run_id>/summary_report.*
```

---

## 6. Configuration & Secrets

- Configuration is managed via environment variables and a root-level `.env` file.
- Start from `configs/.env.example` and add required keys locally (never commit `.env`).
- The orchestrator validates the presence of `OPENAI_API_KEY` or `OPEN_AI_KEY`.
- Layer paths can be overridden via env vars (e.g., `BRONZE_ROOT`, `SILVER_ROOT`, `GOLD_ROOT`).

---

## 7. Data Quality & Governance

- **Bronze:** captures file-level metadata, hashes, and run summaries.
- **Silver:** applies standardization and lightweight normalization with row-level tracking.
- **Gold:** validates required schemas before producing marts/aggregates.
- **Lineage & metadata:** each layer writes `metadata.yaml` and a human-readable report.
- **PII/GDPR:** no built-in masking; treat inputs as non-sensitive or enforce handling upstream.

For governance details and standards, consult the ADRs: `docs/adr/0000-adr-index.md`.

---

## 8. Observability & Operations

- **Logging:** `run_log.txt` per layer and orchestrator logs under `artifacts/orchestrator/`.
- **Run tracing:** `run_id` is propagated through Bronze → Silver → Gold.
- **Failure modes:** downstream steps are skipped if upstream fails or no new data is detected.
- **Backfill strategy:** run layers with explicit run_id inputs to target historical snapshots.
- **Performance/scalability:** optimized for local CSV-scale workloads; not tuned for large-scale IO.

---

## 9. Testing Strategy

- **Unit tests:** core transformation logic and helpers.
- **Integration tests:** end-to-end runs against fixture CSVs.
- **Pipeline tests:** schema validation and artifact integrity checks.

Run tests locally:

```bash
pytest
```

**Definition of Done:**

- New logic is covered by tests.
- Artifacts and metadata are updated as expected.
- ADRs are updated if architectural behavior changes.

---

## 10. Architecture Decisions

- ADR index: `docs/adr/0000-adr-index.md`
- Add or update an ADR when changing:
  - layer responsibilities
  - run_id or artifact layout conventions
  - data quality or governance rules
  - agent/orchestrator execution flow

---

## 11. Agentic / Prompt-Based Analysis

- **Purpose:** draft plans and builders for Silver/Gold layers and code-quality evaluations.
- **Prompts location:** `docs/prompts/` (see `docs/prompts/README.md`).
- **Analysis outputs:** `tmp/prompt_analysis/` (non-versioned; see `tmp/prompt_analysis/README.md`).

---

## 12. Contribution & Review

**Review the system in this order:**

1. This README
2. ADR index (`docs/adr/0000-adr-index.md`)
3. Runners in `src/runs/`
4. Agents in `src/agents/`

**Branching and commit expectations:**

- Use short-lived feature branches.
- Keep commits scoped and descriptive.
- Update tests and ADRs when behavior changes.

**Quality gates for PRs:**

- Linting and tests pass (where applicable).
- Documentation reflects behavior.
- No secrets or generated artifacts are committed.

---

## 13. Roadmap

- Align `.env.example` with orchestrator requirements.
- Add fixture data and integration tests for all three layers.
- Add CI pipeline for linting and tests.

---

## 14. License & Legal

- License: MIT (`LICENSE`)
- Data usage: raw inputs are user-provided; ensure you have rights to use any data placed under `raw/`.
