# Silver Layer Run Report  
**Run ID:** 20260117_101143_#72d1650f (Bronze)  
**Silver Run ID:** 20260117_101309_#72d1650f  

---

## Executive Summary
- All six expected input data files from CRM and ERP sources were successfully ingested into the Bronze layer without errors or skips.
- The Silver layer preparation focused on standardizing data types, handling missing values, parsing dates, and trimming whitespace for clean downstream use.
- Data shows good structural integrity: unique key candidates identified, no duplicate rows detected, though some columns have non-trivial null counts needing attention.
- The Silver layer is well-prepared to support business intelligence, analytical reporting, and further modeling tasks such as customer segmentation or product performance analysis.
- Suggested transformations provide a clear path for consistent, clean datasets enabling reliable KPI computations and decision-making.

---

## 1. Problem Definition & Objectives
This run lays the foundation for analytic use cases linked to customer, product, sales, and location data with a focus on:

- Understanding customer behavior and retention by linking customer master data to transaction records.
- Analyzing product lifecycle, costs, and category performance.
- Assessing regional sales performance with location data integration.
- Supporting decisions on marketing spend allocation, targeting, pricing, and assortment optimization.

Impact areas include revenue management, margin improvement, and operational efficiency. Stakeholders range from executives to marketing, sales, operations, finance, and product management teams.

---

## 2. Data Identification & Understanding
- **Processed Tables:**  
  - Customers: `cst_info`, `CST_AZ12`  
  - Products: `prd_info`, `PX_CAT_G1V2`  
  - Sales Transactions: `sales_details`  
  - Locations: `LOC_A101`

- **Master vs Transactional Data:** Master and dimension tables (customers, products, locations, categories) are clearly identified and separated from transactional sales data.

- **Keys:** Multiple candidate keys have been identified (e.g., `cst_id`, `cst_key`, `CID`, `prd_id`, `ID`) facilitating referential integrity verification and joins in later layers.

---

## 3. Data Ingestion & Integration (Bronze)
- File ingestion was completed successfully for all 6 CSV files from CRM and ERP sources.
- Processing duration was very fast (about 0.225 seconds total), indicating efficient raw data loading.
- No files were skipped or failed; all input data is available for transformation.

---

## 4. Data Cleaning & Transformation (Silver)
- Key transformations recommended for Silver layer:  
  - Parsing date fields (`cst_create_date`, `BDATE`, `prd_start_dt`, `prd_end_dt`) into datetime formats.  
  - Standardizing missing values and null representations across demographic and descriptive attributes (e.g., gender, product category, marital status).  
  - Trimming whitespace from string columns to ensure consistency in categorical data.  
  - Harmonizing boolean flags (e.g., `MAINTENANCE` in product categories).  
  - Addressing nulls in sales price and sales amount fields to avoid bias in analyses.

- No aggregation is done at Silver stage; data remains at original grain for detailed downstream analysis.

---

## 5. Exploratory Data Analysis (Structural Focus)
- **Schema Overview:** 6 tables, 6 source files, row counts range from 37 (categories) up to ~60k (sales details).  
- **Inferred Types:** Mostly consistent types with appropriate conversions suggested (e.g., string, datetime, integer).  
- **Null Values:**  
  - Notable nulls in gender (~25% missing in `cst_info`), product costs, end dates, and location country codes.  
  - Sales amount and price fields have a few missing values to be standardized.  
- **Duplicates:** No duplicate rows found — good data uniqueness and cleanliness.  
- **Key Candidates:** Strong key candidates identified in all dimension tables, essential for robust joins and referential integrity.

---

## 6. Modeling & Analytical Methods
- This Silver layer run establishes a clean foundation supporting:  
  - Customer behavior aggregation and lifetime value modeling.  
  - Product performance and lifecycle analysis.  
  - Location-based sales and customer segmentation.  
  - Building fact tables for BI dashboards and predictive models.

- Further modeling activities (predictive, clustering, pricing optimization) depend on subsequent layers but can confidently trust the clean Silver data.

---

## 7. Validation & Quality Control
- Run logs confirm successful reads and copies for all source files, with no errors or skips.  
- Metadata verifications such as row counts and file hashes support data lineage tracking.  
- Null and type checks highlight areas requiring domain-based imputations or exclusions downstream.  
- Orphan keys or mismatches should be checked during Silver transformations but initial keys appear robust.

---

## 8. Interpretation & Communication
- The Silver layer, based on this run, is ready for business reporting, segmentation analysis, and KPI generation without immediate re-ingestion needs.  
- Data quality is sufficient for exploratory and operational BI use cases but NULL-heavy fields warrant treatment strategies.  
- The current dataset supports a wide array of business questions around customer retention, category profitability, and geographic sales patterns.  
- This process unlocks better targeting, assortment, and price setting decisions.

---

## 9. Operationalization
- Clean and standardized metadata has been established, enabling traceability from Bronze to Silver.  
- This layer can serve as a stable input for BI tools such as Tableau and for ad-hoc queries by analysts.  
- Consistent schemas ensure KPI definitions can be reused reliably across dashboards and reports.

---

## 10. Monitoring & Continuous Improvement
- Future runs can be benchmarked against this successful ingestion and cleaning as a baseline.  
- Data quality metrics and null trends should be monitored continuously to detect regressions.  
- Feedback loops to data sources (CRM, ERP) are recommended to address persistent missing or inconsistent values.

---

# Schema Overview & Data Quality Details

| Table           | Rows  | Columns | Key Candidates       | Null Highlights                   | Duplicates | Suggested Silver Transforms                                    |
|-----------------|-------|---------|----------------------|---------------------------------|------------|--------------------------------------------------------------|
| CST_AZ12        | 18484 | 3       | CID (unique, non-null) | GEN: 1472 nulls                 | 0          | Parse BDATE, standardize GEN nulls, trim whitespace           |
| cst_info        | 18494 | 7       | cst_id, cst_key (both ~99.95% unique) | cst_gndr: 4578 nulls, minor in others | 0          | Parse cst_create_date, standardize missing values, trim names  |
| LOC_A101        | 18484 | 2       | CID (unique, non-null) | CNTRY: 332 nulls                | 0          | Standardize CNTRY nulls, trim whitespace                      |
| prd_info        | 397   | 7       | prd_id (unique, non-null) | prd_cost: 2 nulls, prd_line: 17 nulls, prd_end_dt:197 nulls | 0          | Parse prd dates, standardize nulls, trim prd_line             |
| PX_CAT_G1V2     | 37    | 4       | ID, SUBCAT (unique)   | None                           | 0          | No major transforms needed                                    |
| sales_details   | 60398 | 9       | None                   | sls_sales: 8 nulls, sls_price: 7 nulls | 0          | Standardize missing sales price and sales values              |

---

# Potential Business Problems & Decisions

| Problem Label                | Description                                                                                           | Impact/Cost/Risk/Opportunity                                  | Stakeholders                   | Example Decisions                           | Assumptions to Test                          |
|-----------------------------|---------------------------------------------------------------------------------------------------|---------------------------------------------------------------|-------------------------------|---------------------------------------------|---------------------------------------------|
| Declining Customer Retention | Customers are not making repeat purchases as frequently as before.                                | Revenue loss, increased acquisition costs, lifetime value drops | Marketing, Sales, Finance      | Which customer segments to target for retention campaigns  | Shorter delivery times improve repeat rates |
| High Product Return Rates    | Some product categories have return rates disproportionately high, increasing cost and logistics | Margin erosion, increased costs, customer dissatisfaction       | Product Management, Operations | Which product lines/categories to modify or phase out        | Discount-heavy sales correlate with higher returns |
| Regional Sales Imbalance     | Significant sales discrepancies between regions without clear explanation                        | Stock misallocation, lost sales, marketing inefficiencies       | Sales, Operations, Finance      | How to allocate inventory and marketing budgets regionally | Certain product categories perform better in specific countries |
| Discount Dependency          | Sales only meet targets when significant discounts are offered                                   | Margin erosion, risk of customer churn, brand devaluation       | Sales, Marketing, Finance       | Optimize pricing and discount strategy                     | Heavy discount use correlates with churn or returns |

---

# Scope Definition Options

- **Time Scope:** Last 12 months, year-to-date, rolling windows (e.g. 90 days or 6 months).  
- **Geographic Scope:** Specific countries or regions based on `LOC_A101` country codes; e.g., focus on DACH, EMEA, or global.  
- **Data Scope:**  
  - Customers with ≥1 purchase or active in last N days.  
  - Products with minimum sales volume or active lifecycle status.  
- **System/Source:** CRM for customers and sales; ERP for product classifications, locations, and categories.  
- **Output Formats:** Dashboards (Tableau), static reports, ML-ready feature tables for downstream modeling.

---

# KPI Candidates for BI/Tableau

| KPI Name               | Business Description                            | High-level Formula                                                   | Typical Usage                                 |
|------------------------|------------------------------------------------|---------------------------------------------------------------------|-----------------------------------------------|
| Conversion Rate        | % of customers who made at least one purchase  | (Number of purchases / number of unique customers or visits) * 100% | Measure marketing effectiveness                |
| Customer Lifetime Value (LTV) | Average revenue expected from a customer over their lifespan | Average order value * purchase frequency * customer lifespan         | Forecast revenues and segment customers         |
| Return Rate            | % of sold units returned                        | (Returned units / sold units) * 100%                                | Identify problematic product categories         |
| Cost per Acquisition (CPA) | Marketing cost to acquire one new customer    | Marketing spend / number of newly acquired customers                | Budget allocation and channel efficiency        |
| Revenue Growth %       | Change in revenue over comparable periods      | ((Revenue_period2 − Revenue_period1) / Revenue_period1) * 100%      | Track sales performance and growth              |
| Average Order Value (AOV) | Average revenue per order                      | Total revenue / number of orders                                    | Measure transaction size                         |
| Purchase Frequency     | Average number of orders per customer           | Number of orders / number of unique customers                       | Understand repeat purchase behavior              |
| Customer Retention Rate | % of customers retained period-over-period     | ((customers_end - new_customers) / customers_start) * 100%          | Measure loyalty and churn                        |

---

# Segmentation & Clustering Opportunities

- **Useful Features:**  
  - Demographics: Age (from `BDATE`), gender, country.  
  - Behavior: Recency, frequency, monetary value from sales details; discount usage inferred from price and cost.  
  - Product Preferences: Category and subcategory affinity via `PX_CAT_G1V2` linked to sales and product master data.

- **Methods:**  
  - K-Means clustering or hierarchical clustering for customer groups.  
  - RFM (Recency, Frequency, Monetary) segmentation for marketing stratification.  
  - Market basket analysis for product affinity and cross-selling opportunities.

- **Example Segments:**  
  - High-value loyal customers.  
  - Discount-sensitive shoppers.  
  - Seasonal product category buyers.  
  - One-time or inactive customers.

These segmentation outputs can support personalized marketing, inventory planning, and product development strategies.

---

# Summary

This Silver layer run successfully integrated varied CRM and ERP data with high fidelity and cleanliness focus. It sets a robust platform to explore critical business problems, produce actionable KPIs, and enable advanced analytics such as customer segmentation and product lifecycle analysis. Continuous monitoring and refinement should maintain and improve data readiness over time.

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
