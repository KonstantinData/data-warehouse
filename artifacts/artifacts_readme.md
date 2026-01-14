# Artifacts / Bronze Layer

This folder contains the **Bronze staging layer outputs** of the ELT process.

## Purpose

The Bronze layer serves as a **central landing zone** for raw data ingested from
multiple source systems:

- **CRM source:** raw CRM tables under raw/source_crm
- **ERP source:** raw ERP tables under raw/source_erp

This Python ELT process does not transform or cleanse, but reliably copies
source files into a **versioned run folder**, capturing:

- File copies of all source tables
- Extraction durations and row counts
- Table schemas (column lists)
- Run identifiers and timestamps
- Structured metadata and log files
- A simple HTML summary report

## Structure

Within `artifacts/bronze/elt/` each run creates a new folder:

artifacts/bronze/elt/
├── 20260114_2249_#9random/
│ ├── data/
│ │ ├── cust_info.csv
│ │ ├── prod_info.csv
│ │ ├── sales_info.csv
│ │ ├── CST_AZ12.csv
│ │ ├── LOC_A101.csv
│ │ ├── PX_CAT_G1V2.csv
│ │ ├── metadata.yaml
│ │ └── run_log.txt
│ └── reports/
│ └── elt_report.html

markdown
Code kopieren

### `data/`

Contains **raw copies of source files** for this run, plus:

- `metadata.yaml`: run metadata including file schemas and row counts
- `run_log.txt`: log messages showing start, success/failure, and timing

### `reports/`

Contains:

- `elt_report.html`: a simple HTML summary showing timing, status, rows.

## Run IDs

Each run uses a unique identifier:

YYYYMMDD_HHMMSS_#`<random>`

makefile
Code kopieren

Example:

20260114_2249_#9a1b2c3d

markdown
Code kopieren

This ensures reproducibility and easy traceability.

## Why This Matters

- **Reproducibility:** Each run’s outputs and logs are preserved.
- **Auditability:** Times, row counts, and errors are logged explicitly.
- **Separation:** Raw sources are not overwritten — each run is fresh.
- **Extensibility:** Downstream Silver/Gold transforms can read from these
  stable Bronze files.

---

## Dependencies

This ELT runner uses standard Python libraries:

- pandas
- pyyaml
- jinja2

Install via:

pip install pandas pyyaml jinja2

yaml
Code kopieren

---

## How to Run

From project root:

python src/elt_runner.py

yaml
Code kopieren

This will create the next Bronze ELT output folder automatically.

---

## ❗ Notes

- This Bronze layer is the baseline for all downstream transformations.
- No cleaning or normalization happens at this stage.
- Downstream Silver and Gold transforms will operate on these stable CSV
  snapshots.

✔ Requirements (add to requirements.txt)
shell
Code kopieren
pandas>=1.5.0
PyYAML>=6.0
Jinja2>=3.0
Additional Features You Have
▪ Time stamps and duration metrics
Each file load logs duration and time.

▪ Success & failure detection
Every processed file logs status in run_log.txt and in the
HTML summary report.

▪ Metadata capture
The metadata.yaml file contains run global and per-file metadata.

Next Steps (optional)
If you want, I can generate:

css
Code kopieren
A) Silver transform script
B) Gold KPI script
C) Unit tests for ETL
D) CI/CD automation snippet (PowerShell or GitHub Action)
Reply with which ones you want.
