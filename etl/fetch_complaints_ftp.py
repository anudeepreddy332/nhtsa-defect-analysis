from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DB_URL = os.getenv("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError("SUPABASE_DB_URL is NOT loaded")

import psycopg2
import pandas as pd
from ftplib import FTP

DATA_DIR = "data"
FILENAME = "flat_cmpl.txt"

def download_complaint_flatfile():
    ftp = FTP("ftp.nhtsa.dot.gov")
    ftp.login()
    ftp.cwd("/Complaints")

    os.makedirs(DATA_DIR, exist_ok=True)

    local_path = f"{DATA_DIR}/{FILENAME}"
    with open(local_path, "wb") as f:
        ftp.retrbinary(f"RETR {FILENAME}", f.write)

    ftp.quit()
    print(f"[SUCCESS] Downloaded {FILENAME}")

def load_complaints_to_db():
    df = pd.read_csv(
        f"{DATA_DIR}/{FILENAME}",
        sep="|",
        encoding="latin1",
        low_memory=False
    )

    df = df.dropna(subset=["CMPLID"])

    insert_sql = """
        INSERT INTO flat_cmpl (
            CMPLID, MAKETXT, MODELTXT, YEARTXT,
            CRASH, FIRE, INJURED, DEATHS,
            COMPDESC, LDATE
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (CMPLID) DO NOTHING
    """

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            for _,r in df.iterrows():
                cur.execute(insert_sql, (
                    r["CMPLID"],
                    r["MAKETXT"],
                    r["MODELTXT"],
                    r["YEARTXT"],
                    r["CRASH"],
                    r["FIRE"],
                    r["INJURED"] or 0,
                    r["DEATHS"] or 0,
                    r["COMPDESC"],
                    r["LDATE"]
                ))
        conn.commit()

    print("[SUCCESS] Complaints loaded with deduplication")

def main():
    download_complaint_flatfile()
    load_complaints_to_db()


if __name__ == "__main__":
    main()

