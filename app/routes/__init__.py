from app.routes.health import health_bp
from app.routes.dashboard import dashboard_bp
from app.routes.budget import budget_bp
from app.routes.trades import trades_bp
from app.routes.signals import signals_bp
from app.routes.agent import agent_bp


def register_routes(app):
    app.register_blueprint(health_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(trades_bp)
    app.register_blueprint(signals_bp)
    app.register_blueprint(agent_bp)
