import time
import requests
import a2s
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION ---
SERVER_IP = "176.57.173.26"
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
was_online = None  # Cette variable sert de mémoire au script

def check_server():
    global message_id, was_online
    
    # 1. On récupère les infos du serveur
    try:
        info = a2s.info((SERVER_IP, QUERY_PORT), timeout=5.0)
        current_online = True
        message = f"🟢 **Le serveur Conan est EN LIGNE**\n\n👥 **Joueurs connectés :** {info.player_count}/{info.max_players}\n🗺️ **Carte :** {info.map_name}"
        color = 3066993 # Vert
    except Exception:
        current_online = False
        message = "🔴 **Le serveur Conan est HORS LIGNE !**\n\nLe serveur ne répond pas ou est en cours de redémarrage."
        color = 15158332 # Rouge

    # 2. ALERTE DE REDÉMARRAGE 
    # Si le serveur ÉTAIT hors ligne (False) et qu'il est MAINTENANT en ligne (True)
    if was_online is False and current_online is True:
        try:
            alert_payload = {
                "content": "🚀 **@here Le serveur Blood Lady vient de redémarrer ! Il est de nouveau accessible. Bon jeu à tous !**"
                # Astuce : Vous pouvez ajouter @everyone ou @ici au début du texte si vous voulez notifier tout le monde
            }
            requests.post(WEBHOOK_URL, json=alert_payload)
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'alerte : {e}")

    # On met à jour la mémoire pour le prochain tour
    was_online = current_online

    # Heure française approximative pour le footer
    current_time = time.strftime('%H:%M:%S')

    payload = {
        "embeds": [{
            "title": "Statut du Serveur Conan Exiles",
            "description": message,
            "color": color,
            "footer": {"text": f"Dernière mise à jour : {current_time}"}
        }]
    }

    # 3. On gère l'envoi ou la modification du message fixe
    try:
        if message_id is None:
            res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
            if res.status_code in [200, 201]:
                message_id = res.json().get("id")
        else:
            res = requests.patch(f"{WEBHOOK_URL}/messages/{message_id}", json=payload)
            if res.status_code == 404:
                res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
                if res.status_code in [200, 201]:
                    message_id = res.json().get("id")
    except Exception as e:
        print(f"Erreur Webhook : {e}")

# Boucle principale : vérifie toutes les 3 minutes
while True:
    check_server()
    time.sleep(180)
