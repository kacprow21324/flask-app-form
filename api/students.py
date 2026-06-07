import secrets

from flask import Blueprint, jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from api.common import (
    album_number_value,
    email_value,
    json_payload,
    require_roles,
    required_text,
)
from api.errors import ConflictError, NotFoundError
from core.audit import log_action
from core.models import User, db


students_bp = Blueprint("api_students", __name__, url_prefix="/students")
MANAGER_ROLES = ("admin", "dziekanat")


def _student_or_404(student_id):
    student = db.session.get(User, student_id)
    if student is None or student.role != "student" or not student.is_active:
        raise NotFoundError("Student not found.")
    return student


def _serialize(student):
    return {
        "id": student.id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "album_number": student.album_number,
        "email": student.email,
    }


def _validated_student_data(payload):
    return {
        "first_name": required_text(payload, "first_name", max_length=100),
        "last_name": required_text(payload, "last_name", max_length=100),
        "album_number": album_number_value(payload),
        "email": email_value(payload),
    }


def _ensure_unique(data, *, current_id=None):
    email_owner = User.query.filter_by(email=data["email"]).first()
    if email_owner is not None and email_owner.id != current_id:
        raise ConflictError("A user with this email already exists.")
    album_owner = User.query.filter_by(
        album_number=data["album_number"],
    ).first()
    if album_owner is not None and album_owner.id != current_id:
        raise ConflictError("A user with this album number already exists.")


@students_bp.get("")
@require_roles(*MANAGER_ROLES)
def list_students():
    students = (
        User.query.filter_by(role="student", is_active=1)
        .order_by(User.last_name, User.first_name, User.id)
        .all()
    )
    return jsonify({"students": [_serialize(student) for student in students]})


@students_bp.get("/<int:student_id>")
@require_roles(*MANAGER_ROLES)
def get_student(student_id):
    return jsonify(_serialize(_student_or_404(student_id)))


@students_bp.post("")
@require_roles(*MANAGER_ROLES)
def create_student():
    data = _validated_student_data(json_payload())
    _ensure_unique(data)
    student = User(
        **data,
        password_hash=generate_password_hash(secrets.token_urlsafe(48)),
        role="student",
        is_active=1,
    )
    db.session.add(student)
    try:
        db.session.flush()
        log_action("create", "student", student.id, after=_serialize(student))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ConflictError("Student data conflicts with an existing user.") from None
    return jsonify(_serialize(student)), 201


@students_bp.put("/<int:student_id>")
@require_roles(*MANAGER_ROLES)
def update_student(student_id):
    student = _student_or_404(student_id)
    data = _validated_student_data(json_payload())
    _ensure_unique(data, current_id=student.id)
    before = _serialize(student)
    for field, value in data.items():
        setattr(student, field, value)
    try:
        log_action(
            "update",
            "student",
            student.id,
            before=before,
            after=_serialize(student),
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ConflictError("Student data conflicts with an existing user.") from None
    return jsonify(_serialize(student))


@students_bp.delete("/<int:student_id>")
@require_roles(*MANAGER_ROLES)
def delete_student(student_id):
    student = _student_or_404(student_id)
    before = _serialize(student)
    student.is_active = 0
    log_action("deactivate", "student", student.id, before=before)
    db.session.commit()
    return "", 204
