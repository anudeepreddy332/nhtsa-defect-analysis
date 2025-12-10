# NHTSA Automotive Defect Analysis: Silent Recall Detection
![status](https://img.shields.io/badge/NHTSA-Defect_Analysis-blue)
![sql](https://img.shields.io/badge/Stack-SQL-green)
![tableau](https://img.shields.io/badge/Visualization-Tableau-orange)

**Author:** Anudeep  
**Tools:** PostgreSQL, Python, Tableau Public  
**Data Source:** [NHTSA Office of Defects Investigation](https://www.nhtsa.gov/nhtsa-datasets-and-apis)  
**Live Dashboard:** [Tableau Public Link](https://public.tableau.com/app/profile/anudeep.reddy.mutyala/viz/NHTSA_Silent_Recall_Analysis/Dashboard1)

---

## Project Overview

This project analyzes **500,000+ consumer complaints** filed with the National Highway Traffic Safety Administration (NHTSA) from 2015-2024 to identify **"Silent Recalls"**—vehicles with high complaint volumes but zero manufacturer-issued recalls. By combining SQL-based data engineering with interactive dashboards, this analysis quantifies safety risks and estimates potential cost savings for early intervention.

### Business Problem
Automotive manufacturers face significant financial and reputational risks when safety defects go unaddressed. Early detection of trending issues before they escalate to mandatory recalls can:
- Reduce warranty claim costs by **10-15%** (~$400M potential savings across top components)
- Prevent injury-related litigation
- Improve brand trust and customer retention

### Key Finding
**2017 Chevrolet Volt** has **1,145 complaints** (primarily electrical system failures) with **zero recalls issued**. Complaint rates are **increasing quarterly** despite declining overall volume, suggesting defects worsen with vehicle age.

---

## Data Architecture

### Datasets
1. **FLAT_CMPL.txt** (~500K rows): Consumer complaints (1995-2024)
2. **FLAT_RCL.txt** (~50K rows): Manufacturer-issued recalls (2010-2024)
3. **Safercar_data.csv** (~10K rows): Vehicle safety ratings & specifications

### Database Schema

```sql
-- Complaints Table (49 columns)

CREATE TABLE flat_cmpl (
    CMPLID TEXT,
    MAKETXT TEXT,
    MODELTXT TEXT,
    YEARTXT TEXT,
    COMPDESC TEXT,
    CDESCR TEXT,
    CRASH TEXT,
    INJURED NUMERIC,
    DEATHS NUMERIC,
    LDATE TEXT
    …
);

-- Recalls Table (29 columns)

CREATE TABLE flat_rcl (
    CAMPNO    TEXT,    -- NHTSA recall number
    MAKETXT   TEXT,
    MODELTXT  TEXT,
    YEARTXT   TEXT,
    COMPNAME  TEXT,    -- Component description
    DESC_DEFECT TEXT,  -- Defect summary
    POTAFF    NUMERIC, -- Potential units affected
    …
);
```

### ETL Process
1. Create database
```
createdb nhtsa_defects
```
2. Ingest data (TAB-delimited, LATIN1 encoding for legacy gov data)
```
psql -d nhtsa_defects -c “\copy flat_cmpl FROM ‘FLAT_CMPL.txt’ WITH (FORMAT csv, DELIMITER E’\t’, QUOTE E’\b’, HEADER false, NULL ‘’, ENCODING ‘LATIN1’);”
```

**ETL Parameters Explained:**
- `DELIMITER E'\t'`: TAB-separated (NHTSA standard)
- `QUOTE E'\b'`: Disable CSV quoting (prevents parse errors in complaint narratives)
- `ENCODING 'LATIN1'`: Legacy government data encoding (pre-UTF8)
- `NULL ''`: Treat empty strings as NULL

---

## Methodology

### 1. Exploratory Data Analysis (EDA)
Validated data quality and identified normalization issues:

```sql
-- Check top complained vehicles (2020 model year)
SELECT
  MAKETXT,
  MODELTXT,
  COUNT(*) AS complaint_count
FROM flat_cmpl
WHERE YEARTXT = '2020'
GROUP BY MAKETXT, MODELTXT
ORDER BY complaint_count DESC
LIMIT 10;
```

**Findings:**
- Model names inconsistent (e.g., "F-150" vs "F150")
- ~15% of complaints have `MAKETXT = 'UNKNOWN'` (excluded from analysis)
- Component descriptions (`COMPDESC`) use hierarchical format: `CATEGORY:SUBCATEGORY:DETAIL`

### 2. Core Analysis: Silent Recall Detection

Created a **materialized view** joining complaints and recalls on `(MAKE, MODEL, YEAR)`:

```sql
CREATE VIEW vehicle_risk_summary AS
SELECT
  c.MAKETXT,
  c.MODELTXT,
  c.YEARTXT,
  COUNT(DISTINCT c.CMPLID) AS total_complaints,
  COUNT(DISTINCT r.CAMPNO) AS total_recalls
FROM flat_cmpl c
LEFT JOIN flat_rcl r
  ON c.MAKETXT = r.MAKETXT
  AND c.MODELTXT = r.MODELTXT
  AND c.YEARTXT = r.YEARTXT
WHERE c.YEARTXT BETWEEN '2015' AND '2024'
  AND c.MAKETXT NOT IN ('UNKNOWN', 'FIRESTONE', 'GOODYEAR') -- Exclude tires
GROUP BY c.MAKETXT, c.MODELTXT, c.YEARTXT;
```


### 3. Risk Scoring
Categorized vehicles by severity using business rules:

```sql
-- Create a table of vehicle risk scores (materialized snapshot)
CREATE TABLE vehicle_risk_scores AS
SELECT
  *,
  CASE
    WHEN total_recalls = 0 AND total_complaints > 500 THEN 'CRITICAL'
    WHEN total_recalls = 0 AND total_complaints > 200 THEN 'HIGH'
    WHEN total_complaints > total_recalls * 10 THEN 'MEDIUM'
    ELSE 'LOW'
  END AS risk_category
FROM vehicle_risk_summary
WHERE total_complaints > 50;
```


### 4. Component Pareto Analysis (80/20 Rule)
```sql
-- Component analysis (top 50 by complaint count)
CREATE TABLE component_analysis AS
SELECT
  COMPDESC,
  COUNT(*) AS total_complaints,
  SUM(CASE WHEN CRASH = 'Y' THEN 1 ELSE 0 END) AS crash_related,
  SUM(INJURED) AS total_injuries,
  SUM(DEATHS) AS total_deaths
FROM flat_cmpl
WHERE YEARTXT BETWEEN '2015' AND '2024'
GROUP BY COMPDESC
ORDER BY total_complaints DESC
LIMIT 50;
```

**Result:** Top 10 components account for **65%** of all complaints (Air Bags, Electrical System, Service Brakes).

---

## Advanced SQL Queries

### Query 1: Repeat Offenders (Window Functions)
Identify vehicles with chronic issues across multiple years:

```sql
-- Repeat offenders: Corrected two-step approach to rank models per year
WITH yearly_aggregates AS (
  SELECT
    MAKETXT,
    MODELTXT,
    YEARTXT,
    COUNT(*) AS complaints
  FROM flat_cmpl
  WHERE YEARTXT BETWEEN '2015' AND '2024'
  GROUP BY MAKETXT, MODELTXT, YEARTXT
),
yearly_rankings AS (
  SELECT
    MAKETXT,
    MODELTXT,
    YEARTXT,
    complaints,
    ROW_NUMBER() OVER (PARTITION BY YEARTXT ORDER BY complaints DESC) AS rank_in_year
  FROM yearly_aggregates
)
SELECT
  MAKETXT,
  MODELTXT,
  COUNT(DISTINCT YEARTXT) AS years_in_top10,
  SUM(complaints) AS total_complaints,
  STRING_AGG(YEARTXT, ', ' ORDER BY YEARTXT) AS problem_years
FROM yearly_rankings
WHERE rank_in_year <= 10
GROUP BY MAKETXT, MODELTXT
HAVING COUNT(DISTINCT YEARTXT) >= 3
ORDER BY years_in_top10 DESC;
```

**Key Insight:** Ford F-150 appeared in top 10 for **8 consecutive years** (11,837 total complaints), indicating systemic manufacturing defects.

### Query 2: Cost-Benefit Analysis (CTEs)
Estimate financial impact using industry-standard costs:

```sql
-- Component cost analysis (top 10) — numeric then formatted for display
WITH component_costs AS (
  SELECT
    COMPDESC,
    COUNT(*) AS total_complaints,
    SUM(CASE WHEN CRASH = 'Y' THEN 1 ELSE 0 END) AS crash_count,
    SUM(INJURED) AS total_injuries,
    (COUNT(*) * 5000
     + SUM(CASE WHEN CRASH = 'Y' THEN 1 ELSE 0 END) * 50000
     + SUM(INJURED) * 100000
    )::bigint AS estimated_cost
  FROM flat_cmpl
  WHERE YEARTXT BETWEEN '2015' AND '2024'
  GROUP BY COMPDESC
)
SELECT
  COMPDESC,
  total_complaints,
  crash_count,
  total_injuries,
  TO_CHAR(estimated_cost, 'FM$999,999,999')        AS total_cost,
  TO_CHAR((estimated_cost * 0.10)::bigint, 'FM$999,999,999') AS savings_if_reduced_10pct
FROM component_costs
ORDER BY estimated_cost DESC
LIMIT 10;
```


**Result:** **$404M potential savings** if top 10 components' complaint rates were reduced by 10%.

---

## Dashboard & Visualizations

**[Live Dashboard on Tableau Public](https://public.tableau.com/app/profile/anudeep.reddy.mutyala/viz/NHTSA_Silent_Recall_Analysis/Dashboard1)**

### Chart 1: Top 10 Silent Recall Candidates
- **Type:** Horizontal bar chart
- **Encoding:** Color by risk category (Red = CRITICAL, Orange = HIGH)
- **Insight:** 2017 Volt dominates with 1,145 complaints

### Chart 2: Component Pareto Analysis
- **Type:** Horizontal bar chart
- **Encoding:** Color by total injuries (darker = more severe)
- **Insight:** Air Bags caused 4,979 injuries ($811M estimated cost)

### Chart 3: Complaint Trends (2020-2024)
- **Type:** Multi-line time series
- **Insight:** Volt complaints increasing quarterly (Q4 spike) despite declining annual volume—suggests age-related defects worsening

---

## Key Findings

1. **Silent Recall Risk:** 20 vehicle models have >200 complaints with zero recalls (Volt, Forester, Maverick Hybrid lead)
2. **Component Failures:** Electrical systems and air bags account for **$1.2B** in estimated costs
3. **Trend Alert:** 2017 Chevy Volt shows **rising quarterly complaint rates** (potential ticking time bomb for GM)
4. **Cost Savings:** Early intervention on top 3 components could save manufacturers **$185M annually**

---

## Technical Skills Demonstrated

- **SQL:** Complex joins (LEFT JOIN), window functions (ROW_NUMBER, PARTITION BY), CTEs, aggregate functions, data type casting
- **Data Engineering:** ETL pipeline design, schema normalization, encoding handling (LATIN1), bulk data ingestion
- **Data Visualization:** Tableau dashboard design, color encoding, KPI design, time-series analysis
- **Business Analytics:** Risk scoring, cost-benefit analysis, Pareto principle application, trend detection

---

## Repository Structure
    nhtsa-defect-analysis/
    │
    ├── data/
    │   ├── FLAT_CMPL.txt           # Raw complaints data (not uploaded, 336MB)
    │   ├── FLAT_RCL_POST_2010.txt  # Raw recalls data
    │   └── Safercar_data.csv       # Vehicle specs
    │
    ├── sql/
    │   ├── schema.sql              # Table creation scripts
    │   ├── repeat_offenders.sql    # Window function query
    │   └── cost_analysis.sql       # CTE-based financial model
    │
    ├── exports/
    │   ├── vehicle_risk_scores.csv
    │   ├── component_analysis.csv
    │   └── complaint_trends.csv
    │
    ├── tableau/
    │   └── NHTSA_Dashboard.twbx    # Tableau workbook
    │
    └── README.md


---

## How to Reproduce

1. Clone repository
```bash
git clone https://github.com/anudeepreddy332/nhtsa-defect-analysis.git
cd nhtsa-defect-analysis
 ```
2. Download raw data from NHTSA
    - Link: https://www.nhtsa.gov/nhtsa-datasets-and-apis
    - Save FLAT_CMPL.txt and FLAT_RCL.txt to data/
   

3. Create database and load data
```
createdb nhtsa_defects
psql -d nhtsa_defects -f sql/schema.sql
```
4. Run analysis queries

```
psql -d nhtsa_defects -f sql/repeat_offenders.sql
psql -d nhtsa_defects -f sql/cost_analysis.sql
```
5. Export CSVs for Tableau
```
psql -d nhtsa_defects -c "\copy (SELECT * FROM vehicle_risk_scores) TO 'exports/vehicle_risk_scores.csv' CSV HEADER;"
```
6. Open tableau/NHTSA_Dashboard.twbx in Tableau Desktop

---

## Future Enhancements

- **NLP on Complaint Text:** Use SpaCy/NLTK to extract keywords from `CDESCR` (e.g., "fire," "stall," "brake failure")
- **Predictive Modeling:** Train ML classifier to predict recall likelihood based on complaint patterns
- **Real-Time API:** Automate data refresh using NHTSA's API (currently manual download)
- **Supplier Analysis:** Map components to suppliers to identify vendor quality issues

---

## Contact

**Anudeep**  
[LinkedIn](https://linkedin.com/in/anudeep-reddy-mutyala/) | [Portfolio](https://themachinist.org) | [Email](mailto:anudeepreddy332@gmail.com)