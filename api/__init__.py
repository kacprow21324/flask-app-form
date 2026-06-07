from flask import Blueprint, jsonify
from flask_login import current_user

from api.documents import documents_bp
from api.errors import UnauthorizedError, init_api_errors
from api.internships import internships_bp
from api.students import students_bp
from core.security import csrf_token


api_bp = Blueprint("api", __name__, url_prefix="/api")
api_bp.register_blueprint(students_bp)
api_bp.register_blueprint(internships_bp)
api_bp.register_blueprint(documents_bp)


@api_bp.get("/csrf-token")
def get_csrf_token():
    if not current_user.is_authenticated:
        raise UnauthorizedError("Authentication required.")
    return jsonify({"csrf_token": csrf_token()})


def init_api(app):
    init_api_errors(app)
    app.register_blueprint(api_bp)
