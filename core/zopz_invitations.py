import hashlib
import re
import secrets
import smtplib
from datetime import datetime
from email.message import EmailMessage

from flask import current_app
from werkzeug.security import generate_password_hash

from core.audit import log_action
from core.models import (
    Internship,
    InternshipPart,
    User,
    ZopzInvitation,
    db,
)


class InvitationError(ValueError):
    pass


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def invitation_token_hash(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_zopz_invitation(
    *,
    email,
    first_name,
    last_name,
    internship,
    internship_part=None,
    invited_by,
):
    normalized_email = email.lower().strip()[:255]
    first_name = first_name.strip()[:100]
    last_name = last_name.strip()[:100]
    if not _EMAIL_PATTERN.fullmatch(normalized_email):
        raise InvitationError("Podaj prawidłowy adres e-mail opiekuna.")
    if not first_name or not last_name:
        raise InvitationError("Imię i nazwisko opiekuna są wymagane.")
    if internship_part is not None and internship_part.internship_id != internship.id:
        raise InvitationError("Część praktyki nie należy do wskazanej praktyki.")

    existing_user = User.query.filter_by(email=normalized_email).first()
    if existing_user is not None and existing_user.role != "zopz":
        raise InvitationError(
            "Ten adres e-mail jest już przypisany do konta o innej roli."
        )

    now = datetime.utcnow()
    pending = ZopzInvitation.query.filter_by(
        internship_id=internship.id,
        internship_part_id=getattr(internship_part, "id", None),
    ).filter(
        ZopzInvitation.accepted_at.is_(None),
        ZopzInvitation.revoked_at.is_(None),
    ).all()
    for invitation in pending:
        invitation.revoked_at = now

    raw_token = secrets.token_urlsafe(48)
    invitation = ZopzInvitation(
        email=normalized_email,
        first_name=first_name,
        last_name=last_name,
        internship_id=internship.id,
        internship_part_id=getattr(internship_part, "id", None),
        invited_by_id=invited_by.id,
        token_hash=invitation_token_hash(raw_token),
        expires_at=now + current_app.config["ZOPZ_INVITATION_LIFETIME"],
    )
    db.session.add(invitation)
    db.session.flush()
    log_action(
        "create",
        "zopz_invitation",
        invitation.id,
        after={
            "email": normalized_email,
            "internship_id": internship.id,
            "internship_part_id": invitation.internship_part_id,
            "expires_at": invitation.expires_at.isoformat(),
        },
    )
    return invitation, raw_token


def get_active_invitation(raw_token):
    if not raw_token:
        return None
    invitation = ZopzInvitation.query.filter_by(
        token_hash=invitation_token_hash(raw_token),
    ).first()
    return invitation if invitation is not None and invitation.is_pending else None


def accept_zopz_invitation(invitation, password):
    invitation = ZopzInvitation.query.with_for_update().filter_by(
        id=invitation.id,
    ).first()
    if invitation is None:
        raise InvitationError("Zaproszenie jest nieprawidłowe lub wygasło.")
    if not invitation.is_pending:
        raise InvitationError("Zaproszenie jest nieprawidłowe lub wygasło.")

    user = User.query.filter_by(email=invitation.email).first()
    if user is not None and user.role != "zopz":
        raise InvitationError(
            "Adres zaproszenia jest przypisany do konta o innej roli."
        )
    if user is not None and not user.is_active:
        raise InvitationError("Konto opiekuna zostało dezaktywowane.")
    if user is None:
        if len(password) > 1024:
            raise InvitationError("Hasło jest zbyt długie.")
        if len(password) < 12:
            raise InvitationError("Hasło musi mieć co najmniej 12 znaków.")
        user = User(
            email=invitation.email,
            password_hash=generate_password_hash(password),
            first_name=invitation.first_name,
            last_name=invitation.last_name,
            role="zopz",
            is_active=1,
            email_verified=1,
        )
        db.session.add(user)
        db.session.flush()

    internship = db.session.get(Internship, invitation.internship_id)
    if internship is None:
        raise InvitationError("Praktyka przypisana do zaproszenia już nie istnieje.")
    if invitation.internship_part_id is not None:
        part = db.session.get(InternshipPart, invitation.internship_part_id)
        if part is None or part.internship_id != internship.id:
            raise InvitationError(
                "Część praktyki przypisana do zaproszenia już nie istnieje."
            )
        part.zopz_id = user.id
    else:
        internship.zopz_id = user.id

    invitation.accepted_user_id = user.id
    invitation.accepted_at = datetime.utcnow()
    log_action(
        "accept",
        "zopz_invitation",
        invitation.id,
        after={
            "user_id": user.id,
            "internship_id": internship.id,
            "internship_part_id": invitation.internship_part_id,
        },
        user=user,
    )
    return user


def revoke_zopz_invitation(invitation):
    if invitation.accepted_at is not None:
        raise InvitationError("Zaakceptowanego zaproszenia nie można unieważnić.")
    if invitation.revoked_at is None:
        invitation.revoked_at = datetime.utcnow()
        log_action("revoke", "zopz_invitation", invitation.id)


def send_invitation_email(invitation, invitation_url):
    host = current_app.config.get("SMTP_HOST")
    if not host:
        return False

    message = EmailMessage()
    message["Subject"] = "Zaproszenie do Systemu Praktyk ANS Elbląg"
    message["From"] = current_app.config["MAIL_FROM"]
    message["To"] = invitation.email
    message.set_content(
        f"Dzień dobry {invitation.first_name},\n\n"
        "otrzymujesz dostęp jako zakładowy opiekun praktyki. "
        f"Zaproszenie jest ważne do {invitation.expires_at:%d.%m.%Y %H:%M} UTC.\n\n"
        f"Aktywuj konto: {invitation_url}\n\n"
        "Jeżeli nie oczekujesz tego zaproszenia, zignoruj wiadomość."
    )

    with smtplib.SMTP(
        host, current_app.config["SMTP_PORT"], timeout=15,
    ) as smtp:
        if current_app.config["SMTP_USE_TLS"]:
            smtp.starttls()
        username = current_app.config.get("SMTP_USERNAME")
        if username:
            smtp.login(username, current_app.config.get("SMTP_PASSWORD", ""))
        smtp.send_message(message)
    return True
