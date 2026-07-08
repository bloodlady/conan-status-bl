import time
import requests
import a2s
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone, timedelta  # Plus besoin de zoneinfo !

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
    
    # GROS FILET DE SÉCURITÉ : Empêche le script de mourir quoi qu'il arrive
    try:
        # 1. On récupère les infos du serveur Conan
        try:
            info = a2s.info((SERVER_IP, QUERY_PORT), timeout=6.0)
            current_online = True
            message = f"🟢 **Le serveur *Blood Lady* est EN LIGNE**\n\n👥 **Joueurs connectés :** {info.player_count}/{info.max_players}\n🗺️ **Carte :** {info.map_name}"
            color = 3066993
        except Exception as e:
            print(f"⚠️ Erreur de connexion au serveur Conan : {e}")
            current_online = False
            message = "🔴 **Le serveur *Blood Lady* est HORS LIGNE !**\n\nLe serveur ne répond pas ou est en cours de redémarrage."
            color = 15158332

        # 2. ALERTE DE REDÉMARRAGE
        if was_online is False and current_online is True:
            try:
                alert_payload = {
                    "content": ":white_check_mark: **Le serveur *Blood Lady* Exiles vient de redémarrer ! Il est de nouveau accessible. Bon jeu ! 🟢**"
                }
                requests.post(WEBHOOK_URL, json=alert_payload)
                force_repost = True
            except Exception as e:
                print(f"Erreur lors de l'envoi de l'alerte : {e}")

        # On met à jour la mémoire d'état
        was_online = current_online

        # Heure française de Paris (UTC+2 en été) sans aucune bibliothèque externe
        tz_france = timezone(timedelta(hours=2))
        current_time = datetime.now(tz_france).strftime('%H:%M:%S')

        payload = {
            "embeds": [{
                "title": "Statut du Serveur",
                "description": message,
                "color": color,
                "footer": {"text": f"Dernière mise à jour : {current_time}"}
            }]
        }

        # 3. GESTION DE L'AFFICHAGE SILENCIEUX
        if force_repost and message_id is not None:
            try:
                requests.delete(f"{WEBHOOK_URL}/messages/{message_id}")
            except:
                pass
            message_id = None

        if message_id is None:
            # Premier lancement
            res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
            if res.status_code in [200, 201]:
                message_id = res.json().get("id")
            else:
                print(f"❌ Échec Discord POST. Code : {res.status_code}")
        else:
            # Mise à jour silencieuse
            res = requests.patch(f"{WEBHOOK_URL}/messages/{message_id}", json=payload)
            if res.status_code == 404:  # Si le message a été supprimé manuellement
                res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
                if res.status_code in [200, 201]:
                    message_id = res.json().get("id")
            elif res.status_code not in [200, 204]:
                print(f"❌ Échec Discord PATCH. Code : {res.status_code}")
                
    except Exception as main_error:
        # Si une erreur improbable survient, on l'affiche sans tuer le bot
        print(f"💥 Erreur critique générale : {main_error}")

# Boucle principale : vérifie toutes les 3 minutes
while True:
    check_server()
    time.sleep(90)
