import hashlib
import json
import os
from datetime import datetime

from core.models import GeneratedDocument, db


def source_checksum(record):
    payload = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_fingerprint(
    *,
    album_number,
    form_key,
    source_revision,
    source_digest,
    template_version,
    internship_part=None,
):
    identity = ":".join([
        str(album_number),
        form_key,
        str(source_revision),
        source_digest,
        template_version,
        str(getattr(internship_part, "id", 0) or 0),
    ])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def generated_document_path(document, base_dir):
    root = os.path.abspath(base_dir)
    candidate = os.path.abspath(os.path.join(root, document.file_path))
    if os.path.commonpath([root, candidate]) != root:
        raise ValueError("Ścieżka dokumentu wychodzi poza katalog archiwum.")
    return candidate


def find_generated_document(
    *,
    album_number,
    form_key,
    source_revision,
    source_digest,
    template_version,
    internship_part=None,
):
    fingerprint = source_fingerprint(
        album_number=album_number,
        form_key=form_key,
        source_revision=source_revision,
        source_digest=source_digest,
        template_version=template_version,
        internship_part=internship_part,
    )
    return GeneratedDocument.query.filter_by(
        source_fingerprint=fingerprint,
    ).first()


def archive_pdf(
    pdf_bytes,
    *,
    base_dir,
    album_number,
    form_key,
    file_name,
    generated_by,
    internship=None,
    internship_part=None,
    source_revision=0,
    source_digest=None,
    source_approved_at=None,
    template_version="legacy",
):
    pdf_digest = hashlib.sha256(pdf_bytes).hexdigest()
    source_digest = source_digest or pdf_digest
    fingerprint = source_fingerprint(
        album_number=album_number,
        form_key=form_key,
        source_revision=source_revision,
        source_digest=source_digest,
        template_version=template_version,
        internship_part=internship_part,
    )
    existing = GeneratedDocument.query.filter_by(
        source_fingerprint=fingerprint,
    ).first()
    if existing is not None:
        path = generated_document_path(existing, base_dir)
        if not os.path.isfile(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(pdf_bytes)
            existing.file_size_bytes = len(pdf_bytes)
            existing.checksum_sha256 = pdf_digest
        return existing, path

    version_query = GeneratedDocument.query.filter_by(
        album_number=str(album_number),
        form_key=form_key,
    )
    if internship_part is None:
        version_query = version_query.filter(
            GeneratedDocument.internship_part_id.is_(None),
        )
    else:
        version_query = version_query.filter_by(
            internship_part_id=internship_part.id,
        )
    current_documents = version_query.all()
    version = max(
        (document.document_version or 0 for document in current_documents),
        default=0,
    ) + 1
    for document in current_documents:
        document.is_current = 0

    relative_dir = os.path.join(
        "generated",
        str(album_number),
        form_key,
    )
    target_dir = os.path.join(base_dir, relative_dir)
    os.makedirs(target_dir, exist_ok=True)
    stored_name = f"v{version}_{fingerprint[:16]}.pdf"
    absolute_path = os.path.join(target_dir, stored_name)
    with open(absolute_path, "wb") as handle:
        handle.write(pdf_bytes)

    document = GeneratedDocument(
        internship_id=getattr(internship, "id", None),
        internship_part_id=getattr(internship_part, "id", None),
        album_number=str(album_number),
        form_key=form_key,
        document_version=version,
        source_revision=int(source_revision or 0),
        source_checksum=source_digest,
        source_fingerprint=fingerprint,
        source_approved_at=source_approved_at,
        template_version=template_version,
        file_path=os.path.join(relative_dir, stored_name).replace("\\", "/"),
        file_name=file_name,
        file_size_bytes=len(pdf_bytes),
        mime_type="application/pdf",
        checksum_sha256=pdf_digest,
        generated_by=getattr(generated_by, "id", None),
        download_count=0,
        is_current=1,
    )
    db.session.add(document)
    return document, absolute_path
