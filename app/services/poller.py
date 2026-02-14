"""Poller qui interroge Cash-a-lot pour récupérer les signaux.

Thread en arrière-plan qui poll l'endpoint /api/signal/latest
toutes les POLL_INTERVAL_SECONDS secondes.
"""

import hashlib
import hmac
import logging
import threading
import time

import requests

from config.settings import Settings
from app import models

logger = logging.getLogger("calvalot.poller")

_poller_thread = None
_running = False
_paused = False
_last_poll_result = None
_last_poll_time = None
_follower = None  # Référence au Follower, injectée par __init__.py
_poll_count = 0   # Compteur pour les tâches périodiques (cleanup, etc.)
_last_new_signal_time = None  # Timestamp du dernier signal nouveau reçu
_NO_SIGNAL_ALERT_SECONDS = 7200  # 2 heures sans signal = alerte


def init_poller(follower_service):
    """Démarre le thread de polling."""
    global _poller_thread, _running

    if _poller_thread and _poller_thread.is_alive():
        logger.warning("Poller déjà démarré")
        return

    _running = True
    _poller_thread = threading.Thread(
        target=_poll_loop,
        args=(follower_service,),
        daemon=True,
        name="calvalot-poller",
    )
    _poller_thread.start()
    logger.info(f"Poller démarré: interval {Settings.POLL_INTERVAL_SECONDS}s "
                f"→ {Settings.LEADER_URL}")


def _poll_loop(follower_service):
    """Boucle principale du poller."""
    global _last_poll_result, _last_poll_time

    # Premier poll immédiat
    _do_poll(follower_service)

    while _running:
        time.sleep(Settings.POLL_INTERVAL_SECONDS)

        if not _running:
            break

        if _paused:
            continue

        _do_poll(follower_service)


def _do_poll(follower_service):
    """Un cycle de polling."""
    global _last_poll_result, _last_poll_time, _poll_count, _last_new_signal_time

    _last_poll_time = time.time()
    _poll_count += 1

    # Tâches périodiques
    # 1. Nettoyage des vieux snapshots (toutes les 720 itérations ≈ 1x/jour à 120s)
    if _poll_count % 720 == 0:
        try:
            models.cleanup_old_snapshots()
            logger.info("Nettoyage périodique des snapshots effectué")
        except Exception as e:
            logger.warning(f"Erreur nettoyage snapshots: {e}")

    # 2. Alerte si pas de nouveau signal depuis 2h
    if _last_new_signal_time:
        silence = time.time() - _last_new_signal_time
        if silence > _NO_SIGNAL_ALERT_SECONDS:
            try:
                from app.services.notifier import alert_no_signal
                alert_no_signal(silence / 3600)
            except Exception as e:
                logger.warning(f"Erreur alerte no_signal: {e}")

    try:
        signal = _fetch_signal()

        if signal is None:
            _last_poll_result = {"status": "no_signal"}
            return

        signal_id = signal.get("signal_id")
        if not signal_id:
            _last_poll_result = {"status": "invalid_signal"}
            return

        # Vérifier si ce signal a déjà été traité (déduplication)
        if models.signal_exists(signal_id):
            _last_poll_result = {"status": "already_processed", "signal_id": signal_id}
            return

        _last_new_signal_time = time.time()
        logger.info(f"Nouveau signal reçu: {signal_id}")

        # Reset l'alerte no_signal si on en reçoit un
        try:
            from app.services.notifier import reset_alert
            reset_alert("no_signal")
        except ImportError:
            pass

        # Enregistrer le signal
        models.insert_signal(
            signal_id=signal_id,
            confidence=signal.get("confidence", 0),
            reasoning=signal.get("reasoning", ""),
            actions=signal.get("actions", []),
            portfolio_state=signal.get("portfolio_state"),
        )

        # Exécuter le signal (avec timeout pour éviter de bloquer le poller)
        result = _execute_with_timeout(follower_service, signal, timeout=90)
        _last_poll_result = {
            "status": "executed",
            "signal_id": signal_id,
            "trades": result.get("trades_executed", 0),
        }

    except Exception as e:
        logger.exception(f"Erreur polling: {e}")
        _last_poll_result = {"status": "error", "error": "Erreur de polling"}


def _execute_with_timeout(follower_service, signal, timeout=90):
    """Exécute execute_signal dans un thread avec timeout.

    Si l'exécution dépasse le timeout, on log un warning et on retourne
    un résultat vide. Le thread d'exécution continue en arrière-plan
    (Python ne permet pas de tuer un thread), mais le poller peut reprendre.
    """
    result_holder = [None]
    error_holder = [None]

    def _run():
        try:
            result_holder[0] = follower_service.execute_signal(signal)
        except Exception as e:
            error_holder[0] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        signal_id = signal.get("signal_id", "unknown")
        logger.error(f"execute_signal TIMEOUT ({timeout}s) pour signal {signal_id}")
        return {"status": "timeout", "trades_executed": 0}

    if error_holder[0]:
        raise error_holder[0]

    return result_holder[0] or {"status": "error", "trades_executed": 0}


def _fetch_signal():
    """Récupère le dernier signal depuis Cash-a-lot avec auth HMAC."""
    url = f"{Settings.LEADER_URL.rstrip('/')}/api/signal/latest"

    # Signature HMAC
    timestamp = str(int(time.time()))
    signature = hmac.new(
        Settings.SIGNAL_SECRET.encode(),
        timestamp.encode(),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "X-Signal-Timestamp": timestamp,
        "X-Signal-Signature": signature,
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 204:
            # Pas de signal disponible (Cash-a-lot vient de démarrer)
            return None
        if resp.status_code == 403:
            logger.warning("Auth HMAC rejetée par le leader")
            return None
        if resp.status_code == 404:
            logger.warning("Endpoint signal désactivé sur le leader")
            return None

        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.ConnectionError:
        logger.warning(f"Leader injoignable: {Settings.LEADER_URL}")
        return None
    except requests.exceptions.Timeout:
        logger.warning("Timeout lors du polling du leader")
        return None
    except Exception as e:
        logger.error(f"Erreur fetch signal: {e}")
        return None


def get_status():
    """Status du poller pour le dashboard."""
    return {
        "running": _running and not _paused,
        "paused": _paused,
        "poll_interval_seconds": Settings.POLL_INTERVAL_SECONDS,
        "leader_url": "***" if Settings.LEADER_URL else None,
        "last_poll": _last_poll_result,
        "last_poll_time": _last_poll_time,
    }


def pause():
    """Met le poller en pause."""
    global _paused
    _paused = True
    logger.info("Poller en pause")


def resume():
    """Reprend le poller."""
    global _paused
    _paused = False
    logger.info("Poller repris")


def is_paused():
    return _paused


def stop():
    """Arrête le poller (pour shutdown propre)."""
    global _running
    _running = False
    logger.info("Poller arrêté")
