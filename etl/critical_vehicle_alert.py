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

def get_zero_recall_vehicles():
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    MAKETXT, MODELTXT, YEARTXT,
                    total_complaints
                FROM vehicle_risk_scores
                WHERE total_recalls = 0
                  AND risk_category IN ('HIGH','CRITICAL')
                ORDER BY total_complaints DESC
                LIMIT 5
            """)
            return cur.fetchall()


def get_ratio_critical_vehicles():
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    MAKETXT, MODELTXT, YEARTXT,
                    ROUND((total_complaints::FLOAT / total_recalls)::NUMERIC, 1)
                FROM vehicle_risk_scores
                WHERE total_recalls > 0
                  AND (total_complaints::FLOAT / total_recalls) >= 100
                ORDER BY 4 DESC
                LIMIT 10
            """)
            return cur.fetchall()

def hash_payload(rows):
    """
    rows: list of tuples in the form
    (make, model, year, value, category)
    """
    normalized = "|".join(
        f"{r[0]}-{r[1]}-{r[2]}-{r[3]}-{r[4]}"
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

def send_email(zero_recall, ratio_risk):
    sender = os.getenv("ALERT_EMAIL")
    password = os.getenv("ALERT_PASSWORD")
    recipients = os.getenv("ALERT_RECIPIENTS")

    if not all([sender, password, recipients]):
        print("[WARN] Email credentials not set")
        return

    recipients = [r.strip() for r in recipients.split(",")]

    body = "🚨 NHTSA VEHICLE SAFETY RISK ALERT\n\n"

    if zero_recall:
        body += "🔴 ZERO-RECALL HIGH-RISK VEHICLES (IMMEDIATE ATTENTION)\n"
        for m, mo, y, c in zero_recall:
            body += f"• {m} {mo} {y} — {c} complaints, ZERO recalls\n"
        body += "\n"

    if ratio_risk:
        body += "🟠 EXTREME COMPLAINT-TO-RECALL IMBALANCE\n"
        for m, mo, y, r in ratio_risk:
            body += f"• {m} {mo} {y} — {r} complaints per recall\n"
        body += "\n"

    body += (
        "🔗 Live Dashboard:\n"
        "https://nhtsa-silent-recall.streamlit.app\n\n"
        f"⏰ Generated: {dt.now().strftime('%Y-%m-%d %H:%M')}\n"
        "📊 Source: NHTSA Complaints & Recall APIs"
    )

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = "🚨 NHTSA Safety Alert: Vehicles Requiring Immediate Review"
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

    print("✅ Alert email sent")


def main():
    zero_recall = get_zero_recall_vehicles()
    ratio_risk = get_ratio_critical_vehicles()

    if not zero_recall and not ratio_risk:
        print("[INFO] No critical risks detected")
        return

    normalized_payload = []

    for m, mo, y, c in zero_recall:
        normalized_payload.append((m, mo, y, c, "ZERO_RECALL"))

    for m, mo, y, r in ratio_risk:
        normalized_payload.append((m, mo, y, r, "RATIO_RISK"))

    current_hash = hash_payload(normalized_payload)
    last_hash = get_last_hash()

    if current_hash == last_hash:
        print("[INFO] No change in alert state")
        return

    send_email(zero_recall, ratio_risk)
    update_hash(current_hash)
    print("[SUCCESS] Alert sent and state updated")

if __name__ == "__main__":
    main()