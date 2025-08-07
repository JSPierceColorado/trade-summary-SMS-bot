import os
import json
import requests
import gspread
from datetime import datetime, UTC

# Google Sheet
SHEET_NAME = "Trading Log"
LOG_TAB = "log"

# Mailgun
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")  # e.g., mg.yourdomain.com or sandboxXXXX.mailgun.org
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")          # e.g., bot@mg.yourdomain.com  (no display name)
EMAIL_TO = os.getenv("EMAIL_TO")              # recipient email

def get_google_client():
    creds = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
    return gspread.service_account_from_dict(creds)

def get_today_trades(ws):
    """Return (header, today_rows) where 'today' is UTC calendar day matched in Timestamp."""
    rows = ws.get_all_values()
    if not rows or len(rows) < 2:
        return [], []
    header = rows[0]
    if "Timestamp" not in header:
        print(f"⚠️ No 'Timestamp' in headers: {header}")
        return header, []
    ts_idx = header.index("Timestamp")
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    today = []
    for row in rows[1:]:
        if len(row) > ts_idx and row[ts_idx]:
            if today_str in row[ts_idx]:
                today.append(row)
    return header, today

def summarize_for_subject(header, trades):
    """
    Build subject per spec:
    - Include "Bought X stocks" if any buys happened.
    - Include "$Y.YY profit" if sells happened and total proceeds > 0.
    - If no buys/sells, subject = "Bot ran successfully".
    - Never display losses.
    """
    if not trades:
        return "Bot ran successfully"

    side_idx = header.index("Side") if "Side" in header else None
    price_idx = header.index("Price") if "Price" in header else None

    buys = 0
    sell_proceeds = 0.0

    for row in trades:
        if side_idx is None or side_idx >= len(row):
            continue
        side = (row[side_idx] or "").strip().lower()
        if side == "buy":
            buys += 1
        elif side == "sell":
            if price_idx is not None and price_idx < len(row) and row[price_idx]:
                try:
                    sell_proceeds += float(row[price_idx])
                except ValueError:
                    pass

    parts = []
    if buys > 0:
        parts.append(f"Bought {buys} stocks")
    if sell_proceeds > 0:
        parts.append(f"${sell_proceeds:.2f} profit")

    if not parts:
        return "Bot ran successfully"
    return ", ".join(parts)

def send_mailgun_email(subject, body="Good luck!"):
    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    auth = ("api", MAILGUN_API_KEY)
    data = {
        "from": EMAIL_FROM,   # keep as plain email (no display name) to minimize sender text
        "to": [EMAIL_TO],
        "subject": subject,
        "text": body or "Good luck!",
    }
    resp = requests.post(url, auth=auth, data=data)
    if resp.status_code == 200:
        print("✅ Email sent via Mailgun")
    else:
        print(f"❌ Mailgun error: {resp.status_code}, {resp.text}")

def main():
    print("📩 Building daily notification subject...")
    gc = get_google_client()
    log_ws = gc.open(SHEET_NAME).worksheet(LOG_TAB)

    header, trades = get_today_trades(log_ws)
    subject = summarize_for_subject(header, trades)
    print("Email subject:", subject)

    send_mailgun_email(subject, "Good luck!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("❌ Fatal error:", e)
        traceback.print_exc()
