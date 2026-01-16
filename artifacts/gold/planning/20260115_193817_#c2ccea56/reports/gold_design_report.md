# Phase-1 Gold Layer Design Report
**Silver Run ID:** 20260115_193817_#c2ccea56

---

## 1. Executive Summary

- The Silver layer provides clean, validated, and standardized datasets covering customers, products, sales transactions, locations, and product categories with no data quality issues detected.
- The Gold layer will focus on enabling BI and analytics to address key business problems: customer retention, product return rates, and regional sales performance.
- Proposed Gold architecture includes a star schema with fact sales and dimension tables for customers, products, locations, and categories, supporting KPI calculations and segmentation.
- Emphasis on time-bound and geography-scoped data marts aligned with business scope (last 12 months, DACH/EMEA regions).
- Data quality and join keys are robust but require attention to key consistency and date conversions for accurate time analysis.
- Next steps include structural exploratory analysis, KPI implementation, and dashboard prototyping to validate design and support business decisions.

---

## 2. Available Silver Tables and Their Role

| Table Name       | Role in Data Model                      | Key Columns / Notes                          |
|------------------|---------------------------------------|----------------------------------------------|
| **sales_details.csv** | Fact table capturing transactional sales data | Order number, product key, customer ID, order/ship/due dates, sales amount, quantity, price |
| **cst_info.csv**       | Customer dimension with detailed attributes | Customer ID/key, name, marital status, gender, creation date |
| **CST_AZ12.csv**       | Customer demographics (age, gender) | Customer ID, birthdate, gender (overlaps with cst_info) |
| **LOC_A101.csv**       | Customer location dimension | Customer ID, country code |
| **prd_info.csv**       | Product master dimension | Product ID/key, name, cost, product line, start/end dates |
| **PX_CAT_G1V2.csv**    | Product category dimension | Category ID, category, subcategory, maintenance flag |

---

## 3. Proposed Gold-Layer Objectives (BI & Analytics Only)

- **Enable KPI tracking** for sales effectiveness, customer retention, product returns, and regional performance.
- **Support customer segmentation** for targeted marketing and retention strategies.
- **Provide clean, integrated, and time-aware data marts** for fast, reliable dashboarding and reporting.
- **Facilitate root cause analysis** of business problems such as declining repeat purchases and high return rates.
- **Deliver aggregated and detailed views** to balance performance and analytical depth.
- **Ensure alignment with business scope**: last 12 months, DACH/EMEA geographies, active customers and products.

---

## 4. Recommended Gold Data Marts

### 4.1 Sales Fact Table
- **Business Purpose:** Central repository of all sales transactions for revenue, volume, and timing analysis.
- **Grain:** One row per sales order line (order number + product key).
- **Primary Keys:** Composite key (sls_ord_num, sls_prd_key).
- **Measures:** Sales amount, quantity sold, price, shipping and due dates (for delivery time calculations).
- **Dimensions:** Customer, product, date (order, ship, due), location, category (via product).

### 4.2 Customer Dimension
- **Business Purpose:** Store enriched customer attributes for segmentation and retention analysis.
- **Primary Key:** Customer ID (cst_id or cst_key).
- **Attributes:** Name, gender, birthdate, marital status, customer creation date, country (joined from LOC_A101).
- **Notes:** Merge demographic info from CST_AZ12 and cst_info for completeness.

### 4.3 Product Dimension
- **Business Purpose:** Product master data for category and product line analysis, cost and lifecycle tracking.
- **Primary Key:** Product ID/key (prd_id or prd_key).
- **Attributes:** Product name, cost, product line, start/end dates, category and subcategory (joined from PX_CAT_G1V2).

### 4.4 Location Dimension
- **Business Purpose:** Geographic segmentation of customers for regional sales performance analysis.
- **Primary Key:** Customer ID (CID).
- **Attributes:** Country code, potentially extended to region (DACH, EMEA) via mapping.

### 4.5 Product Category Dimension
- **Business Purpose:** Categorize products for return rate and margin analysis by category/subcategory.
- **Primary Key:** Category ID (ID).
- **Attributes:** Category, subcategory, maintenance flag.

### 4.6 Aggregate Tables (Optional Phase-1)
- **Business Purpose:** Pre-aggregated KPIs by time, region, product category for dashboard performance.
- **Grain:** Aggregated by month, country, product category.
- **Measures:** Total sales, average order value, return rates (if return data available), order counts.

---

## 5. Join and Data-Quality Considerations

- **Keys:**
  - Customer keys: cst_id (int64) and CID (string) appear in different tables; mapping or standardization needed.
  - Product keys: prd_key (string) consistent across sales and product tables.
  - Location keyed by CID, linking to customer dimension.
- **Cardinalities:**
  - One-to-many from customers to sales (multiple orders per customer).
  - One-to-many from products to sales lines.
  - One-to-one or many-to-one for customer demographics and location.
- **Potential Pitfalls:**
  - Date fields in sales are integers (likely YYYYMMDD) and require conversion to date type for time intelligence.
  - Overlapping customer demographic info (CST_AZ12 vs cst_info) needs reconciliation to avoid duplication.
  - Missing explicit return data in Silver layer; return rate KPI may require additional data or proxy measures.
  - Geography scope filtering requires mapping countries in LOC_A101 to DACH/EMEA regions.
- **Data Quality:**
  - No missing critical keys or failed files reported, ensuring reliable joins.
  - Standardized dtypes facilitate integration.

---

## 6. Risks & Assumptions

- **Missing Data:**
  - No explicit returns data in current Silver layer; return rate KPI may be incomplete or require future integration.
  - Discount usage data is not present, limiting analysis of discount impact on returns.
- **Fragile Areas:**
  - Customer key inconsistencies between tables may cause join errors if not harmonized.
  - Date fields stored as integers require careful parsing to avoid errors in time-based analysis.
  - Product lifecycle dates (start/end) may be incomplete or require validation for active product filtering.
- **Assumptions:**
  - Customers with recent purchases and minimum sales volume can be filtered reliably using sales and customer creation dates.
  - Country codes in LOC_A101 are accurate and mappable to business regions.
  - Sales data covers the full last 12 months and year-to-date periods for scope compliance.

---

## 7. Recommended Next Steps for Implementation and Testing

1. **Data Harmonization:**
   - Standardize customer keys across all customer-related tables.
   - Convert integer date fields to proper date types.
   - Reconcile overlapping customer demographic data into a single dimension.

2. **Exploratory Data Analysis:**
   - Perform structural and statistical analysis on Silver tables to validate assumptions and identify anomalies.
   - Map country codes to business regions (DACH, EMEA).

3. **Gold Layer Build:**
   - Develop star schema data marts as outlined, starting with sales fact and core dimensions.
   - Implement filters for scope (time, geography, active customers/products).

4. **KPI Calculation:**
   - Define and compute KPIs (conversion rate, LTV, return rate, AOV, retention) using Gold data marts.
   - Validate KPI accuracy against business expectations.

5. **Dashboard Prototyping:**
   - Build initial BI dashboards focusing on business problems and stakeholder needs.
   - Incorporate drill-downs by customer segments, product categories, and regions.

6. **Testing & Validation:**
   - Perform join integrity and data completeness tests.
   - Validate performance and refresh times for Gold layer.
   - Engage business users for feedback and iterative improvements.

7. **Documentation & Governance:**
   - Document data lineage from Silver to Gold.
   - Define update frequency and monitoring for Gold layer freshness and quality.

---

This Phase-1 Gold layer design provides a solid foundation for BI and analytics, enabling actionable insights into customer behavior, product performance, and regional sales dynamics. It sets the stage for future advanced analytics and ML feature store integration.
