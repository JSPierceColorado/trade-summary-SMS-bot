import os
import json
import requests
import gspread
from datetime import datetime, UTC

SHEET_NAME = "Trading Log"
LOG_TAB = "log"

MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")  # e.g. sandboxXXXX.mailgun.org or mg.yourdomain.com
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")          # e.g. bot@sandboxXXXX.mailgun.org
EMAIL_TO = os.getenv("EMAIL_TO")              # your email

def get_google_client():
    creds = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
    return gspread.service_account_from_dict(creds)

def get_today_trades(ws):
    """Return (header, today_rows). 'Today' is matched by UTC date substring in Timestamp."""
    rows = ws.get_all_values()
    if not rows or len(rows) < 2:
        return [], []

    header = rows[0]
    # Be strict about column naming but fail gracefully
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
    """Return (num_buys, num_sells). We treat any sell as 'profit made' per your bot logic."""
    if not trades:
        return 0, 0
    if "Side" not in header:
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

def build_subject(buys, sells, had_trades):
    if not had_trades:
        return "Bot: No trades today"
    profit_flag = "Profit made" if sells > 0 else "No profit"
    return f"Bot: Bought {buys} • {profit_flag}"

def build_body(header, trades, buys, sells):
    if not trades:
        return "No trades today. Bot ran successfully."
    parts = []
    if buys:
        parts.append(f"Bought {buys} stocks")
    if sells:
        parts.append(f"Sold {sells} stocks")
    # Keep it short and text-like
    return ". ".join(parts) + "."

def send_mailgun_email(subject, body):
    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    auth = ("api", MAILGUN_API_KEY)
    data = {
        "from": EMAIL_FROM,
        "to": [EMAIL_TO],
        "subject": subject,
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
    subject = build_subject(buys, sells, had_trades=bool(trades))
    body = build_body(header, trades, buys, sells)

    print("Email subject:", subject)
    print("Email body:", body)
    send_mailgun_email(subject, body)

if __name__ == "__main__":
    main()
