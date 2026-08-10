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

            # 1. Definizione della No Trade Zone (High e Low H4 recenti)
            h4_high = df_4h['High'].iloc[-2]
            h4_low = df_4h['Low'].iloc[-2]

            # 2. Verifica Chiusura Candela H1
            last_h1_close = round(df_h1['Close'].iloc[-1], 2)
            last_h1_low = round(df_h1['Low'].iloc[-1], 2)
            last_h1_high = round(df_h1['High'].iloc[-1], 2)

            # --- SEGNALE BUY (Chiusura H1 SOPRA la No Trade Zone H4) ---
            if last_h1_close > h4_high:
                entry = last_h1_close
                sl = round(last_h1_low, 2)
                tp = round(entry + ((entry - sl) * 2), 2)  # RR 1:2

                msg = (
                    f"🚀 *{name} - SEGNALE BUY (STRATEGIA H4/H1)*\n"
                    f"-----------------------------------------\n"
                    f"📌 *Setup:* Chiusura H1 fuori dalla No Trade Zone H4\n"
                    f"🧱 *No Trade Zone H4:* {round(h4_low, 2)} - {round(h4_high, 2)}\n"
                    f"🎯 *Entry:* {entry}\n"
                    f"🛑 *Stop Loss:* {sl}\n"
                    f"✅ *Take Profit:* {tp} (RR 1:2)\n"
                    f"-----------------------------------------"
                )
                send_telegram_message(msg)

            # --- SEGNALE SELL (Chiusura H1 SOTTO la No Trade Zone H4) ---
            elif last_h1_close < h4_low:
                entry = last_h1_close
                sl = round(last_h1_high, 2)
                tp = round(entry - ((sl - entry) * 2), 2)  # RR 1:2

                msg = (
                    f"🔻 *{name} - SEGNALE SELL (STRATEGIA H4/H1)*\n"
                    f"-----------------------------------------\n"
                    f"📌 *Setup:* Chiusura H1 fuori dalla No Trade Zone H4\n"
                    f"🧱 *No Trade Zone H4:* {round(h4_low, 2)} - {round(h4_high, 2)}\n"
                    f"🎯 *Entry:* {entry}\n"
                    f"🛑 *Stop Loss:* {sl}\n"
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
    send_telegram_message("🤖 *Bot Tradesby (H4/H1) Attivo!* In ascolto per Oro, Cripto, Indici e Forex...")

    while True:
        try:
            check_tradesby_strategy()
            time.sleep(900)
        except Exception as e:
            print(f"Errore ciclo principale: {e}")
            time.sleep(600)
