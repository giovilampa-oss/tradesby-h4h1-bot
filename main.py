import os
import time
import requests
import schedule
from flask import Flask
from threading import Thread

# --- FLASK WEBSERVER (Per mantenere attivo Render) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Tradesby H4/H1 (Twelve Data) - Attivo!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURAZIONE ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY")

ASSETS = [
    {"name": "BITCOIN (BTC/USD)", "symbol": "BTC/USD", "decimals": 2},
    {"name": "GOLD (XAU/USD)", "symbol": "XAU/USD", "decimals": 2},
    {"name": "EUR/USD", "symbol": "EUR/USD", "decimals": 5}
]

last_signals = {}

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Errore: Credenziali Telegram mancanti.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def get_candles(symbol, interval, outputsize=10):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize={outputsize}&apikey={TWELVE_DATA_KEY}"
    try:
        response = requests.get(url).json()
        if "values" in response:
            return response["values"]
        else:
            print(f"Errore API per {symbol}: {response}")
    except Exception as e:
        print(f"Errore connessione Twelve Data per {symbol}: {e}")
    return None

def check_strategy():
    print("Avvio analisi di mercato Real-Time con Twelve Data...")
    for asset in ASSETS:
        name = asset["name"]
        symbol = asset["symbol"]
        decimals = asset["decimals"]

        h4_data = get_candles(symbol, "4h", outputsize=5)
        h1_data = get_candles(symbol, "1h", outputsize=5)

        if not h4_data or not h1_data:
            continue

        prev_h4 = h4_data[1]
        h4_high = float(prev_h4["high"])
        h4_low = float(prev_h4["low"])

        prev_h1 = h1_data[1]
        last_h1_close = float(prev_h1["close"])
        last_h1_time = prev_h1["datetime"]

        # SEGNALE BUY
        if last_h1_close > h4_high:
            signal_key = f"{name}_BUY_{last_h1_time}"
            if last_signals.get(name) != signal_key:
                last_signals[name] = signal_key

                entry = round(last_h1_close, decimals)
                sl = round(h4_low, decimals)
                risk = entry - sl
                tp = round(entry + (risk * 2), decimals)

                msg = (
                    f"🚀 *{name} - SEGNALE BUY (REAL-TIME)*\n"
                    f"-----------------------------------------\n"
                    f"📌 *Setup:* Chiusura H1 sopra la No Trade Zone H4\n"
                    f"🧱 *No Trade Zone H4:* {round(h4_low, decimals)} - {round(h4_high, decimals)}\n"
                    f"🎯 *Entry:* {entry}\n"
                    f"🛑 *Stop Loss:* {sl} (Minimo H4)\n"
                    f"✅ *Take Profit:* {tp} (RR 1:2)\n"
                    f"-----------------------------------------"
                )
                send_telegram_message(msg)

        # SEGNALE SELL
        elif last_h1_close < h4_low:
            signal_key = f"{name}_SELL_{last_h1_time}"
            if last_signals.get(name) != signal_key:
                last_signals[name] = signal_key

                entry = round(last_h1_close, decimals)
                sl = round(h4_high, decimals)
                risk = sl - entry
                tp = round(entry - (risk * 2), decimals)

                msg = (
                    f"🔻 *{name} - SEGNALE SELL (REAL-TIME)*\n"
                    f"-----------------------------------------\n"
                    f"📌 *Setup:* Chiusura H1 sotto la No Trade Zone H4\n"
                    f"🧱 *No Trade Zone H4:* {round(h4_low, decimals)} - {round(h4_high, decimals)}\n"
                    f"🎯 *Entry:* {entry}\n"
                    f"🛑 *Stop Loss:* {sl} (Massimo H4)\n"
                    f"✅ *Take Profit:* {tp} (RR 1:2)\n"
                    f"-----------------------------------------"
                )
                send_telegram_message(msg)

schedule.every(15).minutes.do(check_strategy)

if __name__ == "__main__":
    # Avvia Flask in background
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    send_telegram_message("🤖 *Bot Tradesby Aggiornato a Twelve Data Real-Time!*")
    check_strategy()

    while True:
        schedule.run_pending()
        time.sleep(1)
