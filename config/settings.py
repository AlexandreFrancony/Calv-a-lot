import os


class Settings:
    # Leader (Cash-a-lot)
    LEADER_URL = os.environ["LEADER_URL"]  # ex: https://crypto.francony.fr
    SIGNAL_SECRET = os.environ["SIGNAL_SECRET"]

    # Binance
    BINANCE_API_KEY = os.environ["BINANCE_API_KEY"]
    BINANCE_API_SECRET = os.environ["BINANCE_API_SECRET"]
    BINANCE_TESTNET = os.environ.get("BINANCE_TESTNET", "true").lower() == "true"

    # Budget
    INITIAL_BUDGET_EUR = float(os.environ.get("INITIAL_BUDGET_EUR", "100"))

    # Trading
    TRADING_MODE = os.environ.get("TRADING_MODE", "dry_run")  # dry_run | live
    POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "120"))

    # Sécurité trading
    MIN_ORDER_USDC = 5.0       # Minimum Binance (5 USDC)
    MIN_BUDGET_EUR = 5.0       # Agent meurt en-dessous
    REBALANCE_THRESHOLD_PCT = float(os.environ.get("REBALANCE_THRESHOLD_PCT", "0.005"))  # 0.5%

    # Email alerts (optionnel)
    SMTP_HOST = os.environ.get("SMTP_HOST", "ssl0.ovh.net")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO")

    # Database SQLite
    DB_PATH = os.environ.get("DB_PATH", "/app/data/calvalot.db")

    # Version (git commit hash, baké dans l'image Docker au build)
    VERSION = os.environ.get("GIT_COMMIT", "unknown")

    # Server
    PORT = int(os.environ.get("PORT", "8080"))
