import time
import requests
import a2s
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION ---
SERVER_IP = "176.57.173.26:28600"
QUERY_PORT = 28615  # Remplace par ton Query Port
WEBHOOK_URL = "https://discord.com/api/webhooks/1517110605205602444/m6mgzZO5O8PSX_vU4M_84PmqCbt7V1DvpFfJhpjH7GTbcBi0uhg-ZuVWh2Tu1-D2o2Zu"
# ---------------------

# --- SERVEUR WEB FACTICE ---
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

message_id = None
was_online = None  # Mémoire du script

def check_server():
    global message_id, was_online
    
    # 1. On récupère les infos du serveur Conan
    try:
        info = a2s.info((SERVER_IP, QUERY_PORT), timeout=5.0)
        current_online = True
        message = f"🟢 **Le serveur *Blood Lady* est EN LIGNE**\n\n👥 **Joueurs connectés :** {info.player_count}/{info.max_players}\n🗺️ **Carte :** {info.map_name}"
        color = 3066993 # Vert
    except Exception:
        current_online = False
        message = "🔴 **Le serveur *Blood Lady* est HORS LIGNE !**\n\nLe serveur ne répond pas ou est en cours de redémarrage."
        color = 15158332 # Rouge

    # 2. ALERTE DE REDÉMARRAGE
    if was_online is False and current_online is True:
        try:
            alert_payload = {
                "content": "🚀 **Le serveur *Blood Lady* vient de redémarrer ! Il est de nouveau accessible. Bon jeu à tous !**"
            }
            requests.post(WEBHOOK_URL, json=alert_payload)
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'alerte : {e}")

    # On met à jour la mémoire d'état
    was_online = current_online

    # Heure de la mise à jour
    current_time = time.strftime('%H:%M:%S')

    payload = {
        "embeds": [{
            "title": "Statut du Serveur Conan Exiles",
            "description": message,
            "color": color,
            "footer": {"text": f"Dernière mise à jour : {current_time}"}
        }]
    }

    # 3. GESTION DE L'AFFICHAGE (Toujours tout en bas)
    try:
        # Si un ancien message existe, on le supprime d'abord
        if message_id is not None:
            requests.delete(f"{WEBHOOK_URL}/messages/{message_id}")
            
        # On poste le nouveau message tout en bas du salon
        res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
        if res.status_code in [200, 201]:
            message_id = res.json().get("id")
            
    except Exception as e:
        print(f"Erreur Webhook (repost) : {e}")

# Boucle principale : vérifie toutes les 3 minutes
while True:
    check_server()
    time.sleep(120)
