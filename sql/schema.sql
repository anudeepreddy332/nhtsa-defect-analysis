-- ==============================
-- NHTSA Defect Analysis Schema
-- ==============================

-- 0. Safety: drop analytical artifacts only
DROP VIEW IF EXISTS vehicle_risk_summary CASCADE;
DROP TABLE IF EXISTS vehicle_risk_scores CASCADE;
DROP TABLE IF EXISTS component_analysis CASCADE;
DROP TABLE IF EXISTS complaint_trends CASCADE;



-- 1. ETL state table (for automated pipelines)
CREATE TABLE IF NOT EXISTS etl_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT now()
);

INSERT INTO etl_state (key, value, updated_at)
VALUES
    ('last_recall_fetch', '2024-01-01', now()),
    ('last_complaint_check', '2024-Q4', now()),
    ('total_recalls_loaded', '0', now())
ON CONFLICT (key) DO NOTHING;

-- 2. Raw complaints table (if not exists)
CREATE TABLE IF NOT EXISTS flat_cmpl (
    CMPLID TEXT,
    ODINO TEXT,
    MFR_NAME TEXT,
    MAKETXT TEXT,
    MODELTXT TEXT,
    YEARTXT TEXT,
    CRASH TEXT,
    FAILDATE TEXT,
    FIRE TEXT,
    INJURED NUMERIC,
    DEATHS NUMERIC,
    COMPDESC TEXT,
    CITY TEXT,
    STATE TEXT,
    VIN TEXT,
    DATEA TEXT,
    LDATE TEXT,
    MILES NUMERIC,
    OCCURENCES NUMERIC,
    CDESCR TEXT,
    CMPL_TYPE TEXT,
    POLICE_RPT_YN TEXT,
    PURCH_DT TEXT,
    ORIG_OWNER_YN TEXT,
    ANTI_BRAKES_YN TEXT,
    CRUISE_CONT_YN TEXT,
    NUM_CYLS NUMERIC,
    DRIVE_TRAIN TEXT,
    FUEL_SYS TEXT,
    FUEL_TYPE TEXT,
    TRANS_TYPE TEXT,
    VEH_SPEED NUMERIC,
    DOT TEXT,
    TIRE_SIZE TEXT,
    LOC_OF_TIRE TEXT,
    TIRE_FAIL_TYPE TEXT,
    ORIG_EQUIP_YN TEXT,
    MANUF_DT TEXT,
    SEAT_TYPE TEXT,
    RESTRAINT_TYPE TEXT,
    DEALER_NAME TEXT,
    DEALER_TEL TEXT,
    DEALER_CITY TEXT,
    DEALER_STATE TEXT,
    DEALER_ZIP TEXT,
    PROD_TYPE TEXT,
    REPAIRED_YN TEXT,
    MEDICAL_ATTN TEXT,
    VEHICLES_TOWED_YN TEXT
);

-- 3. Raw recalls table (if not exists)
CREATE TABLE IF NOT EXISTS flat_rcl (
    RECORD_ID NUMERIC,
    CAMPNO TEXT PRIMARY KEY,
    MAKETXT TEXT,
    MODELTXT TEXT,
    YEARTXT TEXT,
    MFGCAMPNO TEXT,
    COMPNAME TEXT,
    MFGNAME TEXT,
    BGMAN TEXT,
    ENDMAN TEXT,
    RCLTYPECD TEXT,
    POTAFF NUMERIC,
    ODATE TEXT,
    INFLUENCED_BY TEXT,
    MFGTXT TEXT,
    RCDATE TEXT,
    DATEA TEXT,
    RPNO TEXT,
    FMVSS TEXT,
    DESC_DEFECT TEXT,
    CONEQUENCE_DEFECT TEXT,
    CORRECTIVE_ACTION TEXT,
    NOTES TEXT,
    RCL_CMPT_ID TEXT,
    MFR_COMP_NAME TEXT,
    MFR_COMP_DESC TEXT,
    MFR_COMP_PTNO TEXT,
    DO_NOT_DRIVE TEXT,
    PARK_OUTSIDE TEXT
);

-- 4. Vehicle risk summary view (no data yet if flat_* are empty)
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
WHERE c.YEARTXT BETWEEN '2010' AND '2025'
  AND c.MAKETXT NOT IN ('UNKNOWN', 'FIRESTONE', 'GOODYEAR', 'MICHELIN')
  AND c.MODELTXT NOT LIKE '%CHILD SEAT%'
GROUP BY c.MAKETXT, c.MODELTXT, c.YEARTXT;

-- 5. Vehicle risk scores (materialized snapshot)
CREATE TABLE vehicle_risk_scores AS
SELECT
    MAKETXT,
    MODELTXT,
    YEARTXT,
    total_complaints,
    total_recalls,
    (total_complaints::FLOAT / NULLIF(total_recalls, 0)) AS risk_ratio,
    CASE
        WHEN total_recalls = 0 AND total_complaints > 500 THEN 'CRITICAL'
        WHEN total_recalls = 0 AND total_complaints > 200 THEN 'HIGH'
        WHEN total_complaints > total_recalls * 10 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_category
FROM vehicle_risk_summary
WHERE total_complaints > 50
ORDER BY total_complaints DESC;

-- 6. Component Pareto snapshot
CREATE TABLE component_analysis AS
SELECT
    COMPDESC,
    COUNT(*) AS total_complaints,
    SUM(CASE WHEN CRASH = 'Y' THEN 1 ELSE 0 END) AS crash_related,
    SUM(CASE WHEN FIRE = 'Y' THEN 1 ELSE 0 END) AS fire_related,
    SUM(INJURED) AS total_injuries,
    SUM(DEATHS) AS total_deaths
FROM flat_cmpl
WHERE YEARTXT BETWEEN '2015' AND '2024'
  AND MAKETXT NOT IN ('UNKNOWN', 'FIRESTONE', 'GOODYEAR')
GROUP BY COMPDESC
ORDER BY total_complaints DESC
LIMIT 50;

-- 7. Complaint trends snapshot
CREATE TABLE complaint_trends AS
SELECT
    MAKETXT,
    MODELTXT,
    YEARTXT,
    EXTRACT(YEAR FROM TO_DATE(LDATE, 'YYYYMMDD')) AS complaint_year,
    EXTRACT(QUARTER FROM TO_DATE(LDATE, 'YYYYMMDD')) AS complaint_quarter,
    COUNT(*) AS complaint_count
FROM flat_cmpl
WHERE YEARTXT BETWEEN '2015' AND '2024'
  AND LDATE ~ '^\d{8}$'
  AND MAKETXT IN ('FORD', 'CHEVROLET', 'SUBARU', 'HONDA', 'TOYOTA')
GROUP BY MAKETXT, MODELTXT, YEARTXT, complaint_year, complaint_quarter
ORDER BY complaint_year DESC, complaint_quarter DESC;

-- Add seen campaign numbers tracking
INSERT INTO etl_state (key, value, updated_at)
VALUES ('seen_campaign_numbers', '[]', now())
ON CONFLICT (key) DO NOTHING;


-- Alert State Table
CREATE TABLE IF NOT EXISTS alert_state (
        alert_name TEXT PRIMARY KEY,
        last_payload_hash TEXT,
        updated_at TIMESTAMP DEFAULT now()
);

