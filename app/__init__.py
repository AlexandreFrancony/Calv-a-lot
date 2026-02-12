import logging
from flask import Flask

from app.routes import register_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("calvalot")

_poller_started = False


def create_app():
    app = Flask(__name__, static_folder="static")

    # Initialiser la base de données SQLite
    from app.db import init_db
    init_db()

    register_routes(app)

    # Démarrer le poller une seule fois (gunicorn preload_app=False)
    global _poller_started
    if not _poller_started:
        _poller_started = True
        try:
            from app.services.exchange import ExchangeClient
            from app.services.market_data import MarketData
            from app.services.budget_manager import BudgetManager
            from app.services.follower import Follower
            from app.services import poller

            exchange = ExchangeClient()
            market = MarketData(exchange)
            budget_mgr = BudgetManager()

            # Initialiser le budget
            budget_mgr.initialize()

            follower = Follower(exchange, market, budget_mgr)

            # Rendre le follower accessible aux routes
            poller._follower = follower

            # Démarrer le poller
            poller.init_poller(follower)
        except Exception as e:
            logger.error(f"Failed to start poller: {e}")

    logger.info("Calv-a-lot started")
    return app
