from flask import has_request_context, request
from flask_login import current_user

from core.models import AuditLog, db


_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "secret",
    "token",
    "token_hash",
}


def _sanitize(value):
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if key.lower() in _SENSITIVE_KEYS else _sanitize(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def log_action(
    action,
    entity_type,
    entity_id=None,
    *,
    before=None,
    after=None,
    user=None,
    commit=False,
):
    actor = user
    if actor is None:
        try:
            actor = current_user if current_user.is_authenticated else None
        except Exception:
            actor = None

    entry = AuditLog(
        user_id=getattr(actor, "id", None),
        user_role=getattr(actor, "role", None),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        changes_before=_sanitize(before),
        changes_after=_sanitize(after),
        ip_address=request.remote_addr if has_request_context() else None,
        user_agent=(
            (request.user_agent.string or "")[:500]
            if has_request_context() and request.user_agent
            else None
        ),
    )
    db.session.add(entry)
    if commit:
        db.session.commit()
    return entry
