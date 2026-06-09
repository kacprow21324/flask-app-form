import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    session, url_for,
)
from flask_login import (
    LoginManager, current_user, login_required, login_user, logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

from core.audit import log_action
from core.models import LoginAttempt, User, UserSession, db
from core.zopz_invitations import (
    InvitationError,
    accept_zopz_invitation,
    get_active_invitation,
)


_DUMMY_PASSWORD_HASH = generate_password_hash("invalid-login-placeholder")
oauth = OAuth()
_MICROSOFT_APP_ROLES = {
    "uopz": "uopz",
    "dziekanat": "dziekanat",
    "admin": "admin",
}
_MICROSOFT_MANAGED_ROLES = frozenset(_MICROSOFT_APP_ROLES.values())

_DEBUG_ACCOUNTS = {
    "student": ("Student", "student@student.ans-elblag.pl", "SEED_STUDENT_PASSWORD"),
    "student2": ("Student 2", "student2@student.ans-elblag.pl", "SEED_STUDENT_PASSWORD"),
    "student3": ("Student 3", "student3@student.ans-elblag.pl", "SEED_STUDENT_PASSWORD"),
    "student4": ("Student 4 (kompletny)", "student4@student.ans-elblag.pl", "SEED_STUDENT4_PASSWORD"),
    "uopz": ("UOPZ", "opiekun@ans-elblag.pl", "SEED_UOPZ_PASSWORD"),
    "zopz": ("ZOPZ", "zopz@firma.pl", "SEED_ZOPZ_PASSWORD"),
    "dziekanat": (
        "Dziekanat", "dziekanat@ans-elblag.pl", "SEED_DZIEKANAT_PASSWORD",
    ),
    "admin": ("Admin", "admin@ans-elblag.pl", "SEED_ADMIN_PASSWORD"),
}


class AuthError(Exception):
    """Błąd logowania – bezpieczny do pokazania użytkownikowi."""


def init_oauth(app):
    oauth.init_app(app)
    if app.config["MS_CLIENT_ID"] and app.config["MS_CLIENT_SECRET"]:
        tenant = app.config["MS_TENANT_ID"] or "common"
        oauth.register(
            name="microsoft",
            client_id=app.config["MS_CLIENT_ID"],
            client_secret=app.config["MS_CLIENT_SECRET"],
            server_metadata_url=(
                f"https://login.microsoftonline.com/{tenant}/v2.0/"
                ".well-known/openid-configuration"
            ),
            client_kwargs={"scope": "openid email profile"},
        )


def oauth_provider_status():
    return {
        "microsoft": bool(
            current_app.config["MS_CLIENT_ID"]
            and current_app.config["MS_CLIENT_SECRET"]
        ),
    }


def get_debug_login_accounts():
    if not current_app.config.get("DEBUG_LOGIN_BUTTONS"):
        return []
    return [
        {"key": key, "label": label}
        for key, (label, _email, env_name) in _DEBUG_ACCOUNTS.items()
        if os.environ.get(env_name)
    ]


def authenticate_user(email: str, password: str) -> User:
    """
    Weryfikuje email i hasło względem bazy danych.
    Rzuca AuthError przy złych danych lub nieaktywnym koncie.
    """
    normalized_email = email.lower().strip()[:255]
    password = password[:1024]
    user = User.query.filter_by(email=normalized_email).first()
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = check_password_hash(password_hash, password)

    if user is not None and user.locked_until and user.locked_until > datetime.utcnow():
        db.session.add(LoginAttempt(
            email=normalized_email,
            ip_address=request.remote_addr,
            success=0,
            failure_reason="locked",
        ))
        db.session.commit()
        raise AuthError("Zbyt wiele prób logowania. Spróbuj ponownie później.")

    if user is None or not password_ok:
        db.session.add(LoginAttempt(
            email=normalized_email or "[empty]",
            ip_address=request.remote_addr,
            success=0,
            failure_reason="unknown_user" if user is None else "wrong_password",
        ))
        if user is not None:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.session.commit()
        raise AuthError("Nieprawidłowy email lub hasło.")

    if not user.is_active:
        db.session.add(LoginAttempt(
            email=normalized_email,
            ip_address=request.remote_addr,
            success=0,
            failure_reason="inactive",
        ))
        db.session.commit()
        raise AuthError(
            "Twoje konto oczekuje na aktywację przez administratora systemu."
        )

    user.last_login_at = datetime.utcnow()
    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.add(LoginAttempt(
        email=normalized_email,
        ip_address=request.remote_addr,
        success=1,
    ))
    db.session.commit()
    return user


def start_user_session(user: User) -> None:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    db.session.add(UserSession(
        user_id=user.id,
        token_hash=token_hash,
        ip_address=request.remote_addr,
        user_agent=(request.user_agent.string or "")[:500],
        expires_at=datetime.utcnow() + timedelta(hours=12),
    ))
    log_action("login", "session", user=user)
    db.session.commit()
    session["_db_session_token"] = raw_token
    session.permanent = True


def revoke_user_session() -> None:
    raw_token = session.pop("_db_session_token", None)
    if raw_token:
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        db_session = UserSession.query.filter_by(token_hash=token_hash).first()
        if db_session and not db_session.is_revoked:
            db_session.is_revoked = 1
            db_session.revoked_at = datetime.utcnow()
    log_action("logout", "session", user=current_user)
    db.session.commit()


# ── Flask-Login ────────────────────────────────────────────────────────────────

login_manager = LoginManager()
login_manager.login_view = "login_page"  # type: ignore[assignment]
login_manager.login_message = None
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    raw_token = session.get("_db_session_token")
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    db_session = UserSession.query.filter_by(
        user_id=int(user_id), token_hash=token_hash, is_revoked=0,
    ).first()
    if db_session is None or db_session.expires_at <= datetime.utcnow():
        if db_session is not None and not db_session.is_revoked:
            db_session.is_revoked = 1
            db_session.revoked_at = datetime.utcnow()
            db.session.commit()
        session.pop("_db_session_token", None)
        return None
    user = db.session.get(User, int(user_id))
    return user if user is not None and user.is_active else None


# ── Blueprint ──────────────────────────────────────────────────────────────────

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _oauth_redirect_uri(config_key, endpoint):
    return current_app.config.get(config_key) or url_for(endpoint, _external=True)


def _microsoft_app_role(userinfo):
    raw_roles = userinfo.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    mapped_roles = {
        _MICROSOFT_APP_ROLES[role.strip().lower()]
        for role in raw_roles
        if isinstance(role, str)
        and role.strip().lower() in _MICROSOFT_APP_ROLES
    }
    if len(mapped_roles) > 1:
        raise AuthError(
            "Konto ma przypisanych kilka sprzecznych ról aplikacji Microsoft."
        )
    return next(iter(mapped_roles), None)


def _microsoft_user_names(userinfo, email):
    first_name = (userinfo.get("given_name") or "").strip()
    last_name = (userinfo.get("family_name") or "").strip()
    display_name = (userinfo.get("name") or "").strip()
    if (not first_name or not last_name) and display_name:
        parts = display_name.split(maxsplit=1)
        first_name = first_name or parts[0]
        last_name = last_name or (parts[1] if len(parts) > 1 else parts[0])
    fallback = email.split("@", 1)[0]
    return first_name or fallback, last_name or fallback


def resolve_microsoft_user(userinfo):
    tenant_id = (current_app.config.get("MS_TENANT_ID") or "").strip()
    if tenant_id.lower() in {"", "common", "organizations", "consumers"}:
        raise AuthError(
            "Logowanie uczelniane wymaga skonfigurowanego tenant-a Microsoft."
        )

    claim_tenant = (userinfo.get("tid") or "").strip()
    object_id = (userinfo.get("oid") or "").strip()
    issuer = (userinfo.get("iss") or "").rstrip("/")
    expected_issuer = (
        f"https://login.microsoftonline.com/{tenant_id}/v2.0"
    ).rstrip("/")
    if claim_tenant.lower() != tenant_id.lower() or issuer.lower() != (
        expected_issuer.lower()
    ):
        raise AuthError("Konto nie należy do tenant-a uczelni.")
    if not object_id:
        raise AuthError("Microsoft nie zwrócił identyfikatora konta.")

    email = (
        userinfo.get("email")
        or userinfo.get("preferred_username")
        or ""
    ).lower().strip()
    if not email or "@" not in email:
        raise AuthError("Microsoft nie zwrócił uczelnianego adresu e-mail.")

    allowed_domains = current_app.config.get("MS_ALLOWED_EMAIL_DOMAINS") or ()
    email_domain = email.rsplit("@", 1)[1]
    if allowed_domains and email_domain not in allowed_domains:
        raise AuthError("Adres e-mail nie należy do dozwolonej domeny uczelni.")
    app_role = _microsoft_app_role(userinfo)
    staff_domain = current_app.config.get(
        "MS_STAFF_EMAIL_DOMAIN", "ans-elblag.pl",
    ).strip().lower()

    user = User.query.filter_by(
        microsoft_tenant_id=claim_tenant,
        microsoft_object_id=object_id,
    ).first()
    if user is None:
        user = User.query.filter_by(email=email).first()
        if user is not None and user.microsoft_object_id:
            raise AuthError("Konto jest już powiązane z inną tożsamością Microsoft.")
        if user is not None:
            user.microsoft_tenant_id = claim_tenant
            user.microsoft_object_id = object_id
            user.email_verified = 1

    if user is None and app_role and email_domain == staff_domain:
        first_name, last_name = _microsoft_user_names(userinfo, email)
        user = User(
            email=email,
            password_hash=generate_password_hash(secrets.token_urlsafe(48)),
            first_name=first_name,
            last_name=last_name,
            role=app_role,
            is_active=1,
            email_verified=1,
            microsoft_tenant_id=claim_tenant,
            microsoft_object_id=object_id,
        )
        db.session.add(user)
        db.session.flush()
        log_action(
            "create",
            "user",
            user.id,
            after={"email": email, "role": app_role, "source": "microsoft"},
            user=user,
        )

    if user is None or not user.is_active:
        raise AuthError(
            "To konto nie jest przypisane do aktywnego użytkownika systemu."
        )
    if user.role == "student" and app_role:
        raise AuthError(
            "Rola pracownicza Microsoft nie może zostać przypisana do konta studenta."
        )
    if (
        user.role in _MICROSOFT_MANAGED_ROLES
        and email_domain == staff_domain
        and app_role is None
    ):
        raise AuthError(
            "Konto pracownika nie ma przypisanej roli tej aplikacji w Microsoft."
        )
    if user.role in _MICROSOFT_MANAGED_ROLES and app_role and user.role != app_role:
        previous_role = user.role
        user.role = app_role
        UserSession.query.filter_by(user_id=user.id, is_revoked=0).update(
            {"is_revoked": 1, "revoked_at": datetime.utcnow()},
            synchronize_session=False,
        )
        log_action(
            "update",
            "user_role",
            user.id,
            before={"role": previous_role},
            after={"role": app_role, "source": "microsoft"},
            user=user,
        )
    return user


def _finish_oauth_login(client):
    try:
        token = client.authorize_access_token()
    except OAuthError:
        current_app.logger.exception("OAuth callback failed")
        flash("Logowanie zewnętrzne nie powiodło się.", "error")
        return redirect(url_for("login_page"))

    userinfo = token.get("userinfo") or {}
    try:
        user = resolve_microsoft_user(userinfo)
    except AuthError as exc:
        db.session.rollback()
        flash(
            str(exc), "error",
        )
        return redirect(url_for("login_page"))

    session.clear()
    login_user(user)
    start_user_session(user)
    return redirect(url_for("index"))


@auth_bp.route("/microsoft")
def microsoft_login():
    client = oauth.create_client("microsoft")
    if client is None:
        abort(404)
    return client.authorize_redirect(
        _oauth_redirect_uri("MS_REDIRECT_URI", "auth.microsoft_callback")
    )


@auth_bp.route("/microsoft/callback")
def microsoft_callback():
    client = oauth.create_client("microsoft")
    if client is None:
        abort(404)
    return _finish_oauth_login(client)


@auth_bp.route("/zaproszenie-zopz/<token>", methods=["GET", "POST"])
def accept_zopz_invitation_route(token):
    invitation = get_active_invitation(token)
    if invitation is None:
        return render_template(
            "zopz_invitation_accept.html",
            invitation=None,
        ), 410

    existing_user = User.query.filter_by(email=invitation.email).first()
    if request.method == "POST":
        password = request.form.get("password", "")
        if existing_user is None and password != request.form.get(
            "password_confirmation", "",
        ):
            flash("Hasła nie są identyczne.", "error")
        else:
            try:
                user = accept_zopz_invitation(invitation, password)
                db.session.commit()
            except InvitationError as exc:
                db.session.rollback()
                flash(str(exc), "error")
            else:
                session.clear()
                login_user(user)
                start_user_session(user)
                flash("Konto opiekuna zostało aktywowane.", "success")
                return redirect(url_for("index"))

    return render_template(
        "zopz_invitation_accept.html",
        invitation=invitation,
        existing_account=existing_user is not None,
    )


@auth_bp.route("/debug-login/<account_key>", methods=["POST"])
def debug_login(account_key):
    if not current_app.config.get("DEBUG_LOGIN_BUTTONS"):
        abort(404)
    account = _DEBUG_ACCOUNTS.get(account_key)
    if account is None:
        abort(404)
    _label, email, env_name = account
    password = os.environ.get(env_name, "")
    if not password:
        abort(404)
    try:
        user = authenticate_user(email, password)
    except AuthError as exc:
        flash(str(exc), "error")
        return redirect(url_for("login_page"))
    session.clear()
    login_user(user)
    start_user_session(user)
    return redirect(url_for("index"))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    revoke_user_session()
    logout_user()
    flash("Zostałeś wylogowany.", "info")
    return redirect(url_for("login_page"))
