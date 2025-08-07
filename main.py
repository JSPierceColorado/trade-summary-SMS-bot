import os
import json
import requests
import gspread
from datetime import datetime, UTC

SHEET_NAME = "Trading Log"
LOG_TAB = "log"

MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")  # e.g. sandboxXXXX.mailgun.org or mg.yourdomain.com
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")          # e.g. bot@mg.yourdomain.com  (no display name)
EMAIL_TO = os.getenv("EMAIL_TO")              # recipient email

def get_google_client():
    creds = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
    return gspread.service_account_from_dict(creds)

def get_today_trades(ws):
    """Return (header, today_rows). 'Today' is matched by UTC date substring in Timestamp."""
    rows = ws.get_all_values()
    if not rows or len(rows) < 2:
        return [], []

    header = rows[0]
    if "Timestamp" not in header:
        print(f"⚠️ No 'Timestamp' in headers: {header}")
        return header, []

    ts_idx = header.index("Timestamp")
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")

    today_trades = [
        row for row in rows[1:]
        if len(row) > ts_idx and row[ts_idx] and today_str in row[ts_idx]
    ]
    return header, today_trades

def summarize_counts(header, trades):
    """Return (num_buys, num_sells)."""
    if not trades or "Side" not in header:
        return 0, 0
    side_idx = header.index("Side")
    buys = 0
    sells = 0
    for row in trades:
        if len(row) <= side_idx:
            continue
        side = (row[side_idx] or "").strip().lower()
        if side == "buy":
            buys += 1
        elif side == "sell":
            sells += 1
    return buys, sells

def build_body(trades, buys, sells):
    if not trades:
        return "No trades today. Bot ran successfully."
    parts = []
    if buys:
        parts.append(f"Bought {buys} stocks")
    if sells:
        parts.append(f"Sold {sells} stocks")
    return ". ".join(parts) + "."

def send_mailgun_email(subject, body):
    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    auth = ("api", MAILGUN_API_KEY)
    data = {
        "from": EMAIL_FROM,     # make sure this is just an email address, no display name
        "to": [EMAIL_TO],
        "subject": subject,     # empty string -> "(no subject)" in most clients
        "text": body,
    }
    resp = requests.post(url, auth=auth, data=data)
    if resp.status_code == 200:
        print("✅ Email sent via Mailgun")
    else:
        print(f"❌ Mailgun error: {resp.status_code}, {resp.text}")

def main():
    gc = get_google_client()
    log_ws = gc.open(SHEET_NAME).worksheet(LOG_TAB)

    header, trades = get_today_trades(log_ws)
    buys, sells = summarize_counts(header, trades)

    subject = ""  # intentionally blank
    body = build_body(trades, buys, sells)

    print("Email subject: (empty)")
    print("Email body:", body)
    send_mailgun_email(subject, body)

if __name__ == "__main__":
    main()
