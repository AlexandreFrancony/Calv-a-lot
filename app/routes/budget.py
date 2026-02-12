from flask import Blueprint, jsonify, request

from app import models

budget_bp = Blueprint("budget", __name__)


@budget_bp.route("/api/budget")
def get_budget():
    from app.services.poller import _follower
    mgr = _follower.budget_mgr if _follower else None

    if not mgr:
        return jsonify({"status": "UNINITIALIZED"})

    status = mgr.get_status()

    if status.get("status") == "UNINITIALIZED":
        return jsonify(status)

    # Ajouter cash et total value
    follower = _follower
    if follower:
        try:
            cash_usdt = float(follower._get_cash_balance())
            prices = follower.market.get_prices()
            positions = models.get_positions()
            portfolio_usdt = float(follower._calc_portfolio_value(positions, prices))
            total_usdt = cash_usdt + portfolio_usdt
            eur_rate = float(follower.market.get_eurusdc_rate())
            status["cash_usdt"] = cash_usdt
            status["portfolio_usdt"] = portfolio_usdt
            status["total_value_usdt"] = total_usdt
            status["total_value_eur"] = total_usdt * eur_rate
            status["eurusdc_rate"] = eur_rate
        except Exception:
            pass

    return jsonify(status)


@budget_bp.route("/api/budget/history")
def get_budget_history():
    limit = request.args.get("limit", 5000, type=int)
    limit = min(limit, 5000)
    period_map = {"1d": 24, "1w": 168, "1m": 720, "1y": 8760}
    period = request.args.get("period")
    hours = period_map.get(period)
    snapshots = models.get_snapshots(limit=limit, hours=hours)
    return jsonify(snapshots)


@budget_bp.route("/api/budget/deposit", methods=["POST"])
def add_deposit():
    """Enregistrer un dépôt manuel."""
    data = request.get_json()
    if not data or "amount_eur" not in data:
        return jsonify({"error": "amount_eur required"}), 400

    try:
        amount_eur = float(data["amount_eur"])
    except (ValueError, TypeError):
        return jsonify({"error": "invalid amount"}), 400

    if amount_eur <= 0 or amount_eur > 100000:
        return jsonify({"error": "amount out of range"}), 400

    budget = models.get_budget()
    if not budget:
        return jsonify({"error": "budget not initialized"}), 400

    current = budget.get("total_deposited_eur") or budget["initial_total_eur"]
    new_total = current + amount_eur
    models.update_budget_deposited(budget["id"], new_total)

    return jsonify({"ok": True, "total_deposited_eur": new_total})


@budget_bp.route("/api/budget/deposit", methods=["PUT"])
def set_deposit():
    """Corriger manuellement le total déposé."""
    data = request.get_json()
    if not data or "total_eur" not in data:
        return jsonify({"error": "total_eur required"}), 400

    try:
        total_eur = float(data["total_eur"])
    except (ValueError, TypeError):
        return jsonify({"error": "invalid amount"}), 400

    budget = models.get_budget()
    if not budget:
        return jsonify({"error": "budget not initialized"}), 400

    models.update_budget_deposited(budget["id"], total_eur)
    return jsonify({"ok": True, "total_deposited_eur": total_eur})


@budget_bp.route("/api/budget/withdrawals")
def get_withdrawals():
    """Historique des retraits."""
    limit = request.args.get("limit", 50, type=int)
    withdrawals = models.get_withdrawals(limit=min(limit, 200))
    total_eur = sum(w.get("amount_eur_received", 0) or 0 for w in withdrawals)
    total_usdt = models.get_total_withdrawals()
    return jsonify({
        "withdrawals": withdrawals,
        "total_usdt": total_usdt,
        "total_eur": total_eur,
    })
