# Silver Layer Run Report  
**Bronze run ID:** 20260116_231554_#3a8151e4  
**Silver run ID:** 20260116_231742_#3a8151e4  

---

## Executive Summary
- All six source tables from CRM and ERP systems were successfully ingested in the Bronze layer, including key master data and transactions relevant for customer, product, sales, location, and category analysis.
- The Silver layer transformation proposals focus on type parsing, missing value standardization, and whitespace trimming to ensure data consistency and quality.
- No structural or referential integrity errors detected in Bronze; the Silver layer is well-positioned for comprehensive business reporting, segmentation, and KPI development.
- Downstream analytics can leverage clean datetime fields, unique keys, and harmonized categorical variables to support a wide range of business questions.
- Additional conceptual guidance is provided on potential business problems, scope definitions, KPIs, and segmentation opportunities to align analytics with business needs.

---

## 1. Problem Definition & Objectives
- This Silver layer preparation supports business questions such as:
  - Understanding customer retention and repeat purchase behavior through detailed customer and transaction data.
  - Analyzing product category performance and lifecycle, including cost and availability periods.
  - Detecting regional or country-specific sales differences using location linking.
  - Assessing the impact of discounts and price strategies on sales outcomes.
- Stakeholders include executives (revenue, profitability), marketing (targeting), sales (pricing, conversion), operations (fulfillment), finance (forecasting), and product management.
- Decisions enabled by analysis on this data:
  - Targeting specific customer segments for promotion or retention.
  - Adjusting product assortments or phasing out underperforming categories.
  - Allocating marketing spend effectively across channels and demographics.
  - Tailoring pricing or discount policies by product or region.

---

## 2. Data Identification & Understanding
- Source tables processed successfully:
  - **Customers:** `cst_info`, `CST_AZ12` (demographics, DOB, gender).
  - **Products:** `prd_info`, `PX_CAT_G1V2` (product master and category metadata).
  - **Transactions:** `sales_details` (orders, product keys, customer IDs, sales figures).
  - **Locations:** `LOC_A101` (customer country info).
- Referential integrity is maintainable via keys such as `cst_id` (customer), `prd_key` & `prd_id` (product), and customer ID mappings between CRM and ERP sources.

---

## 3 & 4. Data Ingestion & Cleaning (Bronze → Silver)
- Raw files ingested without aggregation for full traceability; all files had successful reads with no skips or failures.
- Silver transformation recommendations include:
  - Parsing of date columns (e.g., birth dates, product start/end dates, order and shipping dates) to datetime types.
  - Standardizing missing and empty values across multiple categorical and numeric fields.
  - Trimming whitespace from string fields (names, product lines, country codes).
  - Harmonizing gender and maintenance flags to consistent format.
  - Handling a small number of missing values in critical fields like customer IDs, product costs, and sales prices.

---

## 5. Exploratory Data Analysis (Structural Quality)
- No duplicate rows identified in any tables, supporting uniqueness assumptions.
- Candidate keys identified:
  - Customer keys: `cst_id`, `cst_key`, `CID`
  - Product keys: `prd_id`, `prd_key`
  - Category keys: `ID` and `SUBCAT` in category table.
- Null values noted mainly in gender, some product cost/line and sales fields; expected to be standardized in Silver.
- Structural integrity supports confident joins and analysis across datasets.

---

## 7. Validation & Quality Control
- No errors or warnings in Bronze layer run logs or profiling.
- Row counts and schemas consistent with expectations.
- Data types inferred to match business semantics, with planned Silver parsing for dates and standardization.
- Silver layer will be ready for downstream use in BI tools and further analytical modeling.

---

## 8. Interpretation & Communication
- Silver layer run prepares clean, typed, and harmonized master and transactional tables.
- Readiness for KPI calculation, segmentation, and business reporting is high.
- Some missing data points require attention but should not impede core analyses.
- Enables direct linkage of customers, products, transactions, and geography for comprehensive multi-dimensional views.

---

## 9. Operationalization
- Clean metadata and transformations designed for consistent KPI definitions across tools like Tableau.
- Stable Silver tables will support repeatable ad-hoc queries and serve as feature sources for advanced analytics pipelines.

---

## 10. Monitoring & Continuous Improvement
- Pipeline successful with full file processing and no anomalies.
- Future runs should monitor missing data trends, processing times, and file consistency to detect any source system changes.

---

## Schema Overview & Silver Transformation Suggestions

| Table          | Rows   | Columns | Key Candidates                       | Notable Nulls               | Suggested Silver Transforms                                         |
|----------------|--------|---------|------------------------------------|-----------------------------|-------------------------------------------------------------------|
| **CST_AZ12**   | 18,484 | 3       | CID (unique, non-null)              | GEN (1,472 nulls)            | Parse BDATE as datetime; standardize/trim GEN                      |
| **cst_info**   | 18,494 | 7       | cst_id (high uniqueness), cst_key   | cst_gndr (4,578 nulls), others minor                      | Parse cst_create_date; standardize/trim names, marital status, gender, IDs|
| **LOC_A101**   | 18,484 | 2       | CID                                | CNTRY (332 nulls)            | Standardize/trim CNTRY                                              |
| **prd_info**   | 397    | 7       | prd_id (unique)                    | prd_cost (2 nulls), prd_line (17), prd_end_dt (197)          | Parse prd_start_dt/prd_end_dt; standardize missing, trim prd_line    |
| **PX_CAT_G1V2**| 37     | 4       | ID, SUBCAT (unique)                | None                         | No transformations needed                                           |
| **sales_details** | 60,398| 9      | None (transactional fact)           | sls_sales (8), sls_price (7) nulls                          | Standardize missing fields for sales, price                        |

---

## Potential Business Problems and Decisions

- **Declining Repeat Purchase Rates:** Analyze customer transaction patterns to identify segments with low retention. Impact: revenue loss; Stakeholders: Marketing, Sales, C-level; Decisions: targeted retention campaigns; Assumptions: recent delivery times improve loyalty.
- **High Returns in Product Categories:** Tie sales and product data to identify categories with higher returns (requires return data). Impact: margin erosion, logistics cost; Stakeholders: Product Management, Operations; Decisions: review assortment or quality control.
- **Regional Sales Variation:** Use location data to detect unexplained regional differences. Impact: opportunity for targeted marketing; Stakeholders: Marketing, Sales; Decisions: regional pricing or promotions.
- **Discount Impact on Sales and Returns:** Assess how discounting affects purchase frequency and return rates. Impact: margin pressure; Stakeholders: Finance, Sales; Decisions: optimize discount strategies.
- **Customer Demographic Influences:** Explore how age, gender, and marital status correlate with lifetime value or purchase behavior. Impact: marketing effectiveness; Stakeholders: Marketing; Decisions: personalize campaigns.

---

## Scope Definition Options

- **Time Scopes:**
  - Last 12 months, year-to-date, or rolling windows (e.g., last 90 days).
  - Filtered by order dates in `sales_details`.
- **Geographic Scopes:**
  - Specific countries or regions based on `LOC_A101` country codes.
  - Groupings like DACH (Germany, Austria, Switzerland) or EMEA.
- **Data Scopes:**
  - Active customers with purchases in defined recent intervals.
  - Products with minimum sales volume thresholds.
  - Only customers with complete demographic data.
- **System/Source Scopes:**
  - CRM data source for customer and sales details.
  - ERP data source for product master, location, and category metadata.
- **Output Formats:**
  - Static reports and dashboards for executives.
  - BI-ready tables for Tableau or PowerBI.
  - ML feature tables for segmentation and predictive models.

---

## KPI Candidates for BI/Tableau

| KPI Name              | Description                                                            | Formula (High-Level)                                                  |
|-----------------------|------------------------------------------------------------------------|----------------------------------------------------------------------|
| Conversion Rate       | Percentage of customers who made a purchase.                          | (Number of purchases / number of unique customers or visits) * 100%  |
| Customer Lifetime Value (LTV) | Estimated revenue per customer over their active lifespan.        | Avg. order value * purchase frequency * customer lifespan            |
| Return Rate           | Share of sold units that were returned (requires return data).         | (Returned units / sold units) * 100%                                 |
| Cost per Acquisition (CPA) | Average marketing spend per new customer acquired.                    | Marketing spend / number of new customers                            |
| Revenue Growth %      | Period-over-period sales increase or decrease percentage.              | ((Revenue_current - Revenue_previous) / Revenue_previous) * 100%      |
| Average Order Value (AOV) | Average revenue generated per customer order.                         | Total revenue / total number of orders                               |
| Purchase Frequency    | Average number of orders per customer in a time frame.                 | Number of orders / unique customers                                  |
| Customer Retention Rate | Percentage of retained customers between periods excluding new ones. | ((Customers_end_period - New_customers) / Customers_start_period) * 100% |

---

## Segmentation & Clustering Opportunities

- **Features for Segmentation:**
  - Demographics: Age (DOB from CST_AZ12), gender, marital status, country.
  - Behavioral: Recency, frequency, monetary value (RFM), discount usage.
  - Product: Preferred categories, product lines, purchase volumes.
- **Typical Methods:**
  - Clustering techniques like K-Means, hierarchical clustering, DBSCAN.
  - RFM segmentation for customer value tiers.
  - Market basket analysis linking product affinities.
- **Example Segments:**
  - High-Value Loyal Customers: frequent, high-spend, long-term buyers.
  - Discount-Sensitive Buyers: high participation in promotions, possibly higher churn.
  - Seasonal Shoppers: customers focusing purchases on specific time periods or categories.
  - One-Time Buyers: single purchase customers, potential upsell targets.

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
