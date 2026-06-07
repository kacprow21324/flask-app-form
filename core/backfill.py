from core import store
from core.internships import ensure_internship
from core.models import (
    Attachment, Company, DocumentWorkflow, Internship, Notification, User, db,
)
from core.notifications import notify_user


_FORM_PRIORITY = {
    "zal1": 0,
    "zal3": 1,
    "zal6": 2,
    "zal9": 3,
}


def _document_link(album_number, form_key):
    return f"/student/{album_number}#doc-{form_key}"


def backfill_operational_data():
    before = {
        "companies": Company.query.count(),
        "internships": Internship.query.count(),
        "notifications": Notification.query.count(),
    }
    data = store.load_data()
    attachments = {item.key: item for item in Attachment.query.all()}
    workflow_states = {
        (item.album_number, item.form_key): item
        for item in DocumentWorkflow.query.all()
    }

    for album_number, forms in data.items():
        ordered_forms = sorted(
            forms.items(),
            key=lambda item: (_FORM_PRIORITY.get(item[0], 10), item[0]),
        )
        for form_key, record in ordered_forms:
            if not isinstance(record, dict):
                continue
            state = workflow_states.get((album_number, form_key))
            status = state.status if state else "draft"
            ensure_internship(
                album_number,
                form_key,
                record,
                document_status=status,
            )
            attachment = attachments.get(form_key)
            number = attachment.nr if attachment else form_key
            link = _document_link(album_number, form_key)
            if status == "pending" and attachment and attachment.reviewer_role:
                student = User.query.filter_by(album_number=album_number).first()
                recipients = User.query.filter(
                    User.role.in_([attachment.reviewer_role, "admin"]),
                    User.is_active == 1,
                ).all()
                for recipient in recipients:
                    notify_user(
                        recipient,
                        "pending",
                        f"Zał. {number} - do zatwierdzenia",
                        getattr(student, "full_name", album_number),
                        link,
                        entity_type="document",
                        dedupe_key=(
                            f"pending:{album_number}:{form_key}:{recipient.id}"
                        ),
                    )
            elif status == "rejected":
                student = User.query.filter_by(
                    role="student", album_number=album_number,
                ).first()
                notify_user(
                    student,
                    "rejected",
                    f"Zał. {number} - wymaga poprawy",
                    getattr(state, "rejection_comment", None)
                    or "Dokument został odrzucony.",
                    link,
                    entity_type="document",
                    dedupe_key=(
                        f"rejected:{album_number}:{form_key}:"
                        f"{getattr(student, 'id', 0)}"
                    ),
                )

    db.session.commit()
    after = {
        "companies": Company.query.count(),
        "internships": Internship.query.count(),
        "notifications": Notification.query.count(),
    }
    return {key: after[key] - before[key] for key in before}


def backfill_approved_revisions():
    updated = 0
    for state in DocumentWorkflow.query.filter_by(status="approved").all():
        if state.approved_revision is not None:
            continue
        revision = store.get_form_revision(state.album_number, state.form_key)
        if revision is None:
            continue
        state.approved_revision = revision
        updated += 1
    db.session.commit()
    return updated
