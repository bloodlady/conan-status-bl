import time
import requests
import a2s
import os
import sys
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone, timedelta

# ============================================================
#  CONFIGURATION
#  Toutes les valeurs sensibles se règlent dans Render, dans
#  l'onglet "Environment" du service. Rien à modifier ici.
# ============================================================

def get_required_env(name):
    value = os.environ.get(name)
    if not value:
        print(f"❌ ERREUR : la variable d'environnement '{name}' n'est pas définie. "
              f"Va dans Render > ton service > Environment, et ajoute-la.")
        sys.exit(1)
    return value

WEBHOOK_URL = get_required_env("WEBHOOK_URL")
GITHUB_TOKEN = get_required_env("GITHUB_TOKEN")
GIST_ID = get_required_env("GIST_ID")

SERVER_IP = os.environ.get("SERVER_IP", "176.57.173.26")
QUERY_PORT = int(os.environ.get("QUERY_PORT", "28615"))

# Heure (0-23, heure de Paris) du reboot quotidien deja programme sur GPortal.
# Si definie, aucune alerte de redemarrage n'est envoyee quand le serveur
# s'arrete pendant cette fenetre (c'est un reboot attendu, pas une mise a jour).
# Si non definie (laisser vide sur Render), une alerte sera envoyee a CHAQUE
# arret du serveur, quelle qu'en soit la cause.
REBOOT_QUOTIDIEN_HEURE = os.environ.get("REBOOT_QUOTIDIEN_HEURE")
REBOOT_QUOTIDIEN_TOLERANCE_MIN = int(os.environ.get("REBOOT_QUOTIDIEN_TOLERANCE_MIN", "15"))

def is_reboot_quotidien_attendu(now):
    """True si 'now' tombe dans la fenetre du reboot quotidien connu (donc a ignorer)."""
    if not REBOOT_QUOTIDIEN_HEURE:
        return False
    try:
        heure_prevue = int(REBOOT_QUOTIDIEN_HEURE)
    except ValueError:
        return False
    reboot_prevu = now.replace(hour=heure_prevue, minute=0, second=0, microsecond=0)
    ecart_minutes = abs((now - reboot_prevu).total_seconds()) / 60
    return ecart_minutes <= REBOOT_QUOTIDIEN_TOLERANCE_MIN

STATE_FILENAME = "conan_bot_state.json"
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"
GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

# ============================================================
#  SERVEUR WEB FACTICE
#  Sert uniquement à répondre aux "pings" d'un service externe
#  (UptimeRobot, cron-job.org...). Ce serveur seul ne suffit pas
#  à empêcher la mise en veille : il faut qu'un service externe
#  vienne réellement l'appeler toutes les 5-10 minutes.
# ============================================================

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Le bot fonctionne !")

    def do_HEAD(self):
        # UptimeRobot (plan gratuit) envoie des requetes HEAD, pas GET.
        # Sans cette methode, le serveur renvoie une erreur 501 Not Implemented.
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # evite de polluer les logs Render a chaque ping

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# ============================================================
#  PERSISTANCE DE L'ETAT (message_id, was_online) DANS UN GIST
#  Un Gist GitHub sert de toute petite "memoire" gratuite qui
#  survit aux redemarrages de Render (contrairement a la memoire
#  du script ou a son disque local, qui sont remis a zero).
# ============================================================

def load_state():
    """Lit message_id et was_online depuis le Gist. Renvoie (None, None) si indisponible."""
    try:
        res = requests.get(GIST_API_URL, headers=GITHUB_HEADERS, timeout=10)
        res.raise_for_status()
        content = res.json()["files"][STATE_FILENAME]["content"]
        data = json.loads(content)
        print(f"✅ Etat precedent restaure depuis le Gist : {data}")
        return data.get("message_id"), data.get("was_online")
    except Exception as e:
        print(f"⚠️ Aucun etat precedent trouve dans le Gist (ou erreur de lecture) : {e}")
        return None, None

def save_state(current_message_id, current_was_online):
    """Ecrit message_id et was_online dans le Gist pour qu'ils survivent a un redemarrage."""
    payload = {
        "files": {
            STATE_FILENAME: {
                "content": json.dumps({
                    "message_id": current_message_id,
                    "was_online": current_was_online,
                })
            }
        }
    }
    try:
        res = requests.patch(GIST_API_URL, headers=GITHUB_HEADERS, json=payload, timeout=10)
        if res.status_code != 200:
            print(f"⚠️ Echec de la sauvegarde de l'etat dans le Gist : {res.status_code} {res.text}")
    except Exception as e:
        print(f"⚠️ Erreur reseau lors de la sauvegarde de l'etat : {e}")

# Etat en memoire, restaure depuis le Gist au demarrage du script
message_id, was_online = load_state()

# ============================================================
#  BOUCLE PRINCIPALE
# ============================================================

def check_server():
    global message_id, was_online
    force_repost = False

    # GROS FILET DE SECURITE : empeche le script de mourir quoi qu'il arrive
    try:
        # 1. On recupere les infos du serveur Conan
        try:
            info = a2s.info((SERVER_IP, QUERY_PORT), timeout=6.0)
            current_online = True
            message = (f"🟢 **Le serveur *Blood Lady* est EN LIGNE**\n\n"
                       f"🗺️ **Carte :** {info.map_name}")
            color = 3066993
        except Exception as e:
            print(f"⚠️ Erreur de connexion au serveur Conan : {e}")
            current_online = False
            message = ("🔴 **Le serveur *Blood Lady* est HORS LIGNE !**\n\n"
                       "Le serveur ne repond pas ou est en cours de redemarrage.")
            color = 15158332

        tz_france = timezone(timedelta(hours=2))
        now_france = datetime.now(tz_france)

        # 2. ALERTE DE MISE HORS LIGNE (mise a jour GPortal / maintenance imprevue)
        # On ignore silencieusement si ca tombe dans la fenetre du reboot quotidien connu.
        if was_online is True and current_online is False:
            if not is_reboot_quotidien_attendu(now_france):
                try:
                    requests.post(WEBHOOK_URL, json={
                        "content": "🔄 **Le serveur *Blood Lady* redemarre (mise a jour ou maintenance). "
                                   "Il sera de nouveau operationnel dans un instant.**"
                    })
                except Exception as e:
                    print(f"Erreur lors de l'envoi de l'alerte de mise hors ligne : {e}")

        # 3. ALERTE DE REDEMARRAGE (retour en ligne)
        if was_online is False and current_online is True:
            try:
                alert_payload = {
                    "content": ":white_check_mark: **Le serveur *Blood Lady* Exiles vient de redemarrer ! "
                               "Il est de nouveau accessible. Bon jeu ! 🟢**"
                }
                requests.post(WEBHOOK_URL, json=alert_payload)
                force_repost = True
            except Exception as e:
                print(f"Erreur lors de l'envoi de l'alerte : {e}")

        # On met a jour la memoire d'etat
        was_online = current_online

        # Heure francaise de Paris (UTC+2 en ete) sans aucune bibliotheque externe
        current_time = now_france.strftime('%H:%M:%S')

        payload = {
            "embeds": [{
                "title": "Statut du Serveur",
                "description": message,
                "color": color,
                "footer": {"text": f"Derniere mise a jour : {current_time}"}
            }]
        }

        # 4. GESTION DE L'AFFICHAGE SILENCIEUX
        if force_repost and message_id is not None:
            try:
                requests.delete(f"{WEBHOOK_URL}/messages/{message_id}")
            except:
                pass
            message_id = None

        if message_id is None:
            # Premier lancement (ou reprise apres une alerte de redemarrage)
            res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
            if res.status_code in [200, 201]:
                message_id = res.json().get("id")
            else:
                print(f"❌ Echec Discord POST. Code : {res.status_code}")
        else:
            # Mise a jour silencieuse
            res = requests.patch(f"{WEBHOOK_URL}/messages/{message_id}", json=payload)
            if res.status_code == 404:  # Si le message a ete supprime manuellement
                res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
                if res.status_code in [200, 201]:
                    message_id = res.json().get("id")
            elif res.status_code not in [200, 204]:
                print(f"❌ Echec Discord PATCH. Code : {res.status_code}")

        # 5. SAUVEGARDE DE L'ETAT
        # A chaque cycle, on sauvegarde message_id et was_online dans le Gist.
        # Si Render redemarre le bot juste apres, il retrouvera le bon etat
        # au prochain demarrage au lieu de reposter une carte en double.
        save_state(message_id, was_online)

    except Exception as main_error:
        # Si une erreur improbable survient, on l'affiche sans tuer le bot
        print(f"💥 Erreur critique generale : {main_error}")

# Boucle principale : verifie toutes les 3 minutes
while True:
    check_server()
    time.sleep(90)
