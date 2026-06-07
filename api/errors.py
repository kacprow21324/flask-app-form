from flask import jsonify, request
from werkzeug.exceptions import HTTPException

from core.models import db


class APIError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.message = message
        self.details = details


class ValidationError(APIError):
    code = "validation_error"


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"


class ConflictError(APIError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(APIError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(APIError):
    status_code = 403
    code = "forbidden"


def _response(message, status_code, code, details=None):
    payload = {"error": message, "code": code}
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


def init_api_errors(app):
    @app.errorhandler(APIError)
    def handle_api_error(error):
        return _response(
            error.message,
            error.status_code,
            error.code,
            error.details,
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if not request.path.startswith("/api"):
            return error
        return _response(
            error.description or error.name,
            error.code or 500,
            error.name.lower().replace(" ", "_"),
        )

    @app.errorhandler(500)
    def handle_internal_error(error):
        if not request.path.startswith("/api"):
            return error
        db.session.rollback()
        return _response(
            "Internal server error.",
            500,
            "internal_server_error",
        )
