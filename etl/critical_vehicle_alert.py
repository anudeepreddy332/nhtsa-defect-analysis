from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DB_URL = os.getenv("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError("SUPABASE_DB_URL is NOT loaded")

import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import psycopg2
from datetime import datetime as dt

ALERT_NAME = "critical_vehicle_risk"
print("DB_URL =", DB_URL)
def get_critical_vehicles():
    """Get vehicles with risk_ratio > 50"""
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    MAKETXT, MODELTXT, YEARTXT,
                    total_complaints, total_recalls,
                    ROUND((total_complaints::FLOAT / NULLIF(total_recalls,0))::NUMERIC, 1) AS risk_ratio
                FROM vehicle_risk_scores
                WHERE (total_complaints::FLOAT / NULLIF(total_recalls,0)) > 50
                ORDER BY risk_ratio DESC
                """
            )
            return cur.fetchall()

def hash_payload(rows):
    """Create a stable hash of alert payload"""
    normalized = "|".join(
        f"{r[0]}-{r[1]}-{r[2]}-{r[5]}"
        for r in rows
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


def get_last_hash():
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT last_payload_hash
                FROM public.alert_state
                WHERE alert_name = %s
            """, (ALERT_NAME,))
            row = cur.fetchone()
            return row[0] if row else None


def update_hash(new_hash):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.alert_state (alert_name, last_payload_hash)
                VALUES (%s, %s)
                ON CONFLICT (alert_name)
                DO UPDATE SET
                    last_payload_hash = EXCLUDED.last_payload_hash,
                    updated_at = now()
            """, (ALERT_NAME, new_hash))
        conn.commit()

def send_email(vehicles):
    sender = os.getenv("ALERT_EMAIL")
    password = os.getenv("ALERT_PASSWORD")
    recipient = os.getenv("ALERT_RECIPIENT")

    if not all([sender, password, recipient]):
        print("[WARN] Email credentials not set")
        return

    body = (
        "🚨 NHTSA CRITICAL VEHICLE RISK ALERT\n\n"
        "This alert flags vehicles with an unusually HIGH number of consumer complaints\n"
        "relative to the number of official recalls.\n\n"
        "📌 How to read this:\n"
        "• A ratio of 100:1 means ~100 complaints for every 1 recall\n"
        "• Higher ratios may indicate delayed recalls or unresolved safety issues\n\n"
        "⚠️ Vehicles currently exceeding the risk threshold:\n\n"
    )

    for v in vehicles:
        make, model, year, complaints, recalls, ratio = v
        body += (
            f"• {make} {model} {year}\n"
            f"  ↳ ~{ratio} complaints per recall\n"
            f"  ↳ {complaints} complaints vs {recalls} recalls\n\n"
        )

    body += (
        "🔗 Live Dashboard:\n"
        "https://nhtsa-silent-recall.streamlit.app\n\n"
        f"⏰ Generated: {dt.now().strftime('%Y-%m-%d %H:%M')}\n"
        "📊 Source: NHTSA Complaints & Recall APIs"
    )

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "🚨 NHTSA Alert: Vehicles With Extreme Complaint-to-Recall Ratios"
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

    print("✅ Alert email sent")


def main():
    vehicles = get_critical_vehicles()
    if not vehicles:
        print("[INFO] No critical vehicles")
        return

    current_hash = hash_payload(vehicles)
    last_hash = get_last_hash()

    if current_hash == last_hash:
        print("[INFO] No change in critical vehicles. No alert sent.")
        return

    send_email(vehicles)
    update_hash(current_hash)
    print("[SUCCESS] Alert sent and state updated")

if __name__ == "__main__":
    main()