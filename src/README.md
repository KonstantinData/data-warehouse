# Core ELT Agents & Runners

This directory contains the core Python scripts that drive the **Bronze, Silver, and Gold ELT layers** for the data warehouse workflow. It includes  **runners** ,  **agents** , and **templates** that implement modular, reusable logic for data ingestion, transformation, and layering.

---

## Table of Contents

1. Overview
2. Directory Structure
3. Modules & Responsibilities
   * Agents
   * Runners
   * Templates
4. Usage Examples
5. Development Best Practices
6. Contribution & License

---

## 1. Overview

The `src/` directory holds the primary code for executing an ELT pipeline that progresses through:

1. **Bronze Layer** (raw ingestion)
2. **Silver Layer** (cleaning and standardization)
3. **Gold Layer** (business-ready models and aggregated outputs)

The code is designed for modularity, extensibility, and automated execution — supporting both manual CLI runs and integration with higher-level orchestration.

---

## 2. Directory Structure

```
src/
├── agents/
│   ├── load_2_report_agent.py
│   ├── load_3_gold_layer_builder_agent.py
│   └── load_3_gold_layer_planning_agent.py
├── runs/
│   ├── load_1_bronze_layer.py
│   ├── load_2_silver_layer.py
│   └── load_3_gold_layer.py
├── templates/
│   └── load_3_gold_layer_template.py
├── .gitkeep
└── README.md
```

---

## 3. Modules & Responsibilities

### Agents

The `agents/` folder encapsulates logic for orchestration tasks beyond simple running — typically responsible for building, planning, and reporting steps.

#### `load_2_report_agent.py`

**Purpose:**
Generates and orchestrates reporting artifacts based on Silver layer outputs.

**Responsibilities:**

* Aggregates metrics and business KPIs
* Produces reporting tables or dashboards
* Validates Silver layer quality

---

#### `load_3_gold_layer_planning_agent.py`

**Purpose:**
Performs planning for Gold layer model construction.

**Responsibilities:**

* Analyzes Silver layer outputs
* Defines objectives and build plans for Gold models
* Outputs structured build plans (e.g., JSON or config)

---

#### `load_3_gold_layer_builder_agent.py`

**Purpose:**
Constructs the Gold layer artifacts according to the plan defined by the planning agent.

**Responsibilities:**

* Loads templates and mappings
* Renders model definitions
* Executes builds and writes outputs

---

### Runners

The `runs/` folder contains scripts that act as **entry points** to execute each ELT layer.

#### `load_1_bronze_layer.py`

**Purpose:**
Ingests source datasets into the Bronze layer.

**Typical Flow:**

1. Discover raw datasets (e.g., CSV files)
2. Read data into Python DataFrames
3. Write Bronze layer artifacts with metadata and raw snapshots

**Example Execution:**

```bash
python src/runs/load_1_bronze_layer.py \
    --raw-path ../raw \
    --output-path ../artifacts/bronze
```

Optional file selection controls:

```bash
python src/runs/load_1_bronze_layer.py \
    --raw-crm ../raw/source_crm \
    --raw-erp ../raw/source_erp \
    --bronze-root ../artifacts/bronze \
    --crm-file-glob "*.csv" \
    --erp-file-glob "*.csv" \
    --crm-file-exclude "*_tmp.csv"
```

---

#### `load_2_silver_layer.py`

**Purpose:**
Transforms Bronze layer artifacts into standardized Silver outputs.

**Typical Flow:**

1. Read Bronze artifacts
2. Apply cleaning and normalization logic
3. Write Silver layer outputs

---

#### `load_3_gold_layer.py`

**Purpose:**
Executes the Gold layer workflow — using both planning and build agents.

**Typical Flow:**

1. Load Silver layer outputs
2. Invoke planning agent
3. Invoke builder agent
4. Write Gold artifacts

---

### Templates

The `templates/` folder contains reusable logic and definitions for constructing standard Gold layer artifacts.

#### `load_3_gold_layer_template.py`

**Purpose:**
Defines templates for Gold layer models.

**Contents may include:**

* Column mappings
* Model structure definitions
* Functions for templated code generation

These templates are typically consumed by the Gold layer builder agent.

---

## 4. Usage Examples

Use the following example CLI patterns to run your pipeline:

### Bronze Layer

```bash
python src/runs/load_1_bronze_layer.py \
  --raw-path ../raw \
  --output-path ../artifacts/bronze
```

### Silver Layer

```bash
python src/runs/load_2_silver_layer.py \
  --bronze-path ../artifacts/bronze \
  --output-path ../artifacts/silver
```

### Gold Layer

```bash
python src/runs/load_3_gold_layer.py \
  --silver-path ../artifacts/silver \
  --output-path ../artifacts/gold
```

---

## 5. Development Best Practices

**Modularity:**
Keep reusable logic (parsers, readers, writers, metrics) separate from runner scripts.

**Agents:**
Use agents for encapsulating plan/build/report operations that may be reused or called programmatically.

**Templates:**
All repeatable Gold layer logic should be templatized for consistency and reuse.

**Testing:**
Write unit tests for agent logic and runner behavior in the `tests/` directory.

**Logging:**
Include configurable logging levels and structured log output for observability.

---

## 6. Contribution & License

This directory is part of the overall data warehouse project and follows the same contribution and licensing guidelines. Please submit Pull Requests with clear documentation and tests for any additions or modifications.
