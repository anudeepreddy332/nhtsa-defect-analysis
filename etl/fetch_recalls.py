import requests
import psycopg2
from datetime import datetime as dt
from etl.state_manager import StateManager
import json
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv('SUPABASE_DB_URL')

RECALL_API = "https://api.nhtsa.gov/recalls/recallsByVehicle"


def get_top_complaint_vehicles(limit=20):
    """Get vehicles with highest complaints from database"""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

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

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    vehicles = [
        {"make": row[0], "model": row[1], "year": row[2], "complaint_count": row[3]}
        for row in results
    ]

    print(f"[INFO] Tracking top {len(vehicles)} vehicles by complaint volume")
    for i, v in enumerate(vehicles[:5], 1):
        print(f"  {i}. {v['make']} {v['model']} {v['year']} ({v['complaint_count']} complaints)")
    if len(vehicles) > 5:
        print(f"  ... and {len(vehicles) - 5} more")

    return vehicles


def fetch_recalls_for_vehicle(make, model, year):
    """Fetch all recalls for a specific vehicle"""
    params = {
        "make": make,
        "model": model,
        "modelYear": year
    }
    try:
        response = requests.get(RECALL_API, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])
        else:
            print(f"[WARN] API returned {response.status_code} for {make} {model} {year}")
            return []
    except Exception as e:
        print(f"[ERROR] Failed to fetch {make} {model} {year}: {e}")
        return []


def fetch_new_recalls():
    """Fetch recalls for tracked vehicles, deduplicate by campaign number"""
    sm = StateManager()

    # Get seen campaign numbers from state (stored as JSON string)
    seen_raw = sm.get('seen_campaign_numbers')
    seen = set(json.loads(seen_raw)) if seen_raw and seen_raw != '[]' else set()

    # DYNAMIC: Get top 20 vehicles from complaint data
    vehicles = get_top_complaint_vehicles(limit=20)

    new_recalls = []
    print(f"\n[INFO] Checking {len(vehicles)} vehicles for new recalls...")
    print(f"[INFO] Already seen {len(seen)} campaign numbers\n")

    for v in vehicles:
        recalls = fetch_recalls_for_vehicle(v['make'], v['model'], v['year'])

        for recall in recalls:
            campaign = recall.get('NHTSACampaignNumber')
            if not campaign:
                continue

            if campaign not in seen:
                new_recalls.append(recall)
                seen.add(campaign)
                print(f"[NEW] {campaign}: {v['make']} {v['model']} {v['year']}")

    # Update state
    if new_recalls:
        sm.set('seen_campaign_numbers', json.dumps(list(seen)))
        sm.set('last_recall_fetch', dt.now().strftime('%Y-%m-%d'))

        total = int(sm.get('total_recalls_loaded') or 0)
        sm.set('total_recalls_loaded', total + len(new_recalls))

    sm.close()

    print(f"\n[INFO] Found {len(new_recalls)} new recalls")
    return new_recalls


if __name__ == "__main__":
    recalls = fetch_new_recalls()

    # Save to file for inspection
    if recalls:
        with open('recalls_cache.json', 'w') as f:
            json.dump(recalls, f, indent=2)
        print(f"\n[SAVED] Wrote {len(recalls)} recalls to recalls_cache.json")
        print(f"Sample: {recalls[0].get('NHTSACampaignNumber')} - {recalls[0].get('Summary', '')[:80]}...")
