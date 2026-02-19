from flask import Blueprint, jsonify

agent_bp = Blueprint("agent", __name__)


@agent_bp.route("/api/agent/status")
def agent_status():
    from app.services import poller
    status = poller.get_status()
    return jsonify(status)


@agent_bp.route("/api/agent/toggle", methods=["POST"])
def toggle_agent():
    from app.services import poller
    if poller.is_paused():
        poller.resume()
        return jsonify({"status": "resumed"})
    else:
        poller.pause()
        return jsonify({"status": "paused"})
