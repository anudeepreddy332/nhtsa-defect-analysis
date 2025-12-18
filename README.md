# NHTSA Automotive Defect Analysis: Silent Recall Detection
![status](https://img.shields.io/badge/NHTSA-Defect_Analysis-blue)
![sql](https://img.shields.io/badge/Stack-SQL-green)
![tableau](https://img.shields.io/badge/Visualization-Tableau-orange)\
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://nhtsa-silent-recall.streamlit.app)
[![ETL Pipeline](https://github.com/anudeepreddy332/nhtsa-defect-analysis/actions/workflows/etl_pipeline.yml/badge.svg)](https://github.com/anudeepreddy332/nhtsa-defect-analysis/actions/workflows/etl_pipeline.yml)

## [**Live Interactive Dashboard**](https://nhtsa-silent-recall.streamlit.app) ⚡
**Author:** Anudeep  
**Tools:** PostgreSQL, Python, Tableau Public  
**Data Source:** [NHTSA Office of Defects Investigation](https://www.nhtsa.gov/nhtsa-datasets-and-apis)


## 📊 Overview

Automated ETL pipeline tracking vehicle safety complaints and recalls from NHTSA. Identifies "silent recalls" - vehicles with high complaint volumes but disproportionately low recall actions.

**Key Insight:** Jeep Wrangler 2024 has **93 complaints per recall** (837 complaints, 9 recalls) - potential safety concern.

---

## 🏗️ Architecture

graph LR
A[NHTSA Recalls API] -->|Weekly Fetch| B[Python ETL]\
B -->|Incremental Load| C[PostgreSQL (Supabase)]\
C -->|Live Queries| D[Streamlit Dashboard]\
E[GitHub Actions] -->|Cron: Mon 9AM IST| B\
D -->|Public URL| F[Users]

---

## 🎯 Project Highlights

- **Automated Recall Intelligence:** Weekly ETL pipeline fetches vehicle recalls from the NHTSA API and tracks **10,000+ consumer safety complaints**.
- **Dynamic Risk Monitoring:** Automatically targets the **top 20 vehicles by complaint volume** (2020–2024), tracking **202 recalls** across high-risk models.
- **Silent Recall Detection:** Uses **complaint-to-recall ratios** to surface vehicles with disproportionately high complaints but low official recalls.
- **Incremental, Reliable ETL:** Runs weekly, deduplicates records by campaign number, and ensures consistent historical tracking.
- **Interactive Risk Dashboard:** Live, query-driven analysis for exploring recall trends and vehicle safety risks.

**Use Cases:** Consumer safety advocacy · Automotive journalism · Insurance risk assessment


---

## 📈 Top Risk Vehicles (Current Data)

| Make | Model | Year | Complaints | Recalls | Risk Ratio |
|------|-------|------|------------|---------|------------|
| JEEP | WRANGLER | 2024 | 837 | 9 | **93.0** |
| NISSAN | ROGUE | 2023 | 136 | 5 | **27.2** |
| JEEP | WRANGLER 4XE | 2024 | 61 | 3 | **20.3** |
| JEEP | GRAND CHEROKEE | 2022 | 68 | 4 | 17.0 |
| HYUNDAI | PALISADE | 2024 | 65 | 4 | 16.3 |

---

## 🛠️ Tech Stack

- **ETL:** Python (psycopg2, requests, state management)
- **Database:** PostgreSQL (Supabase cloud, connection pooling)
- **Orchestration:** GitHub Actions (scheduled workflows)
- **Visualization:** Streamlit + Plotly (interactive charts)
- **Deployment:** Streamlit Cloud (free tier)

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
1. Fetch Top 20 Vehicles (by complaints)
   ↓
2. Query NHTSA Recalls API
   ↓
3. Filter New Recalls (dedupe by campaign number)
   ↓
4. Insert to PostgreSQL (idempotent)
   ↓
5. Refresh Analytical Tables
   ↓
6. Dashboard Auto-Updates
```

**Schedule:** Every Monday 9:00 AM IST

---

## 📊 Database Schema

### Core Tables
- **`flat_cmpl`** - Complaint data (10,000 rows, 2020-2024)
- **`flat_rcl`** - Recall data (202 rows, dynamic)
- **`etl_state`** - Pipeline state tracking

### Analytical Views
- **`vehicle_risk_summary`** - Joined complaints + recalls
- **`vehicle_risk_scores`** - Risk categorization (CRITICAL/HIGH/MEDIUM/LOW)
- **`component_analysis`** - Component failure Pareto (top 50)
- **`yearly_trends`** - Time series (2015-2024)
- **`top_recalled_vehicles`** - Vehicles with 2+ recalls

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

## 📅 Roadmap

- [x] Automated weekly ETL pipeline
- [x] Dynamic vehicle tracking (top 20)
- [x] Risk scoring algorithm
- [x] Streamlit dashboard deployment
- [ ] Email alerts for critical risk scores
- [ ] Expand to complaint data fetching
- [ ] Historical trend analysis (5+ years)

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