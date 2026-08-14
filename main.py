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
    return "TradesBy H4/H1 Ultimate Multi-Asset Bot PRO is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ---------------------------------------------------------
# CONFIGURAZIONE BOT TELEGRAM E TWELVE DATA
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN") or "8985062147:AAFnXAe9zk70k6sji3vo..."
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or "8665047525"
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY") or "fa500c91581d4b4685dd1040f541ac8e"

TIMEFRAME = "1h"
CHECK_INTERVAL = 300  # Controllo ogni 5 minuti

# LISTA COMPLETA DEGLI ASSET (GOLD + INDICI USA + CRYPTO + FX)
ASSETS = [
    # Top Priority - ORO & INDICI USA
    {"name": "GOLD (XAU/USD)", "symbol": "XAU/USD", "decimals": 2, "rr": 2.5, "atr_mult": 1.2},
    {"name": "NASDAQ 100", "symbol": "NDX", "decimals": 1, "rr": 2.5, "atr_mult": 1.3},
    {"name": "S&P 500", "symbol": "SPX", "decimals": 1, "rr": 2.0, "atr_mult": 1.2},
    {"name": "DOW JONES", "symbol": "DJI", "decimals": 1, "rr": 2.0, "atr_mult": 1.2},

    # Crypto & Forex
    {"name": "BITCOIN", "symbol": "BTC/USD", "decimals": 2, "rr": 2.0, "atr_mult": 1.5},
    {"name": "EUR/USD", "symbol": "EUR/USD", "decimals": 5, "rr": 2.0, "atr_mult": 1.0}
]

last_signals = {}
active_trades = []

# ---------------------------------------------------------
# FUNZIONI DI SUPPORTO
# ---------------------------------------------------------
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def get_market_data(symbol):
    """Recupera candele H1, ATR e EMA 200 per uno specifico simbolo"""
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={TIMEFRAME}&outputsize=250&apikey={TWELVE_DATA_KEY}&indicators=atr,ema"
    try:
        res = requests.get(url, timeout=10).json()
        if "values" in res:
            data = res["values"]
            data.reverse()
            return data
    except Exception as e:
        print(f"Errore Twelve Data su {symbol}: {e}")
    return None

# ---------------------------------------------------------
# THREAD: MONITORAGGIO WIN / LOSS / BREAK-EVEN
# ---------------------------------------------------------
def monitor_active_trades():
    global active_trades
    while True:
        try:
            if active_trades:
                trades_to_remove = []
                for trade in active_trades:
                    candles = get_market_data(trade['symbol'])
                    if not candles or len(candles) == 0:
                        continue

                    current_price = float(candles[-1]['close'])
                    decimals = trade['decimals']

                    # LONG
                    if trade['type'] == 'LONG':
                        if not trade['be_notified'] and current_price >= (trade['entry'] + trade['risk']):
                            send_telegram_message(
                                f"🛡️ **TRADESBY - BREAK-EVEN ({trade['name']})**\n\n"
                                f"Il prezzo ha raggiunto +1R (`{round(current_price, decimals)}`)\n"
                                f"💡 **Azione:** Sposta lo Stop Loss a B/E (`{round(trade['entry'], decimals)}`)."
                            )
                            trade['be_notified'] = True

                        if current_price >= trade['tp']:
                            send_telegram_message(
                                f"🚀 **TRADESBY - TAKE PROFIT! (WIN)** 🎉\n\n"
                                f"**Asset:** {trade['name']}\n"
                                f"**Tipo:** LONG Swing\n"
                                f"**Target Raggiunto:** `{round(trade['tp'], decimals)}`"
                            )
                            trades_to_remove.append(trade)

                        elif current_price <= trade['sl']:
                            send_telegram_message(
                                f"🔴 **TRADESBY - STOP LOSS** 🛑\n\n"
                                f"**Asset:** {trade['name']}\n"
                                f"**Prezzo Uscita:** `{round(trade['sl'], decimals)}`"
                            )
                            trades_to_remove.append(trade)

                    # SHORT
                    elif trade['type'] == 'SHORT':
                        if not trade['be_notified'] and current_price <= (trade['entry'] - trade['risk']):
                            send_telegram_message(
                                f"🛡️ **TRADESBY - BREAK-EVEN ({trade['name']})**\n\n"
                                f"Il prezzo ha raggiunto +1R (`{round(current_price, decimals)}`)\n"
                                f"💡 **Azione:** Sposta lo Stop Loss a B/E (`{round(trade['entry'], decimals)}`)."
                            )
                            trade['be_notified'] = True

                        if current_price <= trade['tp']:
                            send_telegram_message(
                                f"🚀 **TRADESBY - TAKE PROFIT! (WIN)** 🎉\n\n"
                                f"**Asset:** {trade['name']}\n"
                                f"**Tipo:** SHORT Swing\n"
                                f"**Target Raggiunto:** `{round(trade['tp'], decimals)}`"
                            )
                            trades_to_remove.append(trade)

                        elif current_price >= trade['sl']:
                            send_telegram_message(
                                f"🔴 **TRADESBY - STOP LOSS** 🛑\n\n"
                                f"**Asset:** {trade['name']}\n"
                                f"**Prezzo Uscita:** `{round(trade['sl'], decimals)}`"
                            )
                            trades_to_remove.append(trade)

                for t in trades_to_remove:
                    if t in active_trades:
                        active_trades.remove(t)

        except Exception as e:
            print(f"Errore monitoraggio: {e}")

        time.sleep(30)

# ---------------------------------------------------------
# LOGICA DI TRADING: SWING CONTINUATION
# ---------------------------------------------------------
def analyze_asset(asset):
    global last_signals, active_trades

    symbol = asset['symbol']
    name = asset['name']
    decimals = asset['decimals']
    rr_target = asset['rr']
    atr_mult = asset['atr_mult']

    candles = get_market_data(symbol)
    if not candles or len(candles) < 20:
        return

    last_candle = candles[-2]
    prev_candles = candles[-12:-2]

    time_str = last_candle['datetime']
    if last_signals.get(symbol) == time_str:
        return

    try:
        dt_utc = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.utc)
        rome_tz = pytz.timezone("Europe/Rome")
        formatted_time = dt_utc.astimezone(rome_tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        formatted_time = time_str

    close_p = float(last_candle['close'])
    high_p = float(last_candle['high'])
    low_p = float(last_candle['low'])
    open_p = float(last_candle['open'])

    ema_200 = float(last_candle.get('ema', close_p))
    atr = float(last_candle.get('atr', 2.0))

    recent_high = max(float(c['high']) for c in prev_candles)
    recent_low = min(float(c['low']) for c in prev_candles)

    # SWING BUY
    if close_p > recent_high and close_p > ema_200 and close_p > open_p:
        last_signals[symbol] = time_str

        sl = round(low_p - (atr_mult * atr), decimals)
        risk = round(close_p - sl, decimals)
        tp = round(close_p + (risk * rr_target), decimals)

        active_trades.append({
            'name': name,
            'symbol': symbol,
            'type': 'LONG',
            'entry': close_p,
            'sl': sl,
            'tp': tp,
            'risk': risk,
            'decimals': decimals,
            'be_notified': False
        })

        msg = (
            f"📈 **TRADESBY PRO - SEGNALE BUY ({name})**🔥 🇮🇹\n\n"
            f"📊 **Struttura:** Breakout Continuation H1\n"
            f"📍 **Prezzo Entrata:** `{round(close_p, decimals)}`\n"
            f"🛑 **Stop Loss:** `{sl}`\n"
            f"🎯 **Take Profit (1:{rr_target}):** `{tp}`\n"
            f"⏱️ **Orario:** `{formatted_time}`"
        )
        send_telegram_message(msg)
        return

    # SWING SELL
    if close_p < recent_low and close_p < ema_200 and close_p < open_p:
        last_signals[symbol] = time_str

        sl = round(high_p + (atr_mult * atr), decimals)
        risk = round(sl - close_p, decimals)
        tp = round(close_p - (risk * rr_target), decimals)

        active_trades.append({
            'name': name,
            'symbol': symbol,
            'type': 'SHORT',
            'entry': close_p,
            'sl': sl,
            'tp': tp,
            'risk': risk,
            'decimals': decimals,
            'be_notified': False
        })

        msg = (
            f"📉 **TRADESBY PRO - SEGNALE SELL ({name})**🔥 🇮🇹\n\n"
            f"📊 **Struttura:** Breakout Continuation H1\n"
            f"📍 **Prezzo Entrata:** `{round(close_p, decimals)}`\n"
            f"🛑 **Stop Loss:** `{sl}`\n"
            f"🎯 **Take Profit (1:{rr_target}):** `{tp}`\n"
            f"⏱️ **Orario:** `{formatted_time}`"
        )
        send_telegram_message(msg)
        return

# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------
if __name__ == '__main__':
    t_flask = Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()

    t_monitor = Thread(target=monitor_active_trades)
    t_monitor.daemon = True
    t_monitor.start()

    send_telegram_message("📊 TradesBy Ultimate Bot PRO (Gold + US Indices + BTC + FX) Avviato! 🚀")

    while True:
        try:
            for asset in ASSETS:
                analyze_asset(asset)
                time.sleep(2)  # Pausa di 2 secondi tra gli asset per rispettare le API
        except Exception as e:
            print(f"Errore esecuzione: {e}")
        time.sleep(CHECK_INTERVAL)
