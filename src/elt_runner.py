"""
DESCRIPTION
Performs a Python-paced ELT of CRM and ERP raw CSV sources into a versioned bronze layer.
Each run produces:
  artifacts/bronze/elt/<timestamp>_#<random>/
    data/
      *.csv  (raw copies)
      metadata.yaml
      run_log.txt
    reports/
      elt_report.html

Includes timing, success/failure details, and audit metadata.

REQUIRES:
  - pandas
  - pyyaml
  - jinja2 (for simple HTML report)
"""

import os
import shutil
import uuid
import yaml
import pandas as pd
import traceback
from datetime import datetime

# Paths (relative to project root)
RAW_CRM = os.path.join("raw", "source_crm")
RAW_ERP = os.path.join("raw", "source_erp")
BRONZE_ROOT = os.path.join("artifacts", "bronze", "elt")

# Files to include (patterns)
CRM_FILES = ["cst_info.csv", "prd_info.csv", "sales_details.csv"]
ERP_FILES = ["CST_AZ12.csv", "LOC_A101.csv", "PX_CAT_G1V2.csv"]

# Report templates (minimal)
HTML_REPORT_TEMPLATE = """
<html>
<head><title>ELT Run Report</title></head>
<body>
<h1>ELT Run Report: {{ run_id }}</h1>
<p>Run start: {{ start_dt }}</p>
<p>Run end: {{ end_dt }}</p>
<table border="1">
<tr><th>file</th><th>status</th><th>rows</th><th>duration(s)</th><th>error</th></tr>
{% for r in results %}
<tr>
<td>{{ r.file }}</td>
<td>{{ r.status }}</td>
<td>{{ r.rows }}</td>
<td>{{ r.duration }}</td>
<td>{{ r.error or "" }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def write_metadata_yaml(metadata, path):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(metadata, f)

def write_html_report(context, path):
    from jinja2 import Template
    template = Template(HTML_REPORT_TEMPLATE)
    html = template.render(**context)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    start_dt = datetime.utcnow()
    run_id = f"{start_dt.strftime('%Y%m%d_%H%M%S')}_#{str(uuid.uuid4())[:8]}"
    elt_dir = os.path.join(BRONZE_ROOT, run_id)
    data_dir = os.path.join(elt_dir, "data")
    report_dir = os.path.join(elt_dir, "reports")

    # Create folders
    ensure_dir(data_dir)
    ensure_dir(report_dir)

    # Logging
    log_file = os.path.join(data_dir, "run_log.txt")
    def log(msg):
        timestamp = datetime.utcnow().isoformat()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {msg}\n")
        print(f"{timestamp} {msg}")

    results = []
    metadata = {
        "run_id": run_id,
        "start_dt": start_dt.isoformat(),
        "source_crm": CRM_FILES,
        "source_erp": ERP_FILES,
        "tables": {},
    }

    # Helper to process files
    def process_file(src_root, filename):
        file_path = os.path.join(src_root, filename)
        dest_path = os.path.join(data_dir, filename)
        rec = {"file": filename, "status": None, "rows": 0, "duration": 0, "error": None}
        try:
            t0 = datetime.utcnow()
            df = pd.read_csv(file_path)
            duration = (datetime.utcnow() - t0).total_seconds()
            rec["duration"] = duration
            rec["rows"] = len(df)
            rec["status"] = "OK"
            rec["schema"] = list(df.columns)

            # Save copy
            df.to_csv(dest_path, index=False)

            # Persist metadata for this table
            metadata["tables"][filename] = {
                "rows": len(df),
                "schema": list(df.columns),
                "duration": duration,
            }
            log(f"SUCCESS {filename} rows={len(df)} dur={duration:.2f}s")

        except Exception as e:
            rec["status"] = "FAILED"
            rec["error"] = str(e)
            log(f"ERROR {filename} {e}")
            traceback_str = traceback.format_exc()
            log(traceback_str)

        results.append(rec)

    # Process CRM
    log("BEGIN CRM SOURCE LOAD")
    for f in CRM_FILES:
        process_file(RAW_CRM, f)

    # Process ERP
    log("BEGIN ERP SOURCE LOAD")
    for f in ERP_FILES:
        process_file(RAW_ERP, f)

    end_dt = datetime.utcnow()
    metadata["end_dt"] = end_dt.isoformat()
    metadata["duration_total_s"] = (end_dt - start_dt).total_seconds()

    # Write metadata.yaml
    write_metadata_yaml(metadata, os.path.join(data_dir, "metadata.yaml"))

    # Write HTML report
    report_ctx = {"run_id": run_id, "start_dt": start_dt, "end_dt": end_dt, "results": results}
    write_html_report(report_ctx, os.path.join(report_dir, "elt_report.html"))

    log(f"ELT run completed in {(end_dt - start_dt).total_seconds():.2f}s")

if __name__ == "__main__":
    main()
