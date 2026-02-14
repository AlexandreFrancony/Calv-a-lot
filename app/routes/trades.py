from flask import Blueprint, jsonify, request

from app import models
from app.auth import auth

trades_bp = Blueprint("trades", __name__)


@trades_bp.route("/api/trades")
@auth.login_required
def get_trades():
    limit = request.args.get("limit", 20, type=int)
    trades = models.get_recent_trades(limit=min(limit, 100))
    return jsonify(trades)


@trades_bp.route("/api/positions")
@auth.login_required
def get_positions():
    positions = models.get_positions()
    return jsonify(positions)


@trades_bp.route("/api/prices")
@auth.login_required
def get_prices():
    """Prix courants pour le dashboard (positions P&L)."""
    from app.services.poller import _follower
    if not _follower:
        return jsonify({})
    try:
        prices = _follower.market.get_prices()
        # Convertir Decimal → float pour JSON
        return jsonify({k: float(v) for k, v in prices.items()})
    except Exception:
        return jsonify({})
