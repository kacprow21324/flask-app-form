import secrets
from hmac import compare_digest

from flask import abort, request, session


_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def init_security(app):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def validate_csrf():
        if request.method not in _UNSAFE_METHODS:
            return None
        expected = session.get("_csrf_token")
        supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
        if not expected or not supplied or not compare_digest(expected, supplied):
            abort(400, description="Nieprawidłowy lub wygasły token CSRF.")
        return None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "base-uri 'self'; frame-ancestors 'none'; object-src 'none'",
        )
        if app.config.get("ENABLE_HSTS") and request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-store")
        return response
