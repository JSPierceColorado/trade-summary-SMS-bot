import os
import json
import requests
import gspread
from datetime import datetime, UTC

SHEET_NAME = "Trading Log"
LOG_TAB = "log"

MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")  # e.g. sandboxXXXX.mailgun.org or mg.yourdomain.com
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")          # e.g. bot@mg.yourdomain.com
EMAIL_TO = os.getenv("EMAIL_TO")              # your email

def get_google_client():
    creds = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
    return gspread.service_account_from_dict(creds)

def get_today_trades(ws):
    """Return (header, today_rows) for current UTC date."""
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

def summarize_trades(header, trades):
    """Return a summary string for subject line."""
    if not trades:
        return "No trades today — Bot ran successfully"

    # Count buys and sells, compute profit from sells
    side_idx = header.index("Side") if "Side" in header else None
    notional_idx = header.index("Notional") if "Notional" in header else None
    price_idx = header.index("Price") if "Price" in header else None

    buys = 0
    sells = 0
    profit = 0.0

    for row in trades:
        if side_idx is None or len(row) <= side_idx:
            continue
        side = (row[side_idx] or "").strip().lower()
        if side == "buy":
            buys += 1
        elif side == "sell":
            sells += 1
            if price_idx is not None and row[price_idx]:
                try:
                    profit += float(row[price_idx])
                except ValueError:
                    pass

    profit_str = f"${profit:.2f} profit" if sells > 0 else "No profit"
    return f"Bought {buys} stocks, {profit_str} — Bot ran successfully"

def send_mailgun_email(subject, body):
    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    auth = ("api", MAILGUN_API_KEY)
    data = {
        "from": EMAIL_FROM,   # Keep as raw email for minimal display name
        "to": [EMAIL_TO],
        "subject": subject,
        "text": body
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
    summary = summarize_trades(header, trades)

    print("Email subject:", summary)
    send_mailgun_email(summary, "")  # empty body

if __name__ == "__main__":
    main()
