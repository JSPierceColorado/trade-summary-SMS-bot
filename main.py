import os
import json
import requests
import gspread
from datetime import datetime

SHEET_NAME = "Trading Log"
LOG_TAB = "log"

MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")  # e.g. sandbox1234.mailgun.org
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")          # e.g. 'Bot <bot@yourdomain.com>' or 'bot@sandbox1234.mailgun.org'
EMAIL_TO = os.getenv("EMAIL_TO")              # your email

def get_google_client():
    creds = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
    return gspread.service_account_from_dict(creds)

def get_today_trades(ws):
    rows = ws.get_all_values()
    if not rows or len(rows) < 2:
        return [], []
    header = rows[0]
    if "Timestamp" not in header:
        print(f"No 'Timestamp' in headers: {header}")
        return header, []
    ts_idx = header.index("Timestamp")
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_trades = [row for row in rows[1:] if len(row) > ts_idx and today_str in row[ts_idx]]
    return header, today_trades

def summarize_trades(header, trades):
    if not trades:
        return "No trades today. Bot ran successfully."
    side_idx = header.index("Side")
    notional_idx = header.index("Notional") if "Notional" in header else None
    price_idx = header.index("Price") if "Price" in header else None

    buys = [row for row in trades if row[side_idx].strip().lower() == "buy"]
    sells = [row for row in trades if row[side_idx].strip().lower() == "sell"]

    profit = 0.0
    if sells and price_idx is not None:
        profit += sum(float(row[price_idx]) if row[price_idx] else 0 for row in sells)
    if buys and notional_idx is not None:
        profit -= sum(float(row[notional_idx]) if row[notional_idx] else 0 for row in buys)

    msg_parts = []
    if buys:
        msg_parts.append(f"Bought {len(buys)} stocks")
    if sells:
        msg_parts.append(f"Sold {len(sells)} stocks")
    msg_parts.append(f"Generated ${profit:.2f} profit today.")

    return ". ".join(msg_parts)

def send_mailgun_email(subject, body):
    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    auth = ("api", MAILGUN_API_KEY)
    data = {
        "from": EMAIL_FROM,
        "to": [EMAIL_TO],
        "subject": subject,
        "text": body,
    }
    response = requests.post(url, auth=auth, data=data)
    if response.status_code == 200:
        print("✅ Email sent via Mailgun")
    else:
        print(f"❌ Mailgun error: {response.status_code}, {response.text}")

def main():
    gc = get_google_client()
    log_ws = gc.open(SHEET_NAME).worksheet(LOG_TAB)
    header, trades = get_today_trades(log_ws)
    summary = summarize_trades(header, trades)
    print("Email body:", summary)
    send_mailgun_email("Trading bot daily summary", summary)

if __name__ == "__main__":
    main()
