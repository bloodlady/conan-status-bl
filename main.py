import time
import requests
import a2s
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION ---
SERVER_IP = "TON_IP_GPORTAL"
QUERY_PORT = 27015  # Remplace par ton Query Port
WEBHOOK_URL = "TON_URL_WEBHOOK_DISCORD"
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

def check_server():
    global message_id
    
    # 1. On récupère les infos du serveur
    try:
        info = a2s.info((SERVER_IP, QUERY_PORT), timeout=5.0)
        message = f"🟢 **Le serveur Conan est EN LIGNE**\n\n👥 **Joueurs connectés :** {info.player_count}/{info.max_players}\n🗺️ **Carte :** {info.map_name}"
        color = 3066993 # Vert
    except Exception:
        message = "🔴 **Le serveur Conan est HORS LIGNE !**\n\nLe serveur ne répond pas ou est en cours de redémarrage."
        color = 15158332 # Rouge

    # Heure française approximative pour le footer (Render est souvent à l'heure UTC)
    current_time = time.strftime('%H:%M:%S')

    payload = {
        "embeds": [{
            "title": "Statut du Serveur Conan Exiles",
            "description": message,
            "color": color,
            "footer": {"text": f"Dernière mise à jour : {current_time}"}
        }]
    }

    # 2. On gère l'envoi ou la modification du message sur Discord
    try:
        if message_id is None:
            # Premier lancement : on crée le message et on sauvegarde son ID
            res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
            if res.status_code in [200, 201]:
                message_id = res.json().get("id")
        else:
            # Lancements suivants : on MODIFIE le message existant
            res = requests.patch(f"{WEBHOOK_URL}/messages/{message_id}", json=payload)
            # Si le message a été supprimé manuellement sur Discord, on en recrée un
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
