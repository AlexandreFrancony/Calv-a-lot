import logging
from flask import Flask

from app.routes import register_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("calvalot")

_poller_started = False


def start_poller():
    """Initialize exchange, budget, follower and start the polling loop.

    Called at startup if already configured, or by the setup wizard
    after config is saved.
    """
    global _poller_started
    if _poller_started:
        return

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

        budget_mgr.initialize()

        follower = Follower(exchange, market, budget_mgr)

        poller._follower = follower
        poller.init_poller(follower)
    except Exception as e:
        logger.error(f"Failed to start poller: {e}")
        _poller_started = False
        raise


def create_app():
    app = Flask(__name__, static_folder="static")

    from app.db import init_db
    init_db()

    register_routes(app)

    from config.settings import Settings
    if Settings.is_configured():
        start_poller()
    else:
        logger.info("Setup required — open the dashboard to configure")

    logger.info("Calv-a-lot started")
    return app
