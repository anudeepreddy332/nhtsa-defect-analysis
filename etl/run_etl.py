from etl.fetch_recalls import fetch_new_recalls
from etl.load_postgres import insert_recalls, refresh_analytical_tables
from datetime import datetime
from etl.fetch_complaints_api import load_complaints
from etl.critical_vehicle_alert import main as run_alerts

def main():
    print("=" * 60)
    print(f"NHTSA ETL Pipeline started at {datetime.now()}")
    print("=" * 60)

    # Step 1: Fetch incremental complaints (API)
    print("\n[STEP 1] Fetching new complaints via API...")
    load_complaints()

    # Step 2: Fetch recalls
    print("\n[STEP 2] Fetching recalls from NHTSA API...")
    recalls = fetch_new_recalls()

    # Step 3: Load recalls
    print(f"\n[STEP 3] Loading {len(recalls)} recalls into database...")
    insert_recalls(recalls)

    # Step 4: Refresh analytics
    print("\n[STEP 4] Refreshing analytical tables...")
    refresh_analytical_tables()

    # Step 5: Alert on critical vehicles
    print("\n[STEP 5] Running critical vehicle alerts...")
    run_alerts()

    print("\n✅ ETL COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
