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
    return "Tradesby H4/H1 Strategy V2 Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ---------------------------------------------------------
# CONFIGURAZIONE BOT TELEGRAM E TWELVE DATA
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TUO_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "TUO_CHAT_ID")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "TUO_TWELVE_DATA_KEY")

SYMBOL = "XAU/USD"
BASE_TF = "4h"       # Timeframe di riferimento per la struttura (es. H4 o H1)
EXEC_TF = "15min"    # Timeframe di esecuzione (es. M15 o M5)
CHECK_INTERVAL = 60  # Controllo ogni 60 secondi

# Stato della posizione e della struttura di mercato
active_trade = {
    "open": False,
    "type": None,          # "LONG" o "SHORT"
    "entry_price": 0.0,
    "sl": 0.0,
    "tp": 0.0,
    "target_level": 0.0,   # Massimo o minimo strutturale rotto
    "breakeven_set": False
}

last_analyzed_candle = None

# ---------------------------------------------------------
# FUNZIONI DI SUPPORTO
# ---------------------------------------------------------
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def get_candles(tf, outputsize=50):
    """Recupera le candele storiche da Twelve Data per un dato timeframe"""
    url = f"https://api.twelvedata.com/time_series?symbol={SYMBOL}&interval={tf}&outputsize={outputsize}&apikey={TWELVE_DATA_KEY}&indicators=atr(timeperiod=14)"
    try:
        res = requests.get(url, timeout=10).json()
        if "values" in res:
            data = res["values"]
            data.reverse()  # Ordine cronologico (dalla più vecchia alla più recente)
            return data
    except Exception as e:
        print(f"Errore Twelve Data ({tf}): {e}")
    return None

# ---------------------------------------------------------
# LOGICA STRATEGIA V2
# ---------------------------------------------------------
def evaluate_strategy():
    global active_trade, last_analyzed_candle

    # 1. Recupero dati dai due timeframe
    base_candles = get_candles(BASE_TF, outputsize=30)
    exec_candles = get_candles(EXEC_TF, outputsize=30)

    if not base_candles or not exec_candles or len(base_candles) < 10 or len(exec_candles) < 10:
        return

    # Candele attuali e precedenti sul timeframe di esecuzione
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

    # Identificazione dei livelli di chiusura sul base timeframe (escludendo le ombre, usiamo i close/body)
    base_closes = [float(c['close']) for c in base_candles[-10:-2]]
    broken_high = max(base_closes)  # Massimo basato sui corpi/livelli rotti
    broken_low = min(base_closes)   # Minimo basato sui corpi/livelli rotti

    # ==========================================
    # GESTIONE TRADE APERTO (CONTROLLO BREAK EVEN)
    # ==========================================
    if active_trade["open"]:
        # Regola Break Even: appena il prezzo rompe una nuova struttura a favore, sposta a BE
        if active_trade["type"] == "LONG" and close_p > broken_high:
            if not active_trade["breakeven_set"]:
                active_trade["sl"] = active_trade["entry_price"]
                active_trade["breakeven_set"] = True
                msg = f"🔒 **BREAK EVEN ATTIVATO (LONG)**\nPrezzo SL spostato a: `{active_trade['entry_price']}`"
                send_telegram_message(msg)
                print(f"[{formatted_time}] SL spostato a Break Even per trade LONG")

        elif active_trade["type"] == "SHORT" and close_p < broken_low:
            if not active_trade["breakeven_set"]:
                active_trade["sl"] = active_trade["entry_price"]
                active_trade["breakeven_set"] = True
                msg = f"🔒 **BREAK EVEN ATTIVATO (SHORT)**\nPrezzo SL spostato a: `{active_trade['entry_price']}`"
                send_telegram_message(msg)
                print(f"[{formatted_time}] SL spostato a Break Even per trade SHORT")
        return

    # Evita di analizzare la stessa candela due volte
    if last_analyzed_candle == current_time:
        return

    # ==========================================
    # RICERCA NUOVI SETUP (STRATEGIA V2)
    # ==========================================
    
    # --- SETUP LONG (Trend Rialzista) ---
    # A & B. Identificazione livello rotto e ritracciamento sotto la linea del livello rotto
    is_correction_long = low_p < broken_high
    # C. Conferma ed Entrata: Rifiuto (wick) o Engulfing rialzista al superamento
    body_size = abs(close_p - open_p)
    candle_range = high_p - low_p
    is_bullish_engulfing = (close_p > open_p) and (body_size > candle_range * 0.5) and (close_p > float(prev_exec['high']))

    if is_correction_long and is_bullish_engulfing:
        last_analyzed_candle = current_time
        # D. Gestione SL e TP strutturali
        sl = round(float(exec_candles[-2]['low']) - (0.5 * atr), 2)  # Ultimo minimo creato
        tp = round(broken_high + (broken_high - sl), 2)              # Massimo strutturale
        
        active_trade = {
            "open": True,
            "type": "LONG",
            "entry_price": close_p,
            "sl": sl,
            "tp": tp,
            "breakeven_set": False
        }

        msg = (
            f"⚡ **TRADESBY V2 - SEGNALE LONG** ⚡\n\n"
            f"🪙 **Strumento:** {SYMBOL}\n"
            f"📊 **TF Base/Exec:** {BASE_TF} / {EXEC_TF}\n"
            f"💵 **Entrata:** `{close_p}`\n"
            f"🛑 **Stop Loss:** `{sl}`\n"
            f"🎯 **Take Profit:** `{tp}`\n"
            f"⏰ **Orario:** {formatted_time}"
        )
        send_telegram_message(msg)
        print(f"[{formatted_time}] Segnale LONG inviato.")
        return

    # --- SETUP SHORT (Trend Ribassista) ---
    # A & B. Ritracciamento sopra il minimo rotto
    is_correction_short = high_p > broken_low
    # C. Conferma ed Entrata: Rifiuto o Engulfing ribassista
    is_bearish_engulfing = (close_p < open_p) and (body_size > candle_range * 0.5) and (close_p < float(prev_exec['low']))

    if is_correction_short and is_bearish_engulfing:
        last_analyzed_candle = current_time
        # D. Gestione SL e TP strutturali
        sl = round(float(exec_candles[-2]['high']) + (0.5 * atr), 2) # Ultimo massimo creato
        tp = round(broken_low - (sl - broken_low), 2)                # Minimo strutturale

        active_trade = {
            "open": True,
            "type": "SHORT",
            "entry_price": close_p,
            "sl": sl,
            "tp": tp,
            "breakeven_set": False
        }

        msg = (
            f"⚡ **TRADESBY V2 - SEGNALE SHORT** ⚡\n\n"
            f"🪙 **Strumento:** {SYMBOL}\n"
            f"📊 **TF Base/Exec:** {BASE_TF} / {EXEC_TF}\n"
            f"💵 **Entrata:** `{close_p}`\n"
            f"🛑 **Stop Loss:** `{sl}`\n"
            f"🎯 **Take Profit:** `{tp}`\n"
            f"⏰ **Orario:** {formatted_time}"
        )
        send_telegram_message(msg)
        print(f"[{formatted_time}] Segnale SHORT inviato.")
        return

# ---------------------------------------------------------
# LOOP PRINCIPALE
# ---------------------------------------------------------
def main_loop():
    print("🚀 Tradesby Strategy V2 Bot Avviato!")
    send_telegram_message("⚡ **Tradesby H4/H1 Strategy V2 Bot Attivo!** 🚀")
    
    while True:
        try:
            evaluate_strategy()
        except Exception as e:
            print(f"Errore nel loop principale: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # Avvia Flask in un thread separato per mantenere Render attivo (Keep-Alive)
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

    # Avvia il loop di trading principale
    main_loop()
