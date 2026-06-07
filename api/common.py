import re
from datetime import datetime
from functools import wraps

from flask import request
from flask_login import current_user

from api.errors import ForbiddenError, UnauthorizedError, ValidationError


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                raise UnauthorizedError("Authentication required.")
            if current_user.role not in roles:
                raise ForbiddenError("You do not have permission for this operation.")
            return view(*args, **kwargs)

        return wrapped

    return decorator


def json_payload():
    if not request.is_json:
        raise ValidationError("Request body must use application/json.")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")
    return payload


def required_text(payload, field, *, max_length=None):
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            "Invalid request data.",
            details={field: "This field is required."},
        )
    value = value.strip()
    if max_length and len(value) > max_length:
        raise ValidationError(
            "Invalid request data.",
            details={field: f"Maximum length is {max_length} characters."},
        )
    return value


def optional_text(payload, field, *, max_length=None):
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(
            "Invalid request data.",
            details={field: "This field must be a string."},
        )
    value = value.strip() or None
    if value and max_length and len(value) > max_length:
        raise ValidationError(
            "Invalid request data.",
            details={field: f"Maximum length is {max_length} characters."},
        )
    return value


def email_value(payload):
    email = required_text(payload, "email", max_length=255).lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise ValidationError(
            "Invalid request data.",
            details={"email": "Invalid email address."},
        )
    return email


def album_number_value(payload):
    album_number = required_text(payload, "album_number", max_length=20)
    if not album_number.isdigit() or len(album_number) < 4:
        raise ValidationError(
            "Invalid request data.",
            details={
                "album_number": "Album number must contain 4 to 20 digits.",
            },
        )
    return album_number


def integer_value(value, field):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            "Invalid request data.",
            details={field: "This field must be an integer."},
        ) from None
    if parsed <= 0:
        raise ValidationError(
            "Invalid request data.",
            details={field: "This field must be a positive integer."},
        )
    return parsed


def date_value(payload, field, *, required=True):
    raw = payload.get(field)
    if raw in (None, "") and not required:
        return None
    if not isinstance(raw, str):
        raise ValidationError(
            "Invalid request data.",
            details={field: "Date must use YYYY-MM-DD format."},
        )
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(
            "Invalid request data.",
            details={field: "Date must use YYYY-MM-DD format."},
        ) from None


def datetime_value(payload, field, *, required=False):
    raw = payload.get(field)
    if raw in (None, "") and not required:
        return None
    if not isinstance(raw, str):
        raise ValidationError(
            "Invalid request data.",
            details={field: "Invalid ISO date or datetime."},
        )
    try:
        return datetime.fromisoformat(raw.strip().replace("Z", "+00:00")).replace(
            tzinfo=None,
        )
    except ValueError:
        raise ValidationError(
            "Invalid request data.",
            details={field: "Invalid ISO date or datetime."},
        ) from None
