from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DB_URL = os.getenv("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError("SUPABASE_DB_URL is NOT loaded")

import psycopg2

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
        WHERE YEARTXT BETWEEN '2020' AND '2024'
          AND total_complaints > 50
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
        WHERE YEARTXT BETWEEN '2020' AND '2024'
          AND MAKETXT NOT IN ('UNKNOWN', 'FIRESTONE', 'GOODYEAR')
        GROUP BY COMPDESC
        ORDER BY total_complaints DESC
        LIMIT 50;
    """)

    # 3. Time Series by Year
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
        WHERE YEARTXT BETWEEN '2020' AND '2024'
        GROUP BY YEARTXT
        ORDER BY YEARTXT;
    """)

    # 4. Top Recalled Vehicles
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
        WHERE YEARTXT BETWEEN '2020' AND '2024'
        GROUP BY MAKETXT, MODELTXT, YEARTXT
        HAVING COUNT(*) > 1
        ORDER BY recall_count DESC
        LIMIT 100;
    """)

    # 5. Repeat Offender Vehicles (persistent top-complaint models)
    print("[INFO] Refreshing repeat_offenders...")
    cursor.execute("DROP TABLE IF EXISTS repeat_offenders;")
    cursor.execute("""
        CREATE TABLE repeat_offenders AS
        WITH yearly_aggregates AS (
            SELECT
                MAKETXT,
                MODELTXT,
                YEARTXT,
                COUNT(*) AS complaints
            FROM flat_cmpl
            WHERE YEARTXT BETWEEN '2020' AND '2024'
            GROUP BY MAKETXT, MODELTXT, YEARTXT
        ),
        yearly_rankings AS (
            SELECT
                MAKETXT,
                MODELTXT,
                YEARTXT,
                complaints,
                ROW_NUMBER() OVER (
                    PARTITION BY YEARTXT
                    ORDER BY complaints DESC
                ) AS rank_in_year
            FROM yearly_aggregates
        )
        SELECT
            MAKETXT,
            MODELTXT,
            COUNT(DISTINCT YEARTXT) AS years_in_top10,
            SUM(complaints) AS total_complaints,
            STRING_AGG(YEARTXT, ',' ORDER BY YEARTXT) AS problem_years
        FROM yearly_rankings
        WHERE rank_in_year <= 10
        GROUP BY MAKETXT, MODELTXT
        HAVING COUNT(DISTINCT YEARTXT) >= 3
        ORDER BY years_in_top10 DESC, total_complaints DESC;
    """)

    # 6. Component Cost Impact (economic + injury burden)
    print("[INFO] Refreshing component_cost_impact")
    cursor.execute("DROP TABLE IF EXISTS component_cost_impact;")
    cursor.execute("""
        CREATE TABLE component_cost_impact AS
        WITH component_costs AS (
            SELECT
                COMPDESC,
                COUNT(*) AS total_complaints,
                SUM(CASE WHEN CRASH = 'Y' THEN 1 ELSE 0 END) AS crash_count,
                SUM(INJURED) AS total_injuries,
                (
                    COUNT(*) * 5000
                    + SUM(CASE WHEN CRASH = 'Y' THEN 1 ELSE 0 END) * 50000
                    + SUM(INJURED) * 100000
                )::BIGINT AS estimated_cost
            FROM flat_cmpl
            WHERE YEARTXT BETWEEN '2020' AND '2024'
                AND MAKETXT NOT IN ('UNKNOWN', 'FIRESTONE', 'GOODYEAR')
            GROUP BY COMPDESC
        )
        SELECT
            COMPDESC,
            total_complaints,
            crash_count,
            total_injuries,
            estimated_cost,
            (estimated_cost * 0.10)::BIGINT AS savings_if_reduced_10pct
        FROM component_costs
        ORDER BY estimated_cost DESC
        LIMIT 50;
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
    cursor.execute("SELECT COUNT(*) FROM repeat_offenders;")
    repeat_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM component_cost_impact;")
    cost_count = cursor.fetchone()[0]

    print(
        f"[SUCCESS] Refreshed: "
        f"{risk_count} risk scores, "
        f"{comp_count} components, "
        f"{trend_count} years, "
        f"{recall_count} recalled vehicles, "
        f"{repeat_count} repeat offenders, "
        f"{cost_count} cost-impact components"
    )

    cursor.close()
    conn.close()


if __name__ == "__main__":
    # Test with an empty list
    insert_recalls([])
    refresh_analytical_tables()
