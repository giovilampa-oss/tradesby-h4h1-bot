import time
import requests
import os
from threading import Thread
from flask import Flask

# --- MINI-SERVER PER MANTENERE APERTA LA PORTA SU RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Traders B (H4/H1) is running!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
# -----------------------------------------------------------

# Configurazioni Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Token o Chat ID Telegram non configurati!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Errore nell'invio del messaggio Telegram: {e}")

def trading_strategy():
    print("Analisi multitimeframe (H4 + H1) per Traders B in corso...")
    
    # --- LOGICA SPECIFICA TRADERS B ---
    # Qui andranno i tuoi controlli incrociati tra H4 (struttura) e H1 (entry)
    setup_trovato = False 
    
    if setup_trovato:
        messaggio = (
            f"📊 *TRADERS B - H4/H1 SIGNAL* 📊\n\n"
            f"🪙 *Asset:* XAUUSD\n"
            f"⏱ *Timeframe:* H4 (Struttura) + H1 (Entry)\n"
            f"Condizioni di mercato soddisfatte!"
        )
        send_telegram_message(messaggio)

if __name__ == "__main__":
    # Avvia il mini-server Flask in un thread separato
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
    
    print("Traders B avviato in modalità autonoma (H4/H1).")
    
    # Ciclo continuo 24/7
    while True:
        try:
            trading_strategy()
        except Exception as e:
            print(f"Errore nel ciclo: {e}")
        
        # Pausa di sicurezza (60 secondi)
        time.sleep(60)
