from flask import Blueprint, jsonify, request

from app import models

trades_bp = Blueprint("trades", __name__)


@trades_bp.route("/api/trades")
def get_trades():
    limit = request.args.get("limit", 20, type=int)
    trades = models.get_recent_trades(limit=min(limit, 100))
    return jsonify(trades)


@trades_bp.route("/api/positions")
def get_positions():
    positions = models.get_positions()
    return jsonify(positions)
