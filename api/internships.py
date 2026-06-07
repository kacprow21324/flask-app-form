from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from api.common import (
    date_value,
    integer_value,
    json_payload,
    optional_text,
    require_roles,
    required_text,
)
from api.errors import ConflictError, NotFoundError, ValidationError
from core.audit import log_action
from core.internships import normalize_academic_year
from core.models import Company, Internship, User, db


internships_bp = Blueprint(
    "api_internships", __name__, url_prefix="/internships",
)
MANAGER_ROLES = ("admin", "dziekanat")
STATUSES = {"draft", "active", "completed", "cancelled"}


def _internship_or_404(internship_id):
    internship = db.session.get(Internship, internship_id)
    if internship is None or internship.is_archived:
        raise NotFoundError("Internship not found.")
    return internship


def _serialize(internship):
    return {
        "id": internship.id,
        "student_id": internship.student_id,
        "company_name": (
            internship.company.name if internship.company is not None else None
        ),
        "start_date": (
            internship.start_date.isoformat() if internship.start_date else None
        ),
        "end_date": (
            internship.end_date.isoformat() if internship.end_date else None
        ),
        "status": internship.status,
        "academic_year": internship.academic_year,
    }


def _status(payload):
    status = required_text(payload, "status", max_length=30)
    if status not in STATUSES:
        raise ValidationError(
            "Invalid request data.",
            details={"status": f"Allowed values: {', '.join(sorted(STATUSES))}."},
        )
    return status


@internships_bp.get("")
@require_roles(*MANAGER_ROLES)
def list_internships():
    query = Internship.query.filter_by(is_archived=0)
    raw_student_id = request.args.get("student_id")
    if raw_student_id is not None:
        query = query.filter_by(
            student_id=integer_value(raw_student_id, "student_id"),
        )
    internships = query.order_by(Internship.id).all()
    return jsonify({
        "internships": [_serialize(internship) for internship in internships],
    })


@internships_bp.get("/<int:internship_id>")
@require_roles(*MANAGER_ROLES)
def get_internship(internship_id):
    return jsonify(_serialize(_internship_or_404(internship_id)))


@internships_bp.post("")
@require_roles(*MANAGER_ROLES)
def create_internship():
    payload = json_payload()
    student_id = integer_value(payload.get("student_id"), "student_id")
    student = db.session.get(User, student_id)
    if student is None or student.role != "student" or not student.is_active:
        raise NotFoundError("Student not found.")

    company_name = required_text(payload, "company_name", max_length=300)
    start_date = date_value(payload, "start_date")
    end_date = date_value(payload, "end_date")
    if end_date < start_date:
        raise ValidationError(
            "Invalid request data.",
            details={"end_date": "End date cannot be earlier than start date."},
        )
    academic_year = normalize_academic_year(
        optional_text(payload, "academic_year", max_length=20),
        default_current=False,
    )
    if academic_year is None:
        academic_year = (
            f"{start_date.year}/{start_date.year + 1}"
            if start_date.month >= 10
            else f"{start_date.year - 1}/{start_date.year}"
        )

    company = Company.query.filter_by(name=company_name).first()
    if company is None:
        company = Company(name=company_name)
        db.session.add(company)
        db.session.flush()
    internship = Internship(
        student_id=student.id,
        company_id=company.id,
        start_date=start_date,
        end_date=end_date,
        status=_status(payload),
        academic_year=academic_year,
    )
    db.session.add(internship)
    try:
        db.session.flush()
        log_action(
            "create",
            "internship",
            internship.id,
            after=_serialize(internship),
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ConflictError(
            "This student already has an internship for the academic year.",
        ) from None
    return jsonify(_serialize(internship)), 201


@internships_bp.put("/<int:internship_id>")
@require_roles(*MANAGER_ROLES)
def update_internship_status(internship_id):
    internship = _internship_or_404(internship_id)
    before = _serialize(internship)
    internship.status = _status(json_payload())
    log_action(
        "update",
        "internship",
        internship.id,
        before=before,
        after=_serialize(internship),
    )
    db.session.commit()
    return jsonify(_serialize(internship))


@internships_bp.delete("/<int:internship_id>")
@require_roles(*MANAGER_ROLES)
def delete_internship(internship_id):
    internship = _internship_or_404(internship_id)
    before = _serialize(internship)
    internship.is_archived = 1
    internship.status = "cancelled"
    log_action("archive", "internship", internship.id, before=before)
    db.session.commit()
    return "", 204
