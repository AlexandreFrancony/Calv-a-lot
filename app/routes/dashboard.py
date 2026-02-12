from flask import Blueprint, send_from_directory

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    return send_from_directory("static", "index.html")
