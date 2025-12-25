# NHTSA Automotive Defect Analysis: Silent Recall Detection
![status](https://img.shields.io/badge/NHTSA-Defect_Analysis-blue)
![sql](https://img.shields.io/badge/Stack-SQL-green)
![tableau](https://img.shields.io/badge/Visualization-Tableau-orange)\
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://nhtsa-silent-recall.streamlit.app)
[![ETL Pipeline](https://github.com/anudeepreddy332/nhtsa-defect-analysis/actions/workflows/etl_pipeline.yml/badge.svg)](https://github.com/anudeepreddy332/nhtsa-defect-analysis/actions/workflows/etl_pipeline.yml)
> **This is a live safety monitoring system, not a static analysis project.**

## [**Live Interactive Dashboard**](https://nhtsa-silent-recall.streamlit.app) ⚡
**Author:** Anudeep  
**Tools:** PostgreSQL, Python, Tableau Public  
**Data Source:** [NHTSA Office of Defects Investigation](https://www.nhtsa.gov/nhtsa-datasets-and-apis)


## 📊 Overview

Automated, stateful ETL pipeline that continuously ingests NHTSA complaints and recalls, detects silent safety risks, and sends real-time alerts.

**Key Insights:**  
* GMC Sierra 1500 (2021) has **445 consumer complaints with ZERO recalls**, indicating a high-priority silent safety risk.  
* Toyota Tundra (2024) follows with **245 complaints and zero recalls**.
---

## 🏗️ Architecture

graph LR
A[NHTSA Complaints API] -->|Incremental Fetch| B[Python ETL]

A2[NHTSA Complaints FTP] -->|Quarterly Full Sync| B

A3[NHTSA Recalls API] -->|Weekly Fetch| B

B -->|Idempotent Load| C[PostgreSQL (Supabase)]

C -->|Analytical Views| D[Streamlit Dashboard]

C -->|Risk Threshold Breach| G[Email Alerts]

E[GitHub Actions] -->|Cron + Manual Dispatch| B

D -->|Public URL| F[Users]

G -->|Critical Risk Notification| F

---

## 🎯 Project Highlights

- **Automated Recall Intelligence:** Weekly ETL pipeline fetches vehicle recalls from the NHTSA API and tracks **10,000+ consumer safety complaints**.
- **Dynamic Risk Monitoring:** Automatically targets the **top 20 vehicles by complaint volume** (2020–2024), tracking **202 recalls** across high-risk models.
- **Silent Recall Detection:** Uses **complaint-to-recall ratios** to surface vehicles with disproportionately high complaints but low official recalls.
- **Incremental, Reliable ETL:** Runs weekly, deduplicates records by campaign number, and ensures consistent historical tracking.
- **Interactive Risk Dashboard:** Live, query-driven analysis for exploring recall trends and vehicle safety risks.

**Use Cases:** Consumer safety advocacy · Automotive journalism · Insurance risk assessment


---
## 🔔 Automated Critical Risk Alerts

This system actively monitors extreme complaint-to-recall imbalances and sends email alerts when meaningful changes are detected.
* Alerts trigger only when the risk profile changes (hash-based change detection)
* Prevents alert fatigue — no duplicate emails for unchanged data
* Designed for consumer safety monitoring, not just visualization

**Alert Definition:** 
A vehicle is flagged as critical when consumer complaints vastly outpace official recalls, suggesting potential underreported or delayed safety action.

**Example Alert Interpretation**
```
HONDA ACCORD 2020 → 171.5 complaints per recall  
(343 complaints, 2 recalls)

Note: While recalls exist, the complaint-to-recall ratio remains extremely high, qualifying it as a **Medium-to-High Silent Recall Risk**.
```
This means:
* Hundreds of consumer safety complaints
* Very few official recall actions
* Possible “silent recall” risk

📬 Alerts are generated automatically after each ETL run.

---
## 🔴 Zero-Recall High-Risk Vehicles (Highest Priority)

| Make | Model | Year | Complaints | Recalls |
|-----|------|------|-----------|---------|
| GMC | SIERRA 1500 | 2021 | 445 | 0 |
| TOYOTA | TUNDRA | 2024 | 245 | 0 |

## 🟠 Top Silent Recall Candidates (Complaints per Recall)

| Rank | Make | Model | Year | Complaints | Recalls | Risk Ratio | Risk |
|-----:|------|-------|------|------------|---------|------------|------|
| 1 | HONDA | ACCORD | 2020 | 343 | 2 | 171.5 | MEDIUM |
| 2 | HYUNDAI | PALISADE | 2020 | 487 | 3 | 162.3 | MEDIUM |
| 3 | JEEP | WRANGLER | 2021 | 867 | 7 | 123.9 | MEDIUM |
| 4 | NISSAN | ROGUE | 2023 | 606 | 5 | 121.2 | MEDIUM |
| 5 | KIA | TELLURIDE | 2020 | 698 | 6 | 116.3 | MEDIUM |

---

## 🛠️ Tech Stack

- **ETL:** Python (psycopg2, requests, state management)
- **Database:** PostgreSQL (Supabase cloud, connection pooling)
- **Orchestration:** GitHub Actions (scheduled workflows)
- **Visualization:** Streamlit + Plotly (interactive charts)
- **Deployment:** Streamlit Cloud (free tier)

---

## ⚙️ Automation & Reliability Features
* Stateful ingestion using etl_state and complaint ODI tracking
* Idempotent inserts (safe re-runs, no duplicates)
* API + FTP ingestion paths (fallback support)
* Database-level analytics refresh
* GitHub Actions scheduling + manual dispatch
* Email alert deduplication using payload hashing

This ensures the system behaves like a production monitoring pipeline, not a batch script.

---

## 📁 Project Structure

```
nhtsa-defect-analysis/
├── .github/workflows/
│   └── etl_pipeline.yml       # Automated ETL workflow
├── etl/
│   ├── state_manager.py       # Track processed recalls
│   ├── fetch_recalls.py       # NHTSA API integration
│   ├── load_postgres.py       # Database operations
│   └── run_etl.py             # Main orchestrator
├── sql/
│   ├── schema.sql             # Database schema
│   ├── cost_analysis.sql      # Financial impact queries
│   └── repeat_offenders.sql   # Recurring issue analysis
├── exports/
│   └── *.csv                  # Static analysis snapshots
├── requirements.txt
└── README.md
```

---

## 🔄 ETL Pipeline Flow

```
1. Identify High-Risk Vehicles (complaint-based)
   ↓
2. Fetch New Complaints (NHTSA Complaints API)
   ↓
3. Deduplicate via ODI Tracking
   ↓
4. Fetch New Recalls (NHTSA Recalls API)
   ↓
5. Insert Data (Idempotent)
   ↓
6. Refresh Analytical Tables
   ↓
7. Evaluate Risk Thresholds
   ↓
8. Send Alerts (if state changed)
   ↓
9. Dashboard Auto-Updates
```

**Schedule:** Every Monday 9:00 AM IST

---
## 🧠 Why Complaint-to-Recall Ratio Matters

Raw complaint counts alone can be misleading. This project introduces a normalized risk signal:
```
Risk Ratio = Total Complaints ÷ Total Recalls
```
Why this matters:
* 	High complaints + high recalls = issues acknowledged
* 	High complaints + low recalls = potential regulatory lag
* 	Normalizes across vehicle popularity and sales volume

This ratio is the core signal behind:
* Risk rankings
* Alerts
* Dashboard prioritization

---
## 🧩 Top Component Failure Drivers

The majority of safety complaints are concentrated in a small number of critical vehicle systems:

| Rank | Component | Complaints | Crashes | Fires | Injuries |
|-----:|-----------|------------|---------|-------|----------|
| 1 | ENGINE | 2,519 | 22 | 48 | 18 |
| 2 | ELECTRICAL SYSTEM | 2,209 | 41 | 45 | 33 |
| 3 | POWER TRAIN | 1,926 | 36 | 4 | 20 |
| 4 | UNKNOWN / OTHER | 1,877 | 54 | 32 | 72 |
| 5 | SERVICE BRAKES | 814 | 70 | 6 | 34 |

This distribution validates a Pareto-style risk concentration, with drivetrain and electrical systems dominating safety complaints.

---

## 📈 Complaint Trends Over Time
### Recent Complaint Trends (2020–2024)

| Year | Complaints | Crashes | Fires | Injuries | Deaths |
|------|------------|---------|-------|----------|--------|
| 2020 | 6,819 | 167 | 53 | 197 | 6 |
| 2021 | 4,233 | 103 | 74 | 91 | 0 |
| 2022 | 2,254 | 106 | 38 | 58 | 2 |
| 2023 | 2,992 | 143 | 36 | 99 | 1 |
| 2024 | 3,397 | 207 | 41 | 124 | 14 |

**Observation:**  
Although total complaints dipped post-2020, **crash-related and fatal incidents rebounded sharply in 2024**, reinforcing the need for continuous monitoring rather than raw volume analysis alone.

---

## 📊 Database Schema

### Core Tables
- **`flat_cmpl`** - Complaint data (API + FTP, incremental, deduplicated by ODI number)
- **`flat_rcl`** - Recall data (202 rows, dynamic)
- **`etl_state`** - Pipeline state tracking
- **`alert_state`** – Tracks alert payload hashes to prevent duplicate notifications

### Analytical Views
- **`vehicle_risk_summary`** - Joined complaints + recalls
- **`vehicle_risk_scores`** - Risk categorization (CRITICAL/HIGH/MEDIUM/LOW)
- **`component_analysis`** - Component failure Pareto (top 50)
- **`yearly_trends`** - Time series (2020-2024)
- **`top_recalled_vehicles`** - Vehicles with 2+ recalls (surfaced in Silent Recalls dashboard for regulatory contrast)
---

## 🚀 Setup Instructions

### 1. Clone Repository
```
git clone https://github.com/anudeepreddy332/nhtsa-defect-analysis.git
cd nhtsa-defect-analysis
```

### 2. Set Up Supabase
- Create free Supabase project
- Run `sql/schema.sql` to initialize database
- Copy connection string

### 3. Configure GitHub Secrets
- Go to **Settings → Secrets → Actions**
- Add `SUPABASE_DB_URL` secret

### 4. Test Workflow
- Go to **Actions** tab
- Click **NHTSA ETL Pipeline**
- Click **Run workflow**

---


## Future Enhancements

- **NLP on Complaint Text:** Use SpaCy/NLTK to extract keywords from `CDESCR` (e.g., "fire," "stall," "brake failure")
- **Predictive Modeling:** Train ML classifier to predict recall likelihood based on complaint patterns
- **Supplier Analysis:** Map components to suppliers to identify vendor quality issues

---

## Contact

**Anudeep**  
[LinkedIn](https://linkedin.com/in/anudeep-reddy-mutyala/) | [Portfolio](https://themachinist.org) | [Email](mailto:anudeepreddy332@gmail.com)