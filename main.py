import os
import time
import datetime
import pytz
import requests
from threading import Thread
from flask import Flask

# ---------------------------------------------------------
# CONFIGURAZIONE FLASK (Keep-alive per Render)
# ---------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Tradesby Multi-Asset Strategy V2 Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ---------------------------------------------------------
# CONFIGURAZIONE BOT TELEGRAM E TWELVE DATA
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TUO_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "TUO_CHAT_ID")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "TUO_TWELVE_DATA_KEY")

# Dizionario dei simboli monitorati con i rispettivi ticker esatti per Twelve Data
SYMBOLS_MAP = {
    "Oro": "XAU/USD",
    "Nasdaq": "IXIC",         # Oppure NDX a seconda del feed, IXIC è l'indice NASDAQ Composite
    "Bitcoin": "BTC/USD",
    "S&P 500": "SPX"          # Oppure GSPC
}

BASE_TF = "4h"       # Timeframe di riferimento per la struttura
EXEC_TF = "15min"    # Timeframe di esecuzione
CHECK_INTERVAL = 60  # Controllo ogni 60 secondi

# Dizionario per tracciare lo stato e la posizione di ogni singolo strumento in modo indipendente
active_trades = {
    name: {
        "open": False,
        "type": None,          # "LONG" o "SHORT"
        "entry_price": 0.0,
        "sl": 0.0,
        "tp": 0.0,
        "breakeven_set": False
    } for name in SYMBOLS_MAP.keys()
}

last_analyzed_candle = {name: None for name in SYMBOLS_MAP.keys()}

# ---------------------------------------------------------
# FUNZIONI DI SUPPORTO E COMUNICAZIONE TELEGRAM
# ---------------------------------------------------------
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Errore invio Telegram: {e}")
    return None

def get_candles(ticker, tf, outputsize=50):
    """Recupera le candele storiche da Twelve Data per un dato ticker e timeframe con indicatore ATR"""
    url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval={tf}&outputsize={outputsize}&apikey={TWELVE_DATA_KEY}&indicators=atr(timeperiod=14)"
    try:
        res = requests.get(url, timeout=10).json()
        if "values" in res:
            data = res["values"]
            data.reverse()  # Ordine cronologico (dalla più vecchia alla più recente)
            return data
        else:
            print(f"Risposta Twelve Data non valida per {ticker}: {res}")
    except Exception as e:
        print(f"Errore Twelve Data ({ticker} - {tf}): {e}")
    return None

# ---------------------------------------------------------
# LOGICA STRATEGIA V2 PER SINGOLO SIMBOLO
# ---------------------------------------------------------
def evaluate_symbol(friendly_name, ticker):
    global active_trades, last_analyzed_candle

    base_candles = get_candles(ticker, BASE_TF, outputsize=30)
    exec_candles = get_candles(ticker, EXEC_TF, outputsize=30)

    if not base_candles or not exec_candles or len(base_candles) < 10 or len(exec_candles) < 10:
        return

    last_exec = exec_candles[-2]    # Ultima candela chiusa
    prev_exec = exec_candles[-3]    # Candela precedente
    
    current_time = last_exec['datetime']
    tz = pytz.timezone('Europe/Rome')
    formatted_time = datetime.datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

    close_p = float(last_exec['close'])
    high_p = float(last_exec['high'])
    low_p = float(last_exec['low'])
    open_p = float(last_exec['open'])
    atr = float(last_exec.get('atr', 1.5))

    # Identificazione dei livelli di chiusura sul base timeframe (escludendo le ombre, usiamo i close)
    base_closes = [float(c['close']) for c in base_candles[-10:-2]]
    broken_high = max(base_closes)  
    broken_low = min(base_closes)   

    trade = active_trades[friendly_name]

    # ==========================================
    # GESTIONE TRADE APERTO (BREAK EVEN STRUTTURALE)
    # ==========================================
    if trade["open"]:
        if trade["type"] == "LONG" and close_p > broken_high:
            if not trade["breakeven_set"]:
                trade["sl"] = trade["entry_price"]
                trade["breakeven_set"] = True
                msg = f"🔒 **BREAK EVEN ATTIVATO ({friendly_name} - LONG)**\nSL spostato a: `{trade['entry_price']}`"
                send_telegram_message(msg)
                print(f"[{formatted_time}] {friendly_name}: SL a Break Even (LONG)")

        elif trade["type"] == "SHORT" and close_p < broken_low:
            if not trade["breakeven_set"]:
                trade["sl"] = trade["entry_price"]
                trade["breakeven_set"] = True
                msg = f"🔒 **BREAK EVEN ATTIVATO ({friendly_name} - SHORT)**\nSL spostato a: `{trade['entry_price']}`"
                send_telegram_message(msg)
                print(f"[{formatted_time}] {friendly_name}: SL a Break Even (SHORT)")
        return

    # Evita di analizzare la stessa candela due volte per lo stesso strumento
    if last_analyzed_candle[friendly_name] == current_time:
        return

    # ==========================================
    # RICERCA NUOVI SETUP (STRATEGIA V2)
    # ==========================================
    body_size = abs(close_p - open_p)
    candle_range = high_p - low_p
    if candle_range == 0:
        return

    # --- SETUP LONG (Trend Rialzista) ---
    is_correction_long = low_p < broken_high
    is_bullish_engulfing = (close_p > open_p) and (body_size > candle_range * 0.5) and (close_p > float(prev_exec['high']))

    if is_correction_long and is_bullish_engulfing:
        last_analyzed_candle[friendly_name] = current_time
        sl = round(float(exec_candles[-2]['low']) - (0.5 * atr), 2)
        tp = round(broken_high + (broken_high - sl), 2)
        
        active_trades[friendly_name] = {
            "open": True,
            "type": "LONG",
            "entry_price": close_p,
            "sl": sl,
            "tp": tp,
            "breakeven_set": False
        }

        msg = (
            f"⚡ **TRADESBY V2 - SEGNALE LONG** ⚡\n\n"
            f"🪙 **Strumento:** {friendly_name} ({ticker})\n"
            f"📊 **TF Base/Exec:** {BASE_TF} / {EXEC_TF}\n"
            f"💵 **Entrata:** `{close_p}`\n"
            f"🛑 **Stop Loss:** `{sl}`\n"
            f"🎯 **Take Profit:** `{tp}`\n"
            f"⏰ **Orario:** {formatted_time}"
        )
        send_telegram_message(msg)
        print(f"[{formatted_time}] Segnale LONG inviato per {friendly_name}.")
        return

    # --- SETUP SHORT (Trend Ribassista) ---
    is_correction_short = high_p > broken_low
    is_bearish_engulfing = (close_p < open_p) and (body_size > candle_range * 0.5) and (close_p < float(prev_exec['low']))

    if is_correction_short and is_bearish_engulfing:
        last_analyzed_candle[friendly_name] = current_time
        sl = round(float(exec_candles[-2]['high']) + (0.5 * atr), 2)
        tp = round(broken_low - (sl - broken_low), 2)

        active_trades[friendly_name] = {
            "open": True,
            "type": "SHORT",
            "entry_price": close_p,
            "sl": sl,
            "tp": tp,
            "breakeven_set": False
        }

        msg = (
            f"⚡ **TRADESBY V2 - SEGNALE SHORT** ⚡\n\n"
            f"🪙 **Strumento:** {friendly_name} ({ticker})\n"
            f"📊 **TF Base/Exec:** {BASE_TF} / {EXEC_TF}\n"
            f"💵 **Entrata:** `{close_p}`\n"
            f"🛑 **Stop Loss:** `{sl}`\n"
            f"🎯 **Take Profit:** `{tp}`\n"
            f"⏰ **Orario:** {formatted_time}"
        )
        send_telegram_message(msg)
        print(f"[{formatted_time}] Segnale SHORT inviato per {friendly_name}.")
        return

# ---------------------------------------------------------
# LOOP PRINCIPALE MULTI-ASSET
# ---------------------------------------------------------
def main_loop():
    print("🚀 Tradesby Multi-Asset Strategy V2 Bot Avviato con successo!")
    send_telegram_message("⚡ **Tradesby Multi-Asset Strategy V2 Bot Attivo e Operativo su Oro, Nasdaq, Bitcoin e S&P 500!** 🚀")
    
    while True:
        for friendly_name, ticker in SYMBOLS_MAP.items():
            try:
                evaluate_symbol(friendly_name, ticker)
            except Exception as e:
                print(f"Errore critico nel loop per lo strumento {friendly_name}: {e}")
            time.sleep(2) # Pausa breve tra una richiesta e l'altra per rispettare i limiti API di Twelve Data
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # Avvio del server Flask in background per mantenere il servizio attivo su Render
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Avvio del ciclo principale di analisi dei mercati
    main_loop()
