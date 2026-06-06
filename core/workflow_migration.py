"""Migration of workflow metadata from MongoDB to MariaDB."""

from core.models import Attachment, DocumentWorkflow, db
from core.store import WORKFLOW_METADATA_FIELDS, _coll


def synchronize_workflow_rows():
    """
    Create missing MariaDB workflow rows from legacy MongoDB metadata.

    Existing SQL statuses are never overwritten. Differences must be resolved
    before legacy MongoDB metadata can be removed.
    """
    reviewers = {item.key: item.reviewer_role for item in Attachment.query.all()}
    sql_rows = {
        (row.album_number, row.form_key): row
        for row in DocumentWorkflow.query.all()
    }
    created = 0
    mismatches = []

    for doc in _coll().find(
        {},
        {
            "album_number": 1,
            "form_key": 1,
            "data._status": 1,
            "data._rejection_comment": 1,
            "data._rejection_by": 1,
        },
    ):
        album_number = str(doc["album_number"])
        form_key = str(doc["form_key"])
        data = doc.get("data", {})
        mongo_status = data.get("_status", "draft")
        key = (album_number, form_key)
        row = sql_rows.get(key)

        if row is None:
            row = DocumentWorkflow(
                album_number=album_number,
                form_key=form_key,
                status=mongo_status,
                reviewer_role=reviewers.get(form_key),
                rejection_comment=data.get("_rejection_comment"),
                rejection_by=data.get("_rejection_by"),
            )
            db.session.add(row)
            sql_rows[key] = row
            created += 1
            continue

        if row.status != mongo_status:
            mismatches.append({
                "album_number": album_number,
                "form_key": form_key,
                "maria_status": row.status,
                "mongo_status": mongo_status,
            })
        if row.status == "rejected":
            if not row.rejection_comment:
                row.rejection_comment = data.get("_rejection_comment")
            if not row.rejection_by:
                row.rejection_by = data.get("_rejection_by")

    db.session.commit()
    return {"created": created, "mismatches": mismatches}


def count_mongo_workflow_metadata():
    """Count documents that still contain legacy workflow fields."""
    clauses = [
        {f"data.{field}": {"$exists": True}}
        for field in sorted(WORKFLOW_METADATA_FIELDS)
    ]
    return _coll().count_documents({"$or": clauses})


def remove_mongo_workflow_metadata():
    """Remove legacy metadata only when MariaDB and MongoDB statuses agree."""
    result = synchronize_workflow_rows()
    if result["mismatches"]:
        raise RuntimeError(
            "Nie usunięto metadanych MongoDB: wykryto rozbieżne statusy."
        )

    clauses = [
        {f"data.{field}": {"$exists": True}}
        for field in sorted(WORKFLOW_METADATA_FIELDS)
    ]
    unset = {f"data.{field}": "" for field in WORKFLOW_METADATA_FIELDS}
    update = _coll().update_many(
        {"$or": clauses},
        {"$unset": unset, "$inc": {"revision": 1}},
    )
    return {
        "created": result["created"],
        "cleaned": update.modified_count,
        "remaining": count_mongo_workflow_metadata(),
    }
