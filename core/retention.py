import hashlib
import json
import os
import secrets
import shutil
import zipfile
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash
from sqlalchemy import or_

from core import store
from core.documents import generated_document_path
from core.models import (
    ArchivePackage,
    AuditLog,
    DocumentLog,
    DocumentWorkflow,
    GeneratedDocument,
    GradeCalculation,
    Internship,
    InternshipPart,
    LoginAttempt,
    Notification,
    User,
    UserSession,
    db,
)


def _json_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        default=str,
    ).encode("utf-8")


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _safe_path(base_dir, relative_path):
    root = os.path.abspath(base_dir)
    candidate = os.path.abspath(os.path.join(root, relative_path))
    if os.path.commonpath([root, candidate]) != root:
        raise ValueError("Ścieżka wychodzi poza katalog danych.")
    return candidate


def archive_package_path(package, base_dir):
    if not package.file_path:
        return None
    return _safe_path(base_dir, package.file_path)


def _model_values(row, excluded=()):
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in excluded
    }


def _student_manifest(student, forms, internships, generated_documents):
    internship_ids = [item.id for item in internships]
    parts = (
        InternshipPart.query.filter(
            InternshipPart.internship_id.in_(internship_ids),
        ).all()
        if internship_ids else []
    )
    grades = (
        GradeCalculation.query.filter(
            GradeCalculation.internship_id.in_(internship_ids),
        ).all()
        if internship_ids else []
    )
    workflow_rows = DocumentWorkflow.query.filter_by(
        album_number=student.album_number,
    ).all()
    document_logs = DocumentLog.query.filter_by(
        album_number=student.album_number,
    ).all()
    return {
        "schema_version": 1,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "student": _model_values(
            student,
            excluded=("password_hash", "failed_login_attempts", "locked_until"),
        ),
        "forms": forms,
        "internships": [_model_values(item) for item in internships],
        "internship_parts": [_model_values(item) for item in parts],
        "workflow": [_model_values(item) for item in workflow_rows],
        "document_logs": [_model_values(item) for item in document_logs],
        "grade_calculations": [_model_values(item) for item in grades],
        "generated_documents": [
            _model_values(item) for item in generated_documents
        ],
    }


def create_student_archive(
    *,
    student,
    base_dir,
    actor,
    retention_years=10,
    hash_salt="",
    now=None,
):
    if student is None or student.role != "student" or not student.album_number:
        raise ValueError("Archiwizacja wymaga aktywnego rekordu studenta.")
    active_package = ArchivePackage.query.filter_by(
        student_id=student.id,
        status="active",
    ).first()
    if active_package is not None:
        raise ValueError("Ten rekord ma już aktywny pakiet archiwalny.")
    now = now or datetime.utcnow()
    album_number = student.album_number
    album_hash = hashlib.sha256(
        f"{hash_salt}:{album_number}".encode("utf-8")
    ).hexdigest()
    version = (
        db.session.query(db.func.max(ArchivePackage.package_version))
        .filter(ArchivePackage.student_id == student.id)
        .scalar()
        or 0
    ) + 1
    forms = store.get_student_forms(album_number)
    internships = Internship.query.filter_by(student_id=student.id).all()
    generated_documents = GeneratedDocument.query.filter_by(
        album_number=album_number,
    ).all()
    manifest = _student_manifest(
        student, forms, internships, generated_documents,
    )
    manifest["package_version"] = version
    manifest_bytes = _json_bytes(manifest)
    stored_manifest = json.loads(manifest_bytes.decode("utf-8"))
    manifest_checksum = _sha256_bytes(manifest_bytes)

    relative_dir = os.path.join("archives", album_hash[:16])
    archive_dir = _safe_path(base_dir, relative_dir)
    os.makedirs(archive_dir, exist_ok=True)
    file_name = f"archive_v{version}_{now.strftime('%Y%m%d%H%M%S')}.zip"
    relative_path = os.path.join(relative_dir, file_name).replace("\\", "/")
    absolute_path = _safe_path(base_dir, relative_path)

    missing_files = []
    with zipfile.ZipFile(
        absolute_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr("manifest.json", manifest_bytes)
        archive.writestr("forms.json", _json_bytes(forms))
        for document in generated_documents:
            try:
                source_path = generated_document_path(document, base_dir)
            except ValueError:
                missing_files.append(document.file_path)
                continue
            if not os.path.isfile(source_path):
                missing_files.append(document.file_path)
                continue
            with open(source_path, "rb") as handle:
                actual_checksum = _sha256_bytes(handle.read())
            if actual_checksum != document.checksum_sha256:
                missing_files.append(
                    f"{document.file_path} (niezgodna suma kontrolna)"
                )
                continue
            archive.write(
                source_path,
                f"generated_documents/{document.id}_{os.path.basename(source_path)}",
            )

        uploads_dir = _safe_path(base_dir, os.path.join("uploads", album_number))
        if os.path.isdir(uploads_dir):
            for root, _, files in os.walk(uploads_dir):
                for name in files:
                    source_path = os.path.join(root, name)
                    if os.path.islink(source_path):
                        continue
                    relative = os.path.relpath(source_path, uploads_dir)
                    archive.write(source_path, f"uploads/{relative}")

    if missing_files:
        os.remove(absolute_path)
        raise FileNotFoundError(
            "Archiwum nie zostało utworzone, ponieważ brakuje plików: "
            + ", ".join(missing_files)
        )

    with open(absolute_path, "rb") as handle:
        archive_bytes = handle.read()
    package = ArchivePackage(
        student_id=student.id,
        original_album_number=album_number,
        album_hash=album_hash,
        package_version=version,
        status="active",
        file_path=relative_path,
        file_name=file_name,
        file_size_bytes=len(archive_bytes),
        checksum_sha256=_sha256_bytes(archive_bytes),
        manifest_checksum_sha256=manifest_checksum,
        manifest=stored_manifest,
        created_by=getattr(actor, "id", None),
        created_at=now,
        retention_until=now + timedelta(days=365 * int(retention_years)),
    )
    db.session.add(package)
    for internship in internships:
        internship.is_archived = 1
    db.session.flush()
    return package, absolute_path


def verify_archive_package(package, base_dir):
    path = archive_package_path(package, base_dir)
    if path is None or not os.path.isfile(path):
        return False
    with open(path, "rb") as handle:
        if _sha256_bytes(handle.read()) != package.checksum_sha256:
            return False
    try:
        with zipfile.ZipFile(path, "r") as archive:
            manifest_bytes = archive.read("manifest.json")
            if archive.testzip() is not None:
                return False
    except (OSError, KeyError, zipfile.BadZipFile):
        return False
    return _sha256_bytes(manifest_bytes) == package.manifest_checksum_sha256


def _redact(value, replacements):
    if isinstance(value, dict):
        return {key: _redact(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, replacements) for item in value]
    if isinstance(value, str):
        result = value
        for old, new in replacements.items():
            if old:
                result = result.replace(old, new)
        return result
    return value


def _remove_tree(base_dir, relative_path):
    target = _safe_path(base_dir, relative_path)
    if os.path.isdir(target):
        shutil.rmtree(target)


def anonymize_expired_archive(package, *, base_dir, now=None):
    now = now or datetime.utcnow()
    if package.status != "active":
        return False
    if package.retention_until > now:
        raise ValueError("Okres retencji tego archiwum jeszcze nie upłynął.")
    student = package.student
    album_number = package.original_album_number
    if student is None or not album_number:
        raise ValueError("Archiwum nie ma rekordu studenta do anonimizacji.")
    if not verify_archive_package(package, base_dir):
        raise ValueError("Integralność pakietu archiwalnego jest nieprawidłowa.")

    old_name = student.full_name
    old_email = student.email
    token = f"anon-{package.album_hash[:16]}"
    replacement_email = f"{token}@invalid.local"
    replacements = {
        album_number: token,
        old_name: "[ANONYMIZED]",
        old_email: replacement_email,
    }

    generated_documents = GeneratedDocument.query.filter_by(
        album_number=album_number,
    ).all()
    for document in generated_documents:
        try:
            path = generated_document_path(document, base_dir)
        except ValueError:
            path = None
        if path and os.path.isfile(path):
            os.remove(path)
        db.session.delete(document)

    _remove_tree(base_dir, os.path.join("uploads", album_number))
    generated_dir = _safe_path(
        base_dir, os.path.join("generated", album_number),
    )
    if os.path.isdir(generated_dir):
        shutil.rmtree(generated_dir)
    store.delete_student_forms(album_number)

    DocumentWorkflow.query.filter_by(album_number=album_number).update(
        {"album_number": token},
        synchronize_session=False,
    )
    for entry in DocumentLog.query.filter_by(album_number=album_number).all():
        entry.album_number = token
        if entry.actor_name == old_name:
            entry.actor_name = "[ANONYMIZED]"

    Notification.query.filter(
        or_(
            Notification.recipient_id == student.id,
            Notification.message.like(f"%{old_name}%"),
            Notification.message.like(f"%{album_number}%"),
        )
    ).delete(synchronize_session=False)
    UserSession.query.filter_by(user_id=student.id).delete(
        synchronize_session=False,
    )
    LoginAttempt.query.filter_by(email=old_email).update(
        {"email": replacement_email},
        synchronize_session=False,
    )
    for audit in AuditLog.query.all():
        audit.entity_id = _redact(audit.entity_id, replacements)
        audit.changes_before = _redact(audit.changes_before, replacements)
        audit.changes_after = _redact(audit.changes_after, replacements)

    student.email = replacement_email
    student.password_hash = generate_password_hash(secrets.token_urlsafe(48))
    student.first_name = "Użytkownik"
    student.last_name = token
    student.album_number = None
    student.speciality = None
    student.study_mode = None
    student.semester = None
    student.study_year = None
    student.avatar_url = None
    student.email_verified = 0
    student.failed_login_attempts = 0
    student.locked_until = None
    student.is_active = 0
    student.anonymized_at = now

    archive_path = archive_package_path(package, base_dir)
    if archive_path and os.path.isfile(archive_path):
        os.remove(archive_path)
    package.original_album_number = None
    package.status = "purged"
    package.file_path = None
    package.file_name = None
    package.file_size_bytes = None
    package.manifest = {
        "schema_version": 1,
        "purged": True,
        "album_hash": package.album_hash,
        "package_version": package.package_version,
    }
    package.anonymized_at = now
    package.purged_at = now
    db.session.flush()
    return True


def process_due_archives(*, base_dir, now=None):
    now = now or datetime.utcnow()
    processed = []
    packages = ArchivePackage.query.filter(
        ArchivePackage.status == "active",
        ArchivePackage.retention_until <= now,
    ).all()
    for package in packages:
        anonymize_expired_archive(package, base_dir=base_dir, now=now)
        processed.append(package.id)
    db.session.commit()
    return processed
