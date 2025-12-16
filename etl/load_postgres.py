import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
DB_URL = os.getenv("SUPABASE_DB_URL")

def insert_recalls(recalls):
    """Insert recalls with ON CONFLICT DO NOTHING (idempotent)"""
    if not recalls:
        print("[INFO] No recalls to insert")
        return 0

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    inserted = 0
    for recall in recalls:
        try:
            cursor.execute("""
                INSERT INTO flat_rcl (
                    CAMPNO, MAKETXT, MODELTXT, YEARTXT,
                    COMPNAME, DESC_DEFECT, RCDATE, POTAFF
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (CAMPNO) DO NOTHING
            """, (
                recall.get('NHTSACampaignNumber', 'UNKNOWN'),
                recall.get('Make', 'UNKNOWN'),
                recall.get('Model', 'UNKNOWN'),
                str(recall.get('ModelYear', '9999')),
                recall.get('Component', ''),
                recall.get('Summary', ''),
                recall.get('ReportReceivedDate', ''),
                recall.get('PotentialUnitsAffected', 0)
            ))
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"[WARN] Failed to insert recall: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"[SUCCESS] Inserted {inserted} new recalls")
    return inserted


def refresh_analytical_tables():
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # 1. Vehicle risk scores
    print("[INFO] Refreshing vehicle_risk_scores...")
    cursor.execute("DROP TABLE IF EXISTS vehicle_risk_scores;")
    cursor.execute("""
        CREATE TABLE vehicle_risk_scores AS
        SELECT 
            MAKETXT, MODELTXT, YEARTXT,
            total_complaints, total_recalls,
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
    """)

    # 2. Component Pareto
    print("[INFO] Refreshing component_analysis...")
    cursor.execute("DROP TABLE IF EXISTS component_analysis;")
    cursor.execute("""
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
    """)

    # 3. Time Series by Year (NEW!)
    print("[INFO] Refreshing yearly_trends...")
    cursor.execute("DROP TABLE IF EXISTS yearly_trends;")
    cursor.execute("""
        CREATE TABLE yearly_trends AS
        SELECT
            YEARTXT AS year,
            COUNT(*) AS total_complaints,
            SUM(CASE WHEN CRASH = 'Y' THEN 1 ELSE 0 END) AS crashes,
            SUM(CASE WHEN FIRE = 'Y' THEN 1 ELSE 0 END) AS fires,
            SUM(INJURED) AS injuries,
            SUM(DEATHS) AS deaths
        FROM flat_cmpl
        WHERE YEARTXT BETWEEN '2015' AND '2024'
        GROUP BY YEARTXT
        ORDER BY YEARTXT;
    """)

    # 4. Top Recalled Vehicles (NEW!)
    print("[INFO] Refreshing top_recalled_vehicles...")
    cursor.execute("DROP TABLE IF EXISTS top_recalled_vehicles;")
    cursor.execute("""
        CREATE TABLE top_recalled_vehicles AS
        SELECT
            MAKETXT,
            MODELTXT,
            YEARTXT,
            COUNT(*) AS recall_count,
            SUM(POTAFF) AS total_units_affected
        FROM flat_rcl
        GROUP BY MAKETXT, MODELTXT, YEARTXT
        HAVING COUNT(*) > 1
        ORDER BY recall_count DESC
        LIMIT 100;
    """)

    conn.commit()

    # Get counts
    cursor.execute("SELECT COUNT(*) FROM vehicle_risk_scores;")
    risk_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM component_analysis;")
    comp_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM yearly_trends;")
    trend_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM top_recalled_vehicles;")
    recall_count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    print(
        f"[SUCCESS] Refreshed: {risk_count} risk scores, {comp_count} components, {trend_count} years, {recall_count} recalled vehicles")


if __name__ == "__main__":
    # Test with an empty list
    insert_recalls([])
    refresh_analytical_tables()
