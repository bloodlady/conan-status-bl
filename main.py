import time
import requests
import a2s
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION ---
SERVER_IP = "176.57.173.26"
QUERY_PORT = 28615  # Remplace par ton Query Port (sans guillemets)
WEBHOOK_URL = "https://discord.com/api/webhooks/1517110605205602444/m6mgzZO5O8PSX_vU4M_84PmqCbt7V1DvpFfJhpjH7GTbcBi0uhg-ZuVWh2Tu1-D2o2Zu"
# ---------------------

# --- SERVEUR WEB FACTICE (Obligatoire pour l'hébergeur gratuit) ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Le bot fonctionne !")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()
# ------------------------------------------------------------------

last_status = None

def check_server():
    global last_status
    try:
        # Interrogation du Query Port (timeout de 5 secondes max)
        info = a2s.info((SERVER_IP, QUERY_PORT), timeout=5.0)
        current_status = "online"
        message = f"🟢 **Le serveur Conan est EN LIGNE**\nJoueurs connectés : {info.player_count}/{info.max_players}"
        color = 3066993 # Code couleur Vert
    except Exception:
        current_status = "offline"
        message = "🔴 **Le serveur Conan est HORS LIGNE !**"
        color = 15158332 # Code couleur Rouge

    # On envoie un message sur Discord UNIQUEMENT si le statut a changé
    if current_status != last_status:
        payload = {
            "embeds": [{
                "title": "Statut du Serveur",
                "description": message,
                "color": color
            }]
        }
        requests.post(WEBHOOK_URL, json=payload)
        last_status = current_status

# Boucle principale : vérifie toutes les 3 minutes (180 secondes)
while True:
    check_server()
    time.sleep(180)
