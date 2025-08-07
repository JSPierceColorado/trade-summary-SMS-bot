import os
import json
import gspread
import requests
from datetime import datetime

# Google Sheet settings
SHEET_NAME = "Trading Log"
LOG_TAB = "log"

# Mailgun settings
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")  # e.g. bot@sandboxXXXX.mailgun.org
EMAIL_TO = os.getenv("EMAIL_TO")      # Your email address

def get_google_client():
    creds = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
    return gspread.service_account_from_dict(creds)

def get_today_trades(ws):
    """Fetch trades from Google Sheet log tab for today's date."""
    rows = ws.get_all_values()
    if not rows:
        return [], []
    header = rows[0]
    if "Timestamp" not in header:
        print("⚠️ No 'Timestamp' column found in log sheet.")
        return header, []
    ts_idx = header.index("Timestamp")
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    trades = [row for row in rows[1:] if len(row) > ts_idx and row[ts_idx].startswith(today_str)]
    return header, trades

def build_summary(trades):
    """Create a concise subject line summary."""
    if not trades:
        return "No trades today — Bot ran successfully"
    buys = sum(1 for t in trades if len(t) > 2 and t[2].lower() == "buy")
    profit = 0.0
    for t in trades:
        if len(t) > 2 and t[2].lower() == "sell":
            try:
                proceeds = float(t[3]) if t[3] else 0
                profit += proceeds
            except ValueError:
                continue
    if profit > 0:
        return f"Bought {buys} stocks, ${profit:.2f} profit — Bot ran successfully"
    elif profit < 0:
        return f"Bought {buys} stocks, -${abs(profit):.2f} loss — Bot ran successfully"
    else:
        return f"Bought {buys} stocks, $0.00 profit — Bot ran successfully"

def send_mailgun_email(subject, body="Good luck!"):
    """Send email via Mailgun."""
    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    auth = ("api", MAILGUN_API_KEY)
    data = {
        "from": EMAIL_FROM,  # keep minimal to avoid long sender names in notification
        "to": [EMAIL_TO],
        "subject": subject,
        "text": body or "Good luck!"
    }
    resp = requests.post(url, auth=auth, data=data)
    if resp.status_code == 200:
        print("✅ Email sent via Mailgun")
    else:
        print(f"❌ Mailgun error: {resp.status_code}, {resp.text}")

def main():
    print("📩 Starting daily trade summary bot...")
    gc = get_google_client()
    log_ws = gc.open(SHEET_NAME).worksheet(LOG_TAB)
    header, trades = get_today_trades(log_ws)
    summary = build_summary(trades)
    print(f"Email subject: {summary}")
    send_mailgun_email(summary)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("❌ Fatal error:", e)
        traceback.print_exc()
