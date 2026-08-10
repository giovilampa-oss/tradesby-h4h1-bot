import os
import time
import requests
import pandas as pd
import yfinance as yf
from flask import Flask
from threading import Thread

# --- FLASK WEBSERVER (Per mantenere attivo Render) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Tradesby H4/H1 - WebService Attivo!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURAZIONE TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "INSERISCI_TUO_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "INSERISCI_TUO_CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

# --- STRUMENTI DA TRACCIARE ---
ASSETS = {
    "GOLD (XAU/USD)": "GC=F",
    "BITCOIN (BTC/USD)": "BTC-USD",
    "ETHEREUM (ETH/USD)": "ETH-USD",
    "NASDAQ 100": "NQ=F",
    "S&P 500": "ES=F",
    "EUR/USD": "EURUSD=X"
}

# Memoria per evitare notifiche doppie
last_signals = {}

# --- STRATEGIA TRADESBY (H4 / H1) ---
def check_tradesby_strategy():
    for name, symbol in ASSETS.items():
        try:
            ticker = yf.Ticker(symbol)
            
            df_h1 = ticker.history(period="10d", interval="1h")
            if df_h1.empty or len(df_h1) < 20:
                continue

            # Creiamo le candele a 4 Ore (H4)
            df_4h = df_h1.resample('4h').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last'
            }).dropna()

            # 1. Definizione della No Trade Zone H4 (Range H4 precedente)
            h4_high = df_4h['High'].iloc[-2]
            h4_low = df_4h['Low'].iloc[-2]

            # 2. Ultima Candela H1 Chiusa
            last_h1_time = str(df_h1.index[-1])
            last_h1_close = df_h1['Close'].iloc[-1]

            # Formattazione decimali (4 per Forex, 2 per altri)
            decimals = 4 if "EURUSD" in symbol else 2

            # --- SEGNALE BUY (Chiusura H1 SOPRA il Massimo H4) ---
            if last_h1_close > h4_high:
                signal_key = f"{name}_BUY_{last_h1_time}"
                if last_signals.get(name) != signal_key:
                    last_signals[name] = signal_key

                    entry = round(last_h1_close, decimals)
                    # SL posto SOTTO la No Trade Zone H4 (con piccolo buffer dello 0.1%)
                    sl = round(h4_low * 0.999, decimals)
                    risk = entry - sl
                    tp = round(entry + (risk * 2), decimals)  # Take Profit RR 1:2

                    msg = (
                        f"🚀 *{name} - SEGNALE BUY (STRATEGIA H4/H1)*\n"
                        f"-----------------------------------------\n"
                        f"📌 *Setup:* Chiusura H1 sopra la No Trade Zone H4\n"
                        f"🧱 *No Trade Zone H4:* {round(h4_low, decimals)} - {round(h4_high, decimals)}\n"
                        f"🎯 *Entry:* {entry}\n"
                        f"🛑 *Stop Loss:* {sl} (Sotto Minimo H4)\n"
                        f"✅ *Take Profit:* {tp} (RR 1:2)\n"
                        f"-----------------------------------------"
                    )
                    send_telegram_message(msg)

            # --- SEGNALE SELL (Chiusura H1 SOTTO il Minimo H4) ---
            elif last_h1_close < h4_low:
                signal_key = f"{name}_SELL_{last_h1_time}"
                if last_signals.get(name) != signal_key:
                    last_signals[name] = signal_key

                    entry = round(last_h1_close, decimals)
                    # SL posto SOPRA la No Trade Zone H4 (con piccolo buffer dello 0.1%)
                    sl = round(h4_high * 1.001, decimals)
                    risk = sl - entry
                    tp = round(entry - (risk * 2), decimals)  # Take Profit RR 1:2

                    msg = (
                        f"🔻 *{name} - SEGNALE SELL (STRATEGIA H4/H1)*\n"
                        f"-----------------------------------------\n"
                        f"📌 *Setup:* Chiusura H1 sotto la No Trade Zone H4\n"
                        f"🧱 *No Trade Zone H4:* {round(h4_low, decimals)} - {round(h4_high, decimals)}\n"
                        f"🎯 *Entry:* {entry}\n"
                        f"🛑 *Stop Loss:* {sl} (Sopra Massimo H4)\n"
                        f"✅ *Take Profit:* {tp} (RR 1:2)\n"
                        f"-----------------------------------------"
                    )
                    send_telegram_message(msg)

        except Exception as e:
            print(f"Errore durante la scansione di {name}: {e}")

# --- CICLO DI ESECUZIONE ---
if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()

    print("🤖 Bot Tradesby H4/H1 Avviato...")
    send_telegram_message("🤖 *Bot Tradesby (H4/H1) Aggiornato con SL Strutturale!*")

    while True:
        try:
            check_tradesby_strategy()
            time.sleep(900)
        except Exception as e:
            print(f"Errore ciclo principale: {e}")
            time.sleep(600)
