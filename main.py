import os
import json
import gspread
from datetime import datetime
from twilio.rest import Client

SHEET_NAME = "Trading Log"
LOG_TAB = "log"

GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
TO_NUMBER = os.getenv("TO_NUMBER")

def get_google_client():
    creds = json.loads(GOOGLE_CREDS_JSON)
    return gspread.service_account_from_dict(creds)

def get_today_trades(ws):
    rows = ws.get_all_values()
    if not rows or len(rows) < 2:
        return []
    header = rows[0]
    data = rows[1:]
    ts_idx = header.index("Timestamp")
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_trades = [row for row in data if len(row) > ts_idx and today_str in row[ts_idx]]
    return header, today_trades

def summarize_trades(header, trades):
    if not trades:
        return "No trades today. Bot ran successfully."
    side_idx = header.index("Side")
    notional_idx = header.index("Notional") if "Notional" in header else None
    price_idx = header.index("Price") if "Price" in header else None

    buys = [row for row in trades if row[side_idx].strip().lower() == "buy"]
    sells = [row for row in trades if row[side_idx].strip().lower() == "sell"]

    # Profit is sum of (sell proceeds) minus (buy costs)
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

def send_sms(body):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=body,
        from_=TWILIO_FROM_NUMBER,
        to=TO_NUMBER
    )
    print("✅ SMS sent:", message.sid)

def main():
    gc = get_google_client()
    log_ws = gc.open(SHEET_NAME).worksheet(LOG_TAB)
    header, trades = get_today_trades(log_ws)
    summary = summarize_trades(header, trades)
    print("SMS body:", summary)
    send_sms(summary)

if __name__ == "__main__":
    main()
