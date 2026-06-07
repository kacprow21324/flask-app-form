from datetime import datetime

from flask import Blueprint, jsonify, request

from api.common import (
    datetime_value,
    integer_value,
    json_payload,
    optional_text,
    require_roles,
    required_text,
)
from api.errors import NotFoundError, ValidationError
from core.audit import log_action
from core.models import Internship, PracticeDocument, db


documents_bp = Blueprint("api_documents", __name__, url_prefix="/documents")
MANAGER_ROLES = ("admin", "dziekanat")
VERIFICATION_STATUSES = {"pending", "approved", "rejected"}


def _document_or_404(document_id):
    document = db.session.get(PracticeDocument, document_id)
    if document is None:
        raise NotFoundError("Document not found.")
    return document


def _serialize(document):
    return {
        "id": document.id,
        "name": document.name,
        "document_type": document.document_type,
        "uploaded_at": document.uploaded_at.isoformat(),
        "internship_id": document.internship_id,
        "verification_status": document.verification_status,
        "supervisor_comment": document.supervisor_comment,
    }


def _verification_status(payload):
    status = payload.get("verification_status", "pending")
    if not isinstance(status, str) or status not in VERIFICATION_STATUSES:
        raise ValidationError(
            "Invalid request data.",
            details={
                "verification_status": (
                    "Allowed values: approved, pending, rejected."
                ),
            },
        )
    return status


@documents_bp.get("")
@require_roles(*MANAGER_ROLES)
def list_documents():
    query = PracticeDocument.query
    raw_internship_id = request.args.get("internship_id")
    if raw_internship_id is not None:
        query = query.filter_by(
            internship_id=integer_value(raw_internship_id, "internship_id"),
        )
    documents = query.order_by(PracticeDocument.id).all()
    return jsonify({
        "documents": [_serialize(document) for document in documents],
    })


@documents_bp.get("/<int:document_id>")
@require_roles(*MANAGER_ROLES)
def get_document(document_id):
    return jsonify(_serialize(_document_or_404(document_id)))


@documents_bp.post("")
@require_roles(*MANAGER_ROLES)
def create_document():
    payload = json_payload()
    internship_id = integer_value(payload.get("internship_id"), "internship_id")
    internship = db.session.get(Internship, internship_id)
    if internship is None or internship.is_archived:
        raise NotFoundError("Internship not found.")
    document = PracticeDocument(
        internship_id=internship.id,
        name=required_text(payload, "name", max_length=255),
        document_type=required_text(
            payload, "document_type", max_length=100,
        ),
        uploaded_at=datetime_value(payload, "uploaded_at") or datetime.utcnow(),
        verification_status=_verification_status(payload),
        supervisor_comment=optional_text(payload, "supervisor_comment"),
    )
    db.session.add(document)
    db.session.flush()
    log_action(
        "create",
        "practice_document",
        document.id,
        after=_serialize(document),
    )
    db.session.commit()
    return jsonify(_serialize(document)), 201


@documents_bp.delete("/<int:document_id>")
@require_roles(*MANAGER_ROLES)
def delete_document(document_id):
    document = _document_or_404(document_id)
    before = _serialize(document)
    document_id = document.id
    db.session.delete(document)
    log_action(
        "delete",
        "practice_document",
        document_id,
        before=before,
    )
    db.session.commit()
    return "", 204
