import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Zmienna środowiskowa {name!r} nie jest ustawiona. "
            "Uzupełnij plik .env (patrz .env.example)."
        )
    return value


def _secret_key() -> str:
    value = _require("SECRET_KEY")
    if len(value) < 32:
        raise RuntimeError("SECRET_KEY musi mieć co najmniej 32 znaki.")
    return value


class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = _require("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    DEBUG_LOGIN_BUTTONS = (
        DEBUG
        and os.environ.get("DEBUG_LOGIN_BUTTONS", "false").lower() == "true"
    )
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE", "false",
    ).lower() == "true"
    TRUST_PROXY_HEADERS = os.environ.get(
        "TRUST_PROXY_HEADERS", "false",
    ).lower() == "true"
    ENABLE_HSTS = os.environ.get(
        "ENABLE_HSTS", "false",
    ).lower() == "true"
    JSON_LOGS = os.environ.get("JSON_LOGS", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
    MS_CLIENT_ID = os.environ.get("MS_CLIENT_ID", "")
    MS_CLIENT_SECRET = os.environ.get("MS_CLIENT_SECRET", "")
    MS_TENANT_ID = os.environ.get("MS_TENANT_ID", "common")
    MS_REDIRECT_URI = os.environ.get("MS_REDIRECT_URI", "")
    MS_STAFF_EMAIL_DOMAIN = os.environ.get(
        "MS_STAFF_EMAIL_DOMAIN", "ans-elblag.pl",
    ).strip().lower()
    MS_ALLOWED_EMAIL_DOMAINS = tuple(
        domain.strip().lower()
        for domain in os.environ.get("MS_ALLOWED_EMAIL_DOMAINS", "").split(",")
        if domain.strip()
    )
    ZOPZ_INVITATION_LIFETIME = timedelta(
        hours=int(os.environ.get("ZOPZ_INVITATION_HOURS", "168")),
    )
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "praktyki@ans-elblag.pl")
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
