

# Data Warehouse Project (Python ELT-First)

A fully completed, portfolio-ready **Python-driven Data Warehouse** demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices using raw CSV sources and ELT workflows. ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## Table of Contents

1. Project Overview
2. Architecture & Design
3. Features
4. Getting Started
   * Prerequisites
   * Setup & Installation
   * Configuration
5. Folder Structure
6. ELT Process
   * Bronze Layer
   * Silver Layer
   * Gold Layer
7. Artifacts & Outputs
8. Reporting & Metadata
9. Testing
10. Dependencies
11. Contributing
12. License

---

## 1. Project Overview

This repository implements a **local, Python-first Data Warehouse pipeline** that:

* Ingests raw CSV source files (CRM + ERP)
* Transforms and stores data in a reproducible **Bronze ELT layer**
* Provides outputs for BI, analytics, and downstream ML workflows

The approach is intentionally engine-agnostic at the Bronze level — no SQL engine or external database is required to generate staging artifacts. ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 2. Architecture & Design

The architecture follows a **Medallion pattern** with an ELT pipeline:

```
Raw Sources (CSV)
       ↓
Bronze Layer (Python ELT snapshots)
       ↓
Silver Layer (clean & standardized)
       ↓
Gold Layer (business-ready aggregates)
       ↓
Consume (BI, reporting, ML)
```

*Bronze layer generation is implemented in Python and snapshots raw data for reproducibility.* ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 3. Features

* Automatic discovery and ingestion of CRM + ERP CSV sources
* Timestamped Bronze layer snapshotting
* Lineage metadata capture
* ELT runner with built-in logging and reporting
* Reusable artifacts for analytics and machine learning
* Modular structure enabling Silver/Gold layer extension
* Test placeholders and pytest integration
* Comprehensive documentation and configuration templates ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 4. Getting Started

### Prerequisites

* Python **3.10+**
* `git`

### Setup & Installation

```bash
git clone https://github.com/KonstantinData/agentic-elt-data-warehouse.git
cd agentic-elt-data-warehouse
python -m venv .venv
source .venv/bin/activate     # macOS / Linux
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### Configuration

Place raw CSV source files under the following structure:

```
raw/
├── source_crm/
└── source_erp/
```

Ensure environment variables or config templates in `configs/` are set according to your environment. ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 5. Folder Structure

```
agentic-elt-data-warehouse/
├── analytics/         # BI artifacts & definitions
├── artifacts/         # Built outputs & snapshots
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   └── reports/
├── configs/           # Configuration templates
├── docs/              # Architecture & standards docs
├── ml/                # ML experiments
├── raw/               # Raw source CSVs
├── scripts/           # Support scripts
├── src/               # Python ELT implementation
├── tests/             # Test files
├── .gitignore
├── requirements.txt
├── pyproject.toml
└── LICENSE
```

This modular design encourages extensibility across layers. ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 6. ELT Process

### Bronze Layer (Python ELT)

The Bronze layer is exclusively generated by the ELT runner in Python:

* Discover raw files under `raw/source_crm` and `raw/source_erp`
* Load CSVs as pandas DataFrames
* Record schema, row counts, and timing metrics
* Write structured snapshot folders under:

```
artifacts/bronze/elt/<timestamp>_<id>/
```

Each snapshot contains:

* Raw file copies (`data/*.csv`)
* Metadata (`metadata.yaml`)
* ELT logs (`run_log.txt`)
* A human-readable HTML run summary ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 7. Artifacts & Outputs

Artifacts generated from ELT runs are organized in:

```
artifacts/
├── bronze/
├── silver/
├── gold/
└── reports/
```

Outputs provide:

* Auditable lineage metadata
* Snapshot results for analytics
* Standardized staging data ready for Silver layer processing ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 8. Reporting & Metadata

HTML reports and YAML metadata files capture:

* Run start/end timestamps
* Per‐file durations
* Success/failure status
* Schema breakdowns
* Row count summaries

These artifacts support data auditing and reproducibility. ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 9. Testing

Tests are located in the `tests/` directory and can be executed with:

```bash
pytest
```

Add tests corresponding to new modules to maintain quality. ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 10. Dependencies

Dependencies are managed via `requirements.txt` and include:

* `pandas>=2.0.3`
* `PyYAML>=6.0`
* `python-dotenv>=1.0.0`
* `Jinja2>=3.0`

Refer to `pyproject.toml` for development metadata. ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 11. Contributing

To contribute:

1. Fork the repository
2. Create a feature branch
3. Add tests and code
4. Open a Pull Request

Follow the code style and include tests for new functionality. ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))

---

## 12. License

This project is licensed under the  **MIT License** . ([GitHub](https://github.com/KonstantinData/agentic-elt-data-warehouse "GitHub - KonstantinData/agentic-elt-data-warehouse: A fully completed, portfolio-ready SQL Data Warehouse demonstrating end-to-end data ingestion, transformation, modeling, governance, and documentation best practices."))
