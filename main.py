import time
import requests
import a2s
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from zoneinfo import ZoneInfo

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
was_online = None

def check_server():
    global message_id, was_online
    force_repost = False
    
    # 1. On récupère les infos du serveur Conan
    try:
        info = a2s.info((SERVER_IP, QUERY_PORT), timeout=6.0)
        current_online = True
        message = f"🟢 **Le serveur Conan est EN LIGNE**\n\n👥 **Joueurs connectés :** {info.player_count}/{info.max_players}\n🗺️ **Carte :** {info.map_name}"
        color = 3066993
    except Exception as e:
        print(f"⚠️ Erreur de connexion au serveur Conan : {e}")
        current_online = False
        message = "🔴 **Le serveur Conan est HORS LIGNE !**\n\nLe serveur ne répond pas ou est en cours de redémarrage."
        color = 15158332

    # 2. ALERTE DE REDÉMARRAGE
    if was_online is False and current_online is True:
        try:
            alert_payload = {
                "content": "🚀 **Le serveur Conan Exiles vient de redémarrer ! Il est de nouveau accessible. Bon jeu !**"
            }
            requests.post(WEBHOOK_URL, json=alert_payload)
            # Le serveur vient de rebooter, on demande au script de recréer la carte tout en bas
            force_repost = True
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'alerte : {e}")

    # On met à jour la mémoire d'état
    was_online = current_online

    # Heure française de Paris
    current_time = datetime.now(ZoneInfo("Europe/Paris")).strftime('%H:%M:%S')

    payload = {
        "embeds": [{
            "title": "Statut du Serveur Conan Exiles",
            "description": message,
            "color": color,
            "footer": {"text": f"Dernière mise à jour : {current_time}"}
        }]
    }

    # 3. GESTION DE L'AFFICHAGE SILENCIEUX
    try:
        # Si un reboot a eu lieu, on force la suppression de l'ancienne carte pour la remettre en bas
        if force_repost and message_id is not None:
            requests.delete(f"{WEBHOOK_URL}/messages/{message_id}")
            message_id = None

        if message_id is None:
            # Nouveau message ou après un reboot -> Envoi classique (génère une notification)
            res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
            if res.status_code in [200, 201]:
                message_id = res.json().get("id")
        else:
            # Mise à jour de routine -> On MODIFIE le message (100% silencieux, pas de notification)
            res = requests.patch(f"{WEBHOOK_URL}/messages/{message_id}", json=payload)
            if res.status_code == 404:  # Si le message a été supprimé manuellement entre temps
                res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
                if res.status_code in [200, 201]:
                    message_id = res.json().get("id")
            
    except Exception as e:
        print(f"Erreur Webhook : {e}")

# Boucle principale : vérifie toutes les 3 minutes
while True:
    check_server()
    time.sleep(180)
