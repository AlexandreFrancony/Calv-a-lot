"""Setup wizard routes for first-time configuration.

Serves the setup page and handles config validation/saving.
When config is saved, starts the poller automatically.
"""

import hashlib
import hmac
import logging
import time

import requests
from flask import Blueprint, jsonify, request, send_from_directory

from config.settings import Settings, save_config

logger = logging.getLogger("calvalot.setup")

setup_bp = Blueprint("setup", __name__)


@setup_bp.route("/setup")
def setup_page():
    """Serve the setup wizard HTML page."""
    if Settings.is_configured():
        from flask import redirect
        return redirect("/")
    return send_from_directory("static", "setup.html")


@setup_bp.route("/api/setup/status")
def setup_status():
    """Check if the app is configured."""
    return jsonify({"configured": Settings.is_configured()})


@setup_bp.route("/api/setup/validate", methods=["POST"])
def validate_config():
    """Validate leader connectivity and Binance API keys.

    Expects JSON body with: leader_url, signal_secret,
    binance_api_key, binance_api_secret, binance_testnet
    """
    data = request.get_json() or {}
    errors = []

    leader_ok = False
    binance_ok = False
    binance_balance_usdc = None

    # Validate leader connectivity
    leader_url = data.get("leader_url", "").strip().rstrip("/")
    signal_secret = data.get("signal_secret", "").strip()

    if leader_url and signal_secret:
        try:
            # Test with HMAC auth (same as poller)
            ts = str(int(time.time()))
            sig = hmac.new(
                signal_secret.encode(), ts.encode(), hashlib.sha256
            ).hexdigest()
            resp = requests.get(
                f"{leader_url}/api/signal/latest",
                headers={
                    "X-Signal-Timestamp": ts,
                    "X-Signal-Signature": sig,
                },
                timeout=10,
            )
            # 200 = signal available, 204 = no signal yet — both are OK
            if resp.status_code in (200, 204):
                leader_ok = True
            elif resp.status_code == 403:
                errors.append("Secret incorrect — le leader a rejeté l'authentification")
            else:
                errors.append(f"Leader a répondu avec le code {resp.status_code}")
        except requests.exceptions.ConnectionError:
            errors.append("Impossible de contacter le leader — vérifie l'URL")
        except requests.exceptions.Timeout:
            errors.append("Le leader ne répond pas (timeout)")
        except Exception as e:
            errors.append(f"Erreur de connexion au leader : {e}")
    elif leader_url or signal_secret:
        errors.append("L'URL du leader et le secret sont tous les deux requis")

    # Validate Binance API keys
    api_key = data.get("binance_api_key", "").strip()
    api_secret = data.get("binance_api_secret", "").strip()
    testnet = data.get("binance_testnet", False)

    if api_key and api_secret:
        try:
            from binance.client import Client
            from binance.exceptions import BinanceAPIException

            client = Client(
                api_key, api_secret,
                testnet=testnet,
                requests_params={"timeout": 10},
            )
            account = client.get_account()
            binance_ok = True

            # Extract USDC balance
            for balance in account.get("balances", []):
                if balance["asset"] == "USDC":
                    binance_balance_usdc = float(balance["free"])
                    break
        except BinanceAPIException as e:
            if e.code == -2015:
                errors.append("Clés API Binance invalides — vérifie la clé et le secret")
            else:
                errors.append(f"Erreur Binance : {e.message}")
        except Exception as e:
            errors.append(f"Erreur de connexion à Binance : {e}")
    elif api_key or api_secret:
        errors.append("La clé API et le secret Binance sont tous les deux requis")

    return jsonify({
        "leader_ok": leader_ok,
        "binance_ok": binance_ok,
        "binance_balance_usdc": binance_balance_usdc,
        "errors": errors,
    })


@setup_bp.route("/api/setup/save", methods=["POST"])
def save_setup():
    """Save configuration and start the poller.

    Expects JSON body with all config values.
    """
    data = request.get_json() or {}

    required = ["leader_url", "signal_secret", "binance_api_key", "binance_api_secret"]
    missing = [k for k in required if not data.get(k, "").strip()]
    if missing:
        return jsonify({"success": False, "error": f"Champs manquants : {', '.join(missing)}"}), 400

    # Build config dict (keys match env var names for _get() compatibility)
    config = {
        "LEADER_URL": data["leader_url"].strip().rstrip("/"),
        "SIGNAL_SECRET": data["signal_secret"].strip(),
        "BINANCE_API_KEY": data["binance_api_key"].strip(),
        "BINANCE_API_SECRET": data["binance_api_secret"].strip(),
        "BINANCE_TESTNET": str(data.get("binance_testnet", False)).lower(),
        "TRADING_MODE": data.get("trading_mode", "dry_run"),
        "INITIAL_BUDGET_EUR": str(data.get("initial_budget_eur", 100)),
    }

    try:
        save_config(config)
        Settings.reload()

        # Start the poller now that config is ready
        from app import start_poller
        start_poller()

        logger.info("Setup complete — poller started")
        return jsonify({"success": True})
    except Exception as e:
        logger.exception(f"Setup failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
