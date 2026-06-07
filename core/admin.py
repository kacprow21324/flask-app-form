import csv
import io
import re
import secrets

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

from core.audit import log_action
from core.internships import current_academic_year, normalize_academic_year
from core.models import (
    ArchivePackage,
    AuditLog,
    DocumentWorkflow,
    Internship,
    User,
    UserSession,
    db,
)


admin_bp = Blueprint("admin", __name__, url_prefix="/administracja")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_HEADERS = {"email", "first_name", "last_name", "album_number"}
OPTIONAL_HEADERS = {
    "speciality",
    "study_mode",
    "semester",
    "study_year",
}


class CSVImportError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("Plik CSV zawiera błędy.")


def _admin_required():
    if current_user.role not in ("admin", "dziekanat"):
        abort(403)


def _decode_csv(file_storage):
    raw = file_storage.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise CSVImportError(["Plik CSV przekracza limit 2 MB."])
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CSVImportError(["Plik CSV musi być zapisany w UTF-8."]) from None


def parse_student_csv(file_storage):
    text = _decode_csv(file_storage)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = {str(item or "").strip() for item in (reader.fieldnames or [])}
    missing = sorted(REQUIRED_HEADERS - headers)
    if missing:
        raise CSVImportError([
            "Brak wymaganych kolumn: " + ", ".join(missing) + "."
        ])

    rows = []
    errors = []
    seen_emails = set()
    seen_albums = set()
    for line_number, raw_row in enumerate(reader, start=2):
        row = {
            key: str(raw_row.get(key) or "").strip()
            for key in REQUIRED_HEADERS | OPTIONAL_HEADERS
        }
        if not any(row.values()):
            continue
        row["email"] = row["email"].lower()
        if not EMAIL_PATTERN.fullmatch(row["email"]):
            errors.append(f"Wiersz {line_number}: nieprawidłowy email.")
        if not row["first_name"] or not row["last_name"]:
            errors.append(f"Wiersz {line_number}: imię i nazwisko są wymagane.")
        if not row["album_number"].isdigit() or not (4 <= len(row["album_number"]) <= 20):
            errors.append(f"Wiersz {line_number}: nieprawidłowy numer albumu.")
        if row["email"] in seen_emails:
            errors.append(f"Wiersz {line_number}: powtórzony email w pliku.")
        if row["album_number"] in seen_albums:
            errors.append(f"Wiersz {line_number}: powtórzony numer albumu w pliku.")
        seen_emails.add(row["email"])
        seen_albums.add(row["album_number"])
        if row["study_mode"] and row["study_mode"] not in (
            "stacjonarne", "niestacjonarne",
        ):
            errors.append(
                f"Wiersz {line_number}: study_mode musi mieć wartość "
                "'stacjonarne' albo 'niestacjonarne'."
            )
        rows.append(row)
    if not rows:
        errors.append("Plik CSV nie zawiera żadnych studentów.")
    if errors:
        raise CSVImportError(errors)
    return rows


def import_students_csv(file_storage):
    rows = parse_student_csv(file_storage)
    created = 0
    updated = 0
    for row in rows:
        by_email = User.query.filter_by(email=row["email"]).first()
        by_album = User.query.filter_by(
            album_number=row["album_number"],
        ).first()
        if by_email and by_album and by_email.id != by_album.id:
            raise CSVImportError([
                f"Konflikt dla {row['email']}: email i numer albumu należą "
                "do różnych kont."
            ])
        user = by_email or by_album
        if user is not None and user.role != "student":
            raise CSVImportError([
                f"Email {row['email']} albo numer {row['album_number']} "
                "należy do konta o innej roli."
            ])
        if user is None:
            user = User(
                email=row["email"],
                password_hash=generate_password_hash(secrets.token_urlsafe(48)),
                first_name=row["first_name"],
                last_name=row["last_name"],
                role="student",
                album_number=row["album_number"],
                is_active=1,
            )
            db.session.add(user)
            created += 1
        else:
            user.email = row["email"]
            user.first_name = row["first_name"]
            user.last_name = row["last_name"]
            user.album_number = row["album_number"]
            updated += 1
        user.speciality = row["speciality"] or None
        user.study_mode = row["study_mode"] or "stacjonarne"
        user.semester = row["semester"] or None
        user.study_year = row["study_year"] or None
    return {"created": created, "updated": updated, "total": len(rows)}


def progress_report_csv(academic_year):
    internships = Internship.query.filter_by(
        academic_year=academic_year,
    ).all()
    student_ids = {item.student_id for item in internships}
    students = (
        User.query.filter(User.id.in_(student_ids))
        .order_by(User.last_name, User.first_name)
        .all()
        if student_ids else []
    )
    internship_by_student = {item.student_id: item for item in internships}
    albums = [student.album_number for student in students if student.album_number]
    workflow_rows = (
        DocumentWorkflow.query.filter(
            DocumentWorkflow.album_number.in_(albums),
        ).all()
        if albums else []
    )
    statuses = {}
    for row in workflow_rows:
        statuses.setdefault(row.album_number, []).append(row.status)

    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "rok_akademicki",
        "nr_albumu",
        "imie",
        "nazwisko",
        "email",
        "czesci_praktyki",
        "godziny",
        "dni",
        "dokumenty_zatwierdzone",
        "dokumenty_oczekujace",
        "dokumenty_odrzucone",
        "ocena_koncowa",
        "status_praktyki",
        "zarchiwizowana",
    ])
    for student in students:
        internship = internship_by_student[student.id]
        student_statuses = statuses.get(student.album_number, [])
        writer.writerow([
            academic_year,
            student.album_number or "",
            student.first_name,
            student.last_name,
            student.email,
            len([part for part in internship.parts if part.status != "cancelled"]),
            internship.total_hours,
            internship.total_days,
            student_statuses.count("approved"),
            student_statuses.count("pending"),
            student_statuses.count("rejected"),
            internship.grade_k or "",
            internship.status,
            "tak" if internship.is_archived else "nie",
        ])
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _dashboard_context():
    role_filter = request.args.get("rola", "").strip()
    active_filter = request.args.get("aktywny", "").strip()
    query_text = request.args.get("q", "").strip()
    users_query = User.query
    if role_filter:
        users_query = users_query.filter(User.role == role_filter)
    if active_filter in ("0", "1"):
        users_query = users_query.filter(User.is_active == int(active_filter))
    if query_text:
        pattern = f"%{query_text}%"
        users_query = users_query.filter(or_(
            User.email.like(pattern),
            User.first_name.like(pattern),
            User.last_name.like(pattern),
            User.album_number.like(pattern),
        ))
    users = users_query.order_by(User.role, User.last_name, User.first_name).limit(300).all()
    return {
        "users": users,
        "role_filter": role_filter,
        "active_filter": active_filter,
        "query_text": query_text,
        "audit_logs": AuditLog.query.order_by(
            AuditLog.performed_at.desc(),
        ).limit(100).all(),
        "archives": ArchivePackage.query.order_by(
            ArchivePackage.created_at.desc(),
        ).limit(100).all(),
        "academic_years": sorted({
            row[0]
            for row in db.session.query(Internship.academic_year).distinct().all()
        } | {current_academic_year()}, reverse=True),
        "counts": {
            "users": User.query.count(),
            "active": User.query.filter_by(is_active=1).count(),
            "students": User.query.filter_by(role="student").count(),
            "archives": ArchivePackage.query.filter_by(status="active").count(),
        },
    }


@admin_bp.route("/")
@login_required
def dashboard():
    _admin_required()
    return render_template("administracja.html", **_dashboard_context())


@admin_bp.route("/uzytkownicy/<int:user_id>/status", methods=["POST"])
@login_required
def user_status(user_id):
    if current_user.role != "admin":
        abort(403)
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash("Nie można dezaktywować własnego konta.", "error")
        return redirect(url_for("admin.dashboard"))
    before = {"is_active": user.is_active}
    user.is_active = 0 if user.is_active else 1
    if not user.is_active:
        UserSession.query.filter_by(user_id=user.id, is_revoked=0).update(
            {"is_revoked": 1},
            synchronize_session=False,
        )
    log_action(
        "update",
        "user",
        user.id,
        before=before,
        after={"is_active": user.is_active},
    )
    db.session.commit()
    flash("Status konta został zmieniony.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/uzytkownicy/<int:user_id>/reset-hasla", methods=["POST"])
@login_required
def reset_password(user_id):
    if current_user.role != "admin":
        abort(403)
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    temporary_password = secrets.token_urlsafe(15)
    user.password_hash = generate_password_hash(temporary_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    UserSession.query.filter_by(user_id=user.id, is_revoked=0).update(
        {"is_revoked": 1},
        synchronize_session=False,
    )
    log_action("reset_password", "user", user.id)
    db.session.commit()
    flash(
        f"Hasło tymczasowe dla {user.email}: {temporary_password}",
        "warning",
    )
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/import-studentow", methods=["POST"])
@login_required
def import_students():
    _admin_required()
    uploaded = request.files.get("csv_file")
    if uploaded is None or not uploaded.filename:
        flash("Wybierz plik CSV.", "error")
        return redirect(url_for("admin.dashboard"))
    try:
        result = import_students_csv(uploaded)
    except CSVImportError as exc:
        db.session.rollback()
        for error in exc.errors[:20]:
            flash(error, "error")
        if len(exc.errors) > 20:
            flash(f"Pozostałe błędy: {len(exc.errors) - 20}.", "error")
        return redirect(url_for("admin.dashboard"))
    log_action("import", "students_csv", after=result)
    db.session.commit()
    flash(
        f"Import zakończony: utworzono {result['created']}, "
        f"zaktualizowano {result['updated']}.",
        "success",
    )
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/import-studentow/wzor.csv")
@login_required
def import_template():
    _admin_required()
    content = (
        "\ufeffemail;first_name;last_name;album_number;speciality;"
        "study_mode;semester;study_year\r\n"
        "student@uczelnia.pl;Jan;Kowalski;25001;"
        "Administracja systemów i sieci komputerowych (ASiSK);"
        "stacjonarne;6;3\r\n"
    ).encode("utf-8")
    return send_file(
        io.BytesIO(content),
        as_attachment=True,
        download_name="wzor_importu_studentow.csv",
        mimetype="text/csv; charset=utf-8",
    )


@admin_bp.route("/raport-postepu.csv")
@login_required
def progress_report():
    _admin_required()
    requested_year = request.args.get("rok")
    year = normalize_academic_year(
        requested_year,
        default_current=not requested_year,
    )
    if year is None:
        abort(400)
    content = progress_report_csv(year)
    log_action(
        "export",
        "progress_report",
        year,
        after={"academic_year": year},
        commit=True,
    )
    return send_file(
        io.BytesIO(content),
        as_attachment=True,
        download_name=f"raport_postepu_{year.replace('/', '-')}.csv",
        mimetype="text/csv; charset=utf-8",
    )
