import json
import os

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/data/config.json")


def _load_config():
    """Load config from JSON file if it exists."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _get(key, default=None):
    """Get setting from env var first, then config.json, then default."""
    val = os.environ.get(key)
    if val:
        return val
    return _load_config().get(key, default)


def save_config(data):
    """Save config to JSON file (called by setup wizard)."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


class Settings:
    # Leader (Cash-a-lot)
    LEADER_URL = _get("LEADER_URL", "")
    SIGNAL_SECRET = _get("SIGNAL_SECRET", "")

    # Binance
    BINANCE_API_KEY = _get("BINANCE_API_KEY", "")
    BINANCE_API_SECRET = _get("BINANCE_API_SECRET", "")
    BINANCE_TESTNET = (_get("BINANCE_TESTNET", "false") or "false").lower() == "true"

    # Budget
    INITIAL_BUDGET_EUR = float(_get("INITIAL_BUDGET_EUR", "100"))

    # Trading
    TRADING_MODE = _get("TRADING_MODE", "dry_run")  # dry_run | live
    POLL_INTERVAL_SECONDS = int(_get("POLL_INTERVAL_SECONDS", "120"))

    # Sécurité trading
    MIN_ORDER_USDC = 5.0       # Minimum Binance (5 USDC)
    MIN_BUDGET_EUR = 5.0       # Agent meurt en-dessous
    REBALANCE_THRESHOLD_PCT = float(_get("REBALANCE_THRESHOLD_PCT", "0.005"))  # 0.5%

    # Email alerts (optionnel)
    SMTP_HOST = _get("SMTP_HOST", "ssl0.ovh.net")
    SMTP_PORT = int(_get("SMTP_PORT", "465"))
    SMTP_USER = _get("SMTP_USER")
    SMTP_PASSWORD = _get("SMTP_PASSWORD")
    ALERT_EMAIL_TO = _get("ALERT_EMAIL_TO")

    # Database SQLite
    DB_PATH = _get("DB_PATH", "/app/data/calvalot.db")

    # Version (git commit hash, baké dans l'image Docker au build)
    VERSION = os.environ.get("GIT_COMMIT", "unknown")

    # Server
    PORT = int(_get("PORT", "8080"))

    # API auth (optionnel)
    API_USER = _get("API_USER", "admin")
    API_PASSWORD_HASH = _get("API_PASSWORD_HASH", "")

    @classmethod
    def is_configured(cls):
        """True if all required config is set."""
        return all([cls.LEADER_URL, cls.SIGNAL_SECRET,
                    cls.BINANCE_API_KEY, cls.BINANCE_API_SECRET])

    @classmethod
    def reload(cls):
        """Reload config from config.json (after setup wizard)."""
        cls.LEADER_URL = _get("LEADER_URL", "")
        cls.SIGNAL_SECRET = _get("SIGNAL_SECRET", "")
        cls.BINANCE_API_KEY = _get("BINANCE_API_KEY", "")
        cls.BINANCE_API_SECRET = _get("BINANCE_API_SECRET", "")
        cls.BINANCE_TESTNET = (_get("BINANCE_TESTNET", "false") or "false").lower() == "true"
        cls.INITIAL_BUDGET_EUR = float(_get("INITIAL_BUDGET_EUR", "100"))
        cls.TRADING_MODE = _get("TRADING_MODE", "dry_run")
        cls.POLL_INTERVAL_SECONDS = int(_get("POLL_INTERVAL_SECONDS", "120"))
        cls.SMTP_HOST = _get("SMTP_HOST", "ssl0.ovh.net")
        cls.SMTP_PORT = int(_get("SMTP_PORT", "465"))
        cls.SMTP_USER = _get("SMTP_USER")
        cls.SMTP_PASSWORD = _get("SMTP_PASSWORD")
        cls.ALERT_EMAIL_TO = _get("ALERT_EMAIL_TO")
        cls.API_USER = _get("API_USER", "admin")
        cls.API_PASSWORD_HASH = _get("API_PASSWORD_HASH", "")
