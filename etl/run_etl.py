from etl.fetch_recalls import fetch_new_recalls
from etl.load_postgres import insert_recalls, refresh_analytical_tables
from datetime import datetime


def main():
    print(f"\n{'=' * 60}")
    print(f"NHTSA ETL Pipeline - Started at {datetime.now()}")
    print(f"{'=' * 60}\n")

    # Step 1: Fetch new recalls from NHTSA API
    print("[STEP 1] Fetching recalls from NHTSA API...")
    recalls = fetch_new_recalls()

    # Step 2: Load recalls to Postgres
    print(f"\n[STEP 2] Loading {len(recalls)} recalls to database...")
    inserted = insert_recalls(recalls)

    # Step 3: Refresh analytical tables
    print(f"\n[STEP 3] Refreshing analytical tables...")
    refresh_analytical_tables()

    print(f"\n{'=' * 60}")
    print(f"✅ ETL Complete - {inserted} new recalls loaded")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
