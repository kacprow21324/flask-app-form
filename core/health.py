from flask import Blueprint, jsonify
from sqlalchemy import text

from core import store
from core.models import db


health_bp = Blueprint("health", __name__)


@health_bp.get("/health/live")
def live():
    return jsonify(status="ok")


@health_bp.get("/health/ready")
def ready():
    checks = {"mariadb": "ok", "mongodb": "ok"}
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        checks["mariadb"] = "error"
    try:
        store.ping()
    except Exception:
        checks["mongodb"] = "error"

    is_ready = all(value == "ok" for value in checks.values())
    return jsonify(
        status="ok" if is_ready else "error",
        checks=checks,
    ), 200 if is_ready else 503
