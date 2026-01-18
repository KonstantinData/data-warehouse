# Silver Layer Run Report  
**Run ID:** 20260117_172753_#7a02852b  
**Bronze Run ID:** 20260117_172429_#7a02852b  
**Run Start (UTC):** 2026-01-17T17:24:30.038264Z  
**Run End (UTC):** Not explicitly provided for Silver, based on Bronze run: 2026-01-17T17:24:30.217368Z  

---

## Executive Summary

- All six source data files from CRM and ERP systems were successfully ingested at the Bronze layer with no errors or skips, ensuring a full initial data capture.
- Profiling shows well-defined schema structures with candidate keys identified and no duplicate rows, indicating good data uniqueness and integrity at source.
- Several columns require standardization of missing values, trimming of whitespace, and datetime parsing for Silver layer readiness.
- The Silver layer preparation focuses on cleaning but retains the original granularity, enabling detailed analysis of customers, products, sales transactions, and locations.
- The cleansed Silver data enables multiple business problem explorations such as customer retention, product category performance, regional sales differences, and discount impacts with broad stakeholder relevance.

---

## 1. Problem Definition & Objectives

The available datasets provide a rich foundation to explore common and impactful business analytics questions, for example:

- **Declining repeat purchase rates or customer retention**  
  *Impact:* Loss of long-term revenue and customer lifetime value (LTV).  
  *Stakeholders:* Marketing, Sales, Finance, C-level.  
  *Decisions:* Customer segmentation, retention campaign targeting, loyalty program adjustments.  
  *Assumptions to test:* Recency and delivery performance impact repeat purchase likelihood.

- **High return rates or issues within specific product categories**  
  *Impact:* Margin erosion, increased logistics and operational costs.  
  *Stakeholders:* Operations, Product management, Finance.  
  *Decisions:* Product assortment changes, quality control focus, pricing adjustments.  
  *Assumptions:* Some categories have systematically higher return or discount dependency.

- **Strong regional differences in sales performance**  
  *Impact:* Missed revenue opportunities or oversupply in low-performing areas.  
  *Stakeholders:* Sales, Operations, Marketing.  
  *Decisions:* Regional marketing budgeting, inventory allocation, local promotions.  
  *Assumptions:* Country-level preferences or pricing are drivers of sales variances.

- **High dependency on discount-driven sales**  
  *Impact:* Pressure on profitability, potential brand value dilution.  
  *Stakeholders:* Finance, Sales, Marketing.  
  *Decisions:* Review discount strategies, optimize pricing, identify discount-sensitive segments.  
  *Assumptions:* Discount-heavy customers may have higher churn or return behavior.

These problems align closely with the available master and transactional tables covering customers, products, sales, categories, and locations.

---

## 2. Data Identification & Understanding

- **Tables Processed:**  
  - Customers: `cst_info.csv` (CRM), `CST_AZ12.csv` (ERP, demographic extensions)  
  - Products: `prd_info.csv` (CRM)  
  - Product Categories: `PX_CAT_G1V2.csv` (ERP)  
  - Sales Transactions: `sales_details.csv` (CRM)  
  - Locations: `LOC_A101.csv` (ERP)  

- **Key Relationships:**  
  - Customers linked by customer IDs (`cst_id`, `CID`) across tables.  
  - Products linked via product keys (`prd_key`, `ID`).  
  - Sales transactions reference product keys and customer IDs.  
  - Locations linked to customer IDs for geographical analysis.

- **Master Data vs. Transactional Data:**  
  - Master: Customers, Products, Locations, Categories  
  - Transactional: Sales details

Referential integrity and key consistency should be verified during Silver transformations.

---

## 3. Data Ingestion & Integration (Bronze)

- Completed successfully for all six input files (3 CRM, 3 ERP sources).  
- No errors, skips, or partial loads noted.  
- Data captured faithfully with original schema and row counts preserved.  
- Bronze layer provides full traceability with detailed SHA256 file hashes and timestamps.

---

## 4. Data Cleaning & Transformation (Silver)

- Silver layer aims to standardize and clean without aggregation.  
- Key Silver transformation recommendations per table include:  
  - **Date Parsing:** Convert string/integer date fields to datetime types (e.g., `cst_create_date`, `prd_start_dt`, `prd_end_dt`, `BDATE`).  
  - **Missing Values:** Standardize empty or inconsistent missing values in key columns such as gender (`cst_gndr`, `GEN`), product cost, marital status, country codes, and sales prices/sales amounts.  
  - **Whitespace:** Trim leading/trailing spaces in string fields like names and category descriptors.  
- No duplicate rows detected, supporting data uniqueness effort.  
- Candidate keys identified across customer IDs, product IDs, and category IDs enable robust merges and lookups.

---

## 5. Exploratory Data Analysis (Structural Checks)

- **Row counts** align well with expected business scale (e.g., ~18k customers, ~60k sales).  
- **Null value observations:**  
  - Customer gender missing in ~4,578 records; requires imputation or flagging.  
  - Some missing product costs and category maintenance flags need attention.  
  - Minor null sales price and sales amount entries exist.  
- **No duplicate rows** detected, which is a positive sign for data cleanliness.  
- **Key candidates** suggest strong surrogate primary keys exist for joining.

---

## 6. Modeling & Analytical Methods

- Silver data readiness supports:  
  - Constructing enriched customer profiles with demographic and sales behavior features.  
  - Product performance views including cost, lifecycle, and category attributes.  
  - Fact tables combining sales, customer, product, and location attributes for BI and deeper analysis.  
- The cleansed granular data is an ideal foundation for downstream predictive models, clustering, and segmentation workflows.

---

## 7. Validation & Quality Control

- All tables passed schema and row count validation as shown by Bronze logs.  
- No data loading errors or schema mismatches detected.  
- Referential integrity to be validated in Silver (e.g., matching customer and product keys across tables).  
- Silver layer instructions include standardizing missing values and formatting that improve data consistency for BI tools.

---

## 8. Interpretation & Communication

- Silver layer run prepares a "clean but granular" dataset suitable for:  
  - KPI calculations such as Customer Lifetime Value or Return Rate.  
  - Segmentation and market basket analyses.  
  - Cross-dimensional dashboards (customer, product, sales, location).  
- Data quality issues such as missing gender or product cost values should be flagged and possibly imputed before advanced modeling.  
- The current Silver state enables a wide range of business analyses but still requires domain knowledge inputs for assumptions confirmation and interpretation.

---

## 9. Operationalization

- Silver layer to serve as stable data foundation for BI tools like Tableau and ad-hoc queries.  
- Metadata and lineage traceability preserved from Bronze through Silver, supporting reproducibility.  
- Standardized columns and data types promote consistent KPI definitions and reporting interpretations.

---

## 10. Monitoring & Continuous Improvement

- Pipeline logs confirm repeatable steps with stable read and copy times.  
- Future runs can compare row counts and null rates to monitor data source health and ETL stability.  
- Suggested Silver transformations and profiling highlight recurring data quality areas to target for upstream fixes or enhanced transformations.

---

## Schema Overview & Profiling Summary

| Table Name      | Rows  | Columns | Key Candidate(s)                | Nulls Highlights                          | Duplicate Rows | Suggested Silver Transforms                                 |
|-----------------|-------|---------|--------------------------------|------------------------------------------|----------------|-------------------------------------------------------------|
| CST_AZ12.csv    | 18,484| 3       | CID (unique, non-null)          | GEN: 1,472 nulls                         | 0              | Parse BDATE, standardize and trim GEN                       |
| cst_info.csv    | 18,494| 7       | cst_id (99.95% unique), cst_key (99.97%) | Multiple: gender (4,578 nulls), firstname, lastname, marital status, create_date | 0              | Parse create_date, standardize missing values, trim strings |
| LOC_A101.csv    | 18,484| 2       | CID (unique, non-null)          | CNTRY: 332 nulls                        | 0              | Standardize missing CNTRY, trim strings                      |
| prd_info.csv    | 397   | 7       | prd_id (unique)                 | prd_cost: 2 nulls, prd_line: 17 nulls, prd_end_dt: 197 nulls | 0              | Parse date fields, standardize missing, trim prd_line       |
| PX_CAT_G1V2.csv | 37    | 4       | ID, SUBCAT (unique, non-null)  | None                                    | 0              | No obvious transformations needed                           |
| sales_details.csv| 60,398| 9       | None                           | sls_sales: 8 nulls, sls_price: 7 nulls | 0              | Standardize missing sales_price and sales_sales              |

---

## Potential Business Problems and Decisions

Based on the integrated Silver-layer data, analyses could address:

- **Customer Retention & Loyalty:** Segment by gender, location, and purchase history to identify at-risk customers and target retention initiatives.
- **Product Category Management:** Identify categories/subcategories with weak sales or high returns to inform assortment changes and lifecycle management.
- **Regional Sales Performance:** Analyze sales differences across countries to optimize inventory and marketing allocation.
- **Pricing and Discounts Impact:** Examine how discounts correlate with sales volume, returns, and customer churn to refine promotional strategies.

Each problem impacts multiple stakeholders across marketing, sales, finance, operations, and executive management, supporting decisions about targeting, pricing, inventory, and budgeting. Associated assumptions (e.g., demographics linked to LTV, discount behaviors linked to churn) can be tested using Silver data features.

---

## Scope Definition Options

- **Time Scope:**  
  - Last 12 months or year-to-date for recent trends.  
  - Rolling windows of 90 days for seasonality analyses.

- **Geographic Scope:**  
  - Country-level (from `CNTRY` in LOC_A101).  
  - Region-specific groups (e.g., DACH, EMEA) if mapped.

- **Data Scope:**  
  - Customers with at least one purchase to focus on active buyers.  
  - Products with minimum sales volume to concentrate on impactful SKUs.  
  - Active customers filtered by recent purchase activity.

- **System/Source Scope:**  
  - CRM data for customer and sales transactional insights.  
  - ERP data for enriched demographics and product categories.

- **Output Format:**  
  - Interactive Tableau dashboards for KPI monitoring.  
  - Static summary reports for executive review.  
  - ML-ready feature tables for segmentation/clustering workflows.

---

## KPI Candidates for BI/Tableau

- **Customer Lifetime Value (LTV):**  
  *Description:* Estimated revenue contribution over customer lifespan.  
  *Formula:* Average order value × purchase frequency × customer lifespan.

- **Customer Retention Rate:**  
  *Description:* Percentage of customers retained over a period.  
  *Formula:* ((customers_end_period – new_customers) / customers_start_period) × 100%.

- **Average Order Value (AOV):**  
  *Description:* Average value per customer order.  
  *Formula:* total revenue / total orders.

- **Return Rate:**  
  *Description:* Percentage of sold units returned (requires return data if available).  
  *Formula:* (Returned units / sold units) × 100%.

- **Revenue Growth %:**  
  *Description:* Change in revenue between periods.  
  *Formula:* ((Revenue_period_2 – Revenue_period_1) / Revenue_period_1) × 100%.

- **Purchase Frequency:**  
  *Description:* Number of orders relative to unique customers in a period.  
  *Formula:* number of orders / number of unique customers.

- **Conversion Rate:**  
  *Description:* Ratio of purchases to total customers or visits.  
  *Formula:* (Number of purchases / number of unique customers or visits) × 100%.

---

## Segmentation & Clustering Opportunities

- **Features for segmentation:**  
  - Demographics: Age (from `BDATE` in `CST_AZ12`), gender, country.  
  - Behavior: Purchase recency, frequency, monetary value (monetary aggregates from sales).  
  - Product preferences: Category and subcategory affinity (from `PX_CAT_G1V2` and sales).  
  - Discount usage and return behavior (if returns data added).

- **Typical methods:**  
  - K-Means and hierarchical clustering for grouping customer types.  
  - RFM (Recency, Frequency, Monetary value) analysis for value segmentation.  
  - Market basket analysis for product association insights.

- **Example segments:**  
  - High-value loyal customers with frequent repeat purchases.  
  - Discount-sensitive customers prone to churn.  
  - Seasonal or event-driven product category shoppers.  
  - One-time or infrequent buyers who require reactivation.

The Silver layer provides clean, granular data to engineer features that fuel these ML-driven insights in downstream steps.

---

# End of Report

## Automated Bronze Profiling (for Silver Draft)

### Schema Overview
- CST_AZ12.csv: 18484 rows, 3 columns
- cst_info.csv: 18494 rows, 7 columns
- LOC_A101.csv: 18484 rows, 2 columns
- prd_info.csv: 397 rows, 7 columns
- PX_CAT_G1V2.csv: 37 rows, 4 columns
- sales_details.csv: 60398 rows, 9 columns

### Table: CST_AZ12.csv
- Rows: 18484
- Columns: CID, BDATE, GEN
- Inferred types:
  - CID: string
  - BDATE: datetime
  - GEN: string
- Null counts:
  - CID: 0
  - BDATE: 0
  - GEN: 1472
- Duplicate rows: 0
- Key candidates:
  - CID: unique_non_null
- Suggested Silver transforms:
  - Parse BDATE as datetime.
  - Standardize missing values in GEN.
  - Trim whitespace in GEN.

### Table: cst_info.csv
- Rows: 18494
- Columns: cst_id, cst_key, cst_firstname, cst_lastname, cst_marital_status, cst_gndr, cst_create_date
- Inferred types:
  - cst_id: integer
  - cst_key: string
  - cst_firstname: string
  - cst_lastname: string
  - cst_marital_status: string
  - cst_gndr: string
  - cst_create_date: datetime
- Null counts:
  - cst_id: 4
  - cst_key: 0
  - cst_firstname: 8
  - cst_lastname: 7
  - cst_marital_status: 7
  - cst_gndr: 4578
  - cst_create_date: 4
- Duplicate rows: 0
- Key candidates:
  - cst_id: high_uniqueness_99.95%
  - cst_key: high_uniqueness_99.97%
- Suggested Silver transforms:
  - Parse cst_create_date as datetime.
  - Standardize missing values in cst_create_date.
  - Standardize missing values in cst_firstname.
  - Standardize missing values in cst_gndr.
  - Standardize missing values in cst_id.
  - Standardize missing values in cst_lastname.
  - Standardize missing values in cst_marital_status.
  - Trim whitespace in cst_firstname.
  - Trim whitespace in cst_lastname.

### Table: LOC_A101.csv
- Rows: 18484
- Columns: CID, CNTRY
- Inferred types:
  - CID: string
  - CNTRY: string
- Null counts:
  - CID: 0
  - CNTRY: 332
- Duplicate rows: 0
- Key candidates:
  - CID: unique_non_null
- Suggested Silver transforms:
  - Standardize missing values in CNTRY.
  - Trim whitespace in CNTRY.

### Table: prd_info.csv
- Rows: 397
- Columns: prd_id, prd_key, prd_nm, prd_cost, prd_line, prd_start_dt, prd_end_dt
- Inferred types:
  - prd_id: integer
  - prd_key: string
  - prd_nm: string
  - prd_cost: integer
  - prd_line: string
  - prd_start_dt: datetime
  - prd_end_dt: datetime
- Null counts:
  - prd_id: 0
  - prd_key: 0
  - prd_nm: 0
  - prd_cost: 2
  - prd_line: 17
  - prd_start_dt: 0
  - prd_end_dt: 197
- Duplicate rows: 0
- Key candidates:
  - prd_id: unique_non_null
- Suggested Silver transforms:
  - Parse prd_end_dt as datetime.
  - Parse prd_start_dt as datetime.
  - Standardize missing values in prd_cost.
  - Standardize missing values in prd_end_dt.
  - Standardize missing values in prd_line.
  - Trim whitespace in prd_line.

### Table: PX_CAT_G1V2.csv
- Rows: 37
- Columns: ID, CAT, SUBCAT, MAINTENANCE
- Inferred types:
  - ID: string
  - CAT: string
  - SUBCAT: string
  - MAINTENANCE: boolean
- Null counts:
  - ID: 0
  - CAT: 0
  - SUBCAT: 0
  - MAINTENANCE: 0
- Duplicate rows: 0
- Key candidates:
  - ID: unique_non_null
  - SUBCAT: unique_non_null
- Suggested Silver transforms:
  - No obvious Silver transformations detected.

### Table: sales_details.csv
- Rows: 60398
- Columns: sls_ord_num, sls_prd_key, sls_cust_id, sls_order_dt, sls_ship_dt, sls_due_dt, sls_sales, sls_quantity, sls_price
- Inferred types:
  - sls_ord_num: string
  - sls_prd_key: string
  - sls_cust_id: integer
  - sls_order_dt: integer
  - sls_ship_dt: integer
  - sls_due_dt: integer
  - sls_sales: integer
  - sls_quantity: integer
  - sls_price: integer
- Null counts:
  - sls_ord_num: 0
  - sls_prd_key: 0
  - sls_cust_id: 0
  - sls_order_dt: 0
  - sls_ship_dt: 0
  - sls_due_dt: 0
  - sls_sales: 8
  - sls_quantity: 0
  - sls_price: 7
- Duplicate rows: 0
- Key candidates:
  - None detected
- Suggested Silver transforms:
  - Standardize missing values in sls_price.
  - Standardize missing values in sls_sales.
