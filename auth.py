from datetime import datetime
from typing import Optional

from flask import Blueprint, flash, redirect, url_for
from flask_login import LoginManager, login_required, logout_user
from werkzeug.security import check_password_hash

from models import User, db


class AuthError(Exception):
    """Błąd logowania – bezpieczny do pokazania użytkownikowi."""


def authenticate_user(email: str, password: str) -> User:
    """
    Weryfikuje email i hasło względem bazy danych.
    Rzuca AuthError przy złych danych lub nieaktywnym koncie.
    """
    user = User.query.filter_by(email=email.lower().strip()).first()

    if user is None or not check_password_hash(user.password_hash, password):
        raise AuthError("Nieprawidłowy email lub hasło.")

    if not user.is_active:
        raise AuthError(
            "Twoje konto oczekuje na aktywację przez administratora systemu."
        )

    user.last_login_at = datetime.utcnow()
    db.session.commit()
    return user


# ── Flask-Login ────────────────────────────────────────────────────────────────

login_manager = LoginManager()
login_manager.login_view = "login_page"  # type: ignore[assignment]
login_manager.login_message = "Zaloguj się, aby uzyskać dostęp do systemu."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    return db.session.get(User, int(user_id))


# ── Blueprint ──────────────────────────────────────────────────────────────────

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Zostałeś wylogowany.", "info")
    return redirect(url_for("login_page"))
