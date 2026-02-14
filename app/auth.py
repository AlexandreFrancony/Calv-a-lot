"""Authentification HTTP Basic pour les endpoints sensibles.

Defense-in-depth : Calv-a-lot est déployé chez des amis,
souvent exposé directement sur le réseau (pas de nginx).
"""

import logging

from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash

from config.settings import Settings

logger = logging.getLogger("calvalot.auth")
auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username, password):
    if not Settings.API_PASSWORD_HASH:
        # Si pas de hash configuré, auth désactivée (backward compat)
        return True
    if username == Settings.API_USER:
        return check_password_hash(Settings.API_PASSWORD_HASH, password)
    return False


@auth.error_handler
def auth_error(status):
    logger.warning("Tentative d'accès non autorisée")
    return {"error": "Unauthorized"}, 401
