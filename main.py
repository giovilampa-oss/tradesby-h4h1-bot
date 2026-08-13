import time
import requests
import os
from threading import Thread
from flask import Flask

# Configurazione del mini-server per soddisfare Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

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
    print("Analisi di mercato in corso...")
    # Qui inserisci la logica della strategia
    setup_trovato = False 
    
    if setup_trovato:
        messaggio = "📈 *SEGNALE DI TRADING* 📈\nCondizioni soddisfatte!"
        send_telegram_message(messaggio)

if __name__ == "__main__":
    # Avvia il mini-server Flask in un thread separato per tenere aperta la porta
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
    
    print("Bot avviato in modalità autonoma con supporto Web.")
    
    # Ciclo continuo 24/7 in background
    while True:
        try:
            trading_strategy()
        except Exception as e:
            print(f"Errore nel ciclo: {e}")
        
        time.sleep(60)
