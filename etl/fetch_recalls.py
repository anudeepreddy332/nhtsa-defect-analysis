from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DB_URL = os.getenv("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError("SUPABASE_DB_URL is NOT loaded")

import requests
import psycopg2
from datetime import datetime as dt
from etl.state_manager import StateManager
import json
from time import sleep

RECALL_API = "https://api.nhtsa.gov/recalls/recallsByVehicle"
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3

def safe_get(url, params):
    """HTTP GET with retries"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            else:
                print(f"[WARN] Status {r.status_code}, retry {attempt}")
        except Exception as e:
            print(f"[WARN] Request failed ({attempt}): {e}")
        sleep(2)
    return None


def get_top_complaint_vehicles(limit=20):
    """Get vehicles with highest complaints from database"""
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT
                    MAKETXT AS make,
                    MODELTXT AS model,
                    YEARTXT AS year,
                    COUNT(*) AS complaint_count
                FROM flat_cmpl
                WHERE YEARTXT BETWEEN '2015' AND '2024'
                  AND MAKETXT NOT IN ('UNKNOWN', 'FIRESTONE', 'GOODYEAR')
                  AND MODELTXT != 'UNKNOWN'
                GROUP BY MAKETXT, MODELTXT, YEARTXT
                HAVING COUNT(*) > 50
                ORDER BY complaint_count DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()

    return [
        {"make": row[0], "model": row[1], "year": row[2], "complaint_count": row[3]}
        for row in rows
    ]


def fetch_recalls_for_vehicle(vehicle):
    data = safe_get(RECALL_API, {
        "make": vehicle["make"],
        "model": vehicle["model"],
        "modelYear": vehicle["year"]
    })
    return data.get("results", []) if data else []


def fetch_new_recalls():
    sm = StateManager()
    seen = set(json.loads(sm.get("seen_campaign_numbers") or "[]"))

    vehicles = get_top_complaint_vehicles()
    new_recalls = []

    for v in vehicles:
        recalls = fetch_recalls_for_vehicle(v)
        for r in recalls:
            campaign = r.get("NHTSACampaignNumber")
            if campaign and campaign not in seen:
                new_recalls.append(r)
                seen.add(campaign)
                print(f"[NEW] {campaign} ({v['make']} {v['model']} {v['year']})")

    if new_recalls:
        sm.set("seen_campaign_numbers", json.dumps(list(seen)))
        sm.set("last_recall_fetch", dt.utcnow().isoformat())
        sm.set("total_recalls_loaded",
               int(sm.get("total_recalls_loaded") or 0) + len(new_recalls))

    sm.close()
    return new_recalls


if __name__ == "__main__":
    recalls = fetch_new_recalls()

    # Save to file for inspection
    if recalls:
        with open('recalls_cache.json', 'w') as f:
            json.dump(recalls, f, indent=2)
        print(f"\n[SAVED] Wrote {len(recalls)} recalls to recalls_cache.json")
        print(f"Sample: {recalls[0].get('NHTSACampaignNumber')} - {recalls[0].get('Summary', '')[:80]}...")
