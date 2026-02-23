from flask import Blueprint, redirect, send_from_directory

from config.settings import Settings

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    if not Settings.is_configured():
        return redirect("/setup")
    return send_from_directory("static", "index.html")
