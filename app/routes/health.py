import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    from config.settings import Settings

    # Vérifier que le poller a tourné récemment
    poller_ok = True
    poller_msg = "unknown"
    try:
        from app.services.poller import get_status
        status = get_status()
        last_time = status.get("last_poll_time")
        if last_time:
            age = time.time() - last_time
            max_age = Settings.POLL_INTERVAL_SECONDS * 2  # 2x l'intervalle
            poller_ok = age < max_age
            poller_msg = f"last_poll_{int(age)}s_ago"
        else:
            poller_msg = "no_poll_yet"
    except (ImportError, AttributeError):
        poller_msg = "not_tracked"

    ok = "ok" if poller_ok else "degraded"

    return jsonify({
        "status": ok,
        "service": "calvalot",
        "poller": poller_msg,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200 if poller_ok else 503
