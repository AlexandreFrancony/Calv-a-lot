from flask import Blueprint, jsonify, request

from app import models
from app.auth import auth

signals_bp = Blueprint("signals", __name__)


@signals_bp.route("/api/signals")
@auth.login_required
def get_signals():
    """Historique des signaux reçus de Cash-a-lot."""
    limit = request.args.get("limit", 20, type=int)
    signals = models.get_recent_signals(limit=min(limit, 100))
    return jsonify(signals)
