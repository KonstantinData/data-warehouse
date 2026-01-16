# Generated Outputs & ELT Artifacts

This directory contains all **generated outputs** from ELT runs across Bronze, Silver, and Gold layers — plus machine-learning artifacts and global reports. It is purpose-built to support reproducibility, traceability, and analytical consumption.

---

## Table of Contents

1. Purpose
2. Structure
3. Bronze Layer Artifacts
4. Silver Layer Artifacts
5. Gold Layer Artifacts
6. Machine Learning Artifacts
7. Global Reports
8. Best Practices
9. Cleanup & Retention

---

## 1. Purpose

The `artifacts/` folder is the canonical storage location for all persistent outputs created by your ELT pipeline. It organizes artifacts by layer and run, ensuring each run is identifiable, immutable, and usable for analytics, reporting, or model training.

---

## 2. Directory Structure

```
artifacts/
├── bronze/
│   └── <timestamp>_#<hash>/
│       ├── data/
│       └── reports/
├── silver/
│   └── <timestamp>_#<hash>/
│       ├── data/
│       ├── reports/
│       └── tmp/
├── gold/
│   ├── marts/
│   └── planning/
├── ml/
└── reports/
```

Each section below explains the purpose of these folders.

---

## 3. Bronze Layer Artifacts

**Location:**

```
artifacts/bronze/<timestamp>_#<hash>/
```

**Contents:**

* `data/`: Raw ingested data slices (CSV, Parquet, etc.)
* `reports/`: Metadata and run diagnostics (schema, row counts, timing)

**Purpose:**

The Bronze layer captures the **initial ingestion** of source data with minimal transformation — suitable for lineage tracking and replays.

---

## 4. Silver Layer Artifacts

**Location:**

```
artifacts/silver/<timestamp>_#<hash>/
```

**Contents:**

* `data/`: Cleaned and standardized data sets
* `reports/`: Summary metrics and validation reports
* `tmp/`: Temporary/staging files used during processing

**Purpose:**

Silver artifacts represent **cleaned, standardized, and validated** versions of Bronze data — ready for downstream use in modelling or business logic.

---

## 5. Gold Layer Artifacts

```
artifacts/gold/
├── marts/
├── planning/
```

**`planning/`:**
Intermediate artifacts used during Gold layer planning (e.g., build plans, config templates).

**`marts/`:**
Final business-ready artifacts such as dimensional marts, aggregates, or curated data models.

**Purpose:**

The Gold layer contains artifacts that are **business-ready and consumption-optimized** — whether for dashboards, BI tools, or reporting.

---

## 6. Machine Learning Artifacts

```
artifacts/ml/
```

**Purpose:**

This directory stores data and outputs specific to machine learning workflows, including:

* Feature sets
* Training snapshots
* Model input datasets
* Performance metrics

These artifacts are derived from Silver/Gold outputs and optimized for ML consumption.

---

## 7. Global Reports

```
artifacts/reports/
```

This folder contains **cross-layer or global analytics reports** such as:

* Summarized run dashboards (e.g., combined Bronze/Silver/Gold summaries)
* KPIs and audit dashboards
* Consolidated logs or validation outputs

Reports here are not tied to a single timestamped run but may reference multiple runs or layers.

---

## 8. Best Practices

### Immutable Runs

Each run is timestamped + hash-tagged (e.g., `20260115_174457_#c2cea56`) to guarantee immutability and auditability. **Do not modify** artifacts after creation.

### Naming Conventions

Ensure consistency across folders:

```
YYYYMMDDHHMMSS_#<hash>
```

This ensures chronological ordering and traceability to version control.

### Metadata & Lineage

Always inspect the metadata in `reports/` for:

* Schema definitions
* Source row counts
* Validation checkpoints
* Transformation logs

This supports debugging and compliance requirements.

---

## 9. Cleanup & Retention

Establish archive and retention policies tailored to storage constraints and governance needs. Common guidelines include:

* Retain the latest **N runs** per layer
* Archive older runs to cold storage
* Clean `tmp/` directories periodically

Cleanup operations should **never delete** artifacts used by current analytic dashboards or ML models.

---

## Summary

| Layer         | Location                               | Purpose                                |
| ------------- | -------------------------------------- | -------------------------------------- |
| Bronze        | `artifacts/bronze/<timestamp>_#<hash>` | Raw ingestion snapshots                |
| Silver        | `artifacts/silver/<timestamp>_#<hash>` | Standardized, validated data           |
| Gold          | `artifacts/gold/marts`                 | Business-ready models                  |
| Gold Planning | `artifacts/gold/planning`              | Intermediate build plans               |
| ML            | `artifacts/ml/`                        | Machine learning preparatory artifacts |
| Reports       | `artifacts/reports/`                   | Cross-layer and consolidated analytics |

* a **sample artifact file index**
* or a **policy template** for artifact retention

Let me know what’s next!
