from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DB_URL = os.getenv("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError("SUPABASE_DB_URL is NOT loaded")


import json
import requests
import psycopg2
from time import sleep
from etl.state_manager import StateManager

COMPLAINT_API = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
TIMEOUT = 20
MAX_VEHICLES = 50          # safety cap
REQUEST_DELAY = 0.05       # polite but fast

# =========================
# API FETCH
# =========================
def fetch_complaints(make, model, year):
    """Fetch complaints from NHTSA API for one vehicle"""
    try:
        resp = requests.get(
            COMPLAINT_API,
            params={
                "make": make,
                "model": model,
                "modelYear": year
            },
            timeout=TIMEOUT
        )
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except Exception as e:
        print(f"[WARN] API failed for {make} {model} {year}: {e}")
    return []

# =========================
# MAIN LOADER
# =========================
def load_complaints():
    sm = StateManager()

    # Previously ingested ODI numbers (dedupe)
    raw = sm.get("seen_odi_numbers")
    seen_odis = set(json.loads(raw)) if raw else set()

    print(f"[INFO] Seen ODIs: {len(seen_odis)}")

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            # 🔑 Choose vehicles intelligently (NOT flat_cmpl)
            cur.execute("""
                SELECT MAKETXT, MODELTXT, YEARTXT
                FROM vehicle_risk_scores
                WHERE YEARTXT BETWEEN '2020' AND '2024'
                  AND total_complaints > 50
                ORDER BY total_complaints DESC
                LIMIT %s
            """, (MAX_VEHICLES,))
            vehicles = cur.fetchall()

        print(f"[INFO] Fetching complaints for {len(vehicles)} vehicles")

        rows_to_insert = []

        for idx, (make, model, year) in enumerate(vehicles, start=1):
            print(f"[{idx}/{len(vehicles)}] {make} {model} {year}")

            complaints = fetch_complaints(make, model, year)
            sleep(REQUEST_DELAY)

            for c in complaints:
                odi = str(c.get("odiNumber"))
                if not odi or odi in seen_odis:
                    continue

                rows_to_insert.append((
                    odi,
                    make,
                    model,
                    year,
                    'Y' if c.get("crash") else 'N',
                    'Y' if c.get("fire") else 'N',
                    c.get("numberOfInjuries", 0),
                    c.get("numberOfDeaths", 0),
                    c.get("components"),
                    c.get("summary"),
                    c.get("dateComplaintFiled"),
                ))

                seen_odis.add(odi)

        if not rows_to_insert:
            print("[INFO] No new complaints found")
            return

        print(f"[INFO] Inserting {len(rows_to_insert)} new complaints")

        # 🚀 BULK INSERT (FAST & SAFE)
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO flat_cmpl (
                    cmplid, maketxt, modeltxt, yeartxt,
                    crash, fire, injured, deaths,
                    compdesc, cdescr, ldate
                )
                SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                WHERE NOT EXISTS (
                    SELECT 1 FROM flat_cmpl WHERE cmplid = %s
                )
            """, [row + (row[0],) for row in rows_to_insert])

        conn.commit()

    sm.set("seen_odi_numbers", json.dumps(list(seen_odis)))
    sm.close()

    print("[SUCCESS] Complaint ingestion complete")

# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    load_complaints()