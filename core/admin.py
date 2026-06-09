import csv
import io
import re
import secrets
import smtplib

from flask import (
    Blueprint,
    abort,
    current_app,
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
from core.gender import infer_gender, normalize_gender
from core.internships import current_academic_year, normalize_academic_year
from core.models import (
    AppConfig,
    ArchivePackage,
    AuditLog,
    DocumentWorkflow,
    Internship,
    InternshipPart,
    User,
    UserSession,
    ZopzInvitation,
    db,
)
from core.zopz_invitations import (
    InvitationError,
    create_zopz_invitation,
    revoke_zopz_invitation,
    send_invitation_email,
)


admin_bp = Blueprint("admin", __name__, url_prefix="/administracja")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_HEADERS = {"email", "first_name", "last_name", "album_number"}
OPTIONAL_HEADERS = {
    "speciality",
    "study_mode",
    "gender",
    "semester",
    "study_year",
}
MONTHS_PL = {
    1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień",
    5: "Maj", 6: "Czerwiec", 7: "Lipiec", 8: "Sierpień",
    9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień",
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
        if row["gender"] and normalize_gender(row["gender"]) is None:
            errors.append(
                f"Wiersz {line_number}: gender musi mieć wartość 'K' albo 'M'."
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
        user.gender = (
            normalize_gender(row["gender"])
            or user.gender
            or infer_gender(row["first_name"])
        )
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


def students_export_csv():
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "email",
        "first_name",
        "last_name",
        "album_number",
        "speciality",
        "study_mode",
        "gender",
        "semester",
        "study_year",
    ])
    students = User.query.filter_by(
        role="student", is_active=1,
    ).order_by(User.last_name, User.first_name, User.id).all()
    for student in students:
        writer.writerow([
            student.email,
            student.first_name,
            student.last_name,
            student.album_number or "",
            student.speciality or "",
            student.study_mode or "stacjonarne",
            student.gender or infer_gender(student.first_name),
            student.semester or "",
            student.study_year or "",
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
    internships = Internship.query.filter_by(is_archived=0).order_by(
        Internship.academic_year.desc(),
        Internship.id.desc(),
    ).limit(300).all()
    invitation_targets = []
    for internship in internships:
        label = (
            f"{internship.academic_year} · {internship.student.full_name} "
            f"({internship.student.album_number or 'bez albumu'})"
        )
        invitation_targets.append({
            "value": f"internship:{internship.id}",
            "label": f"{label} · cała praktyka",
        })
        for part in internship.parts:
            invitation_targets.append({
                "value": f"part:{part.id}",
                "label": f"{label} · część {part.part_number}: {part.name}",
            })
    config_values = {
        row.key: row.value
        for row in AppConfig.query.filter(
            AppConfig.key.in_([
                "semester_summer_start_month",
                "semester_winter_start_month",
            ])
        ).all()
    }
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
        "zopz_invitations": ZopzInvitation.query.order_by(
            ZopzInvitation.created_at.desc(),
        ).limit(100).all(),
        "invitation_targets": invitation_targets,
        "academic_years": sorted({
            row[0]
            for row in db.session.query(Internship.academic_year).distinct().all()
        } | {current_academic_year()}, reverse=True),
        "months": MONTHS_PL,
        "summer_month": int(
            config_values.get("semester_summer_start_month", 3)
        ),
        "winter_month": int(
            config_values.get("semester_winter_start_month", 10)
        ),
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


def _invitation_target(raw_target):
    try:
        target_type, raw_id = raw_target.split(":", 1)
        target_id = int(raw_id)
    except (AttributeError, TypeError, ValueError):
        raise InvitationError("Wybierz praktykę lub jej część.") from None

    if target_type == "internship":
        internship = db.session.get(Internship, target_id)
        part = None
    elif target_type == "part":
        part = db.session.get(InternshipPart, target_id)
        internship = part.internship if part is not None else None
    else:
        internship = None
        part = None
    if internship is None or internship.is_archived:
        raise InvitationError("Wybrana praktyka nie istnieje lub jest zarchiwizowana.")
    return internship, part


@admin_bp.route("/zaproszenia-zopz", methods=["POST"])
@login_required
def create_zopz_invitation_route():
    _admin_required()
    try:
        internship, part = _invitation_target(request.form.get("target"))
        invitation, raw_token = create_zopz_invitation(
            email=request.form.get("email", ""),
            first_name=request.form.get("first_name", ""),
            last_name=request.form.get("last_name", ""),
            internship=internship,
            internship_part=part,
            invited_by=current_user,
        )
        db.session.commit()
    except InvitationError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("admin.dashboard"))

    invitation_path = url_for(
        "auth.accept_zopz_invitation_route",
        token=raw_token,
    )
    public_base_url = current_app.config.get("PUBLIC_BASE_URL")
    invitation_url = (
        f"{public_base_url}{invitation_path}"
        if public_base_url
        else url_for(
            "auth.accept_zopz_invitation_route",
            token=raw_token,
            _external=True,
        )
    )
    email_sent = False
    email_error = None
    try:
        email_sent = send_invitation_email(invitation, invitation_url)
    except (OSError, smtplib.SMTPException) as exc:
        current_app.logger.exception("Could not send ZOPZ invitation email")
        email_error = str(exc)
    return render_template(
        "zopz_invitation_created.html",
        invitation=invitation,
        invitation_url=invitation_url,
        email_sent=email_sent,
        email_error=email_error,
    )


@admin_bp.route("/zaproszenia-zopz/<int:invitation_id>/uniewaznij", methods=["POST"])
@login_required
def revoke_zopz_invitation_route(invitation_id):
    _admin_required()
    invitation = db.session.get(ZopzInvitation, invitation_id)
    if invitation is None:
        abort(404)
    try:
        revoke_zopz_invitation(invitation)
        db.session.commit()
    except InvitationError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    else:
        flash("Zaproszenie zostało unieważnione.", "success")
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
        "study_mode;gender;semester;study_year\r\n"
        "student@uczelnia.pl;Jan;Kowalski;25001;"
        "Administracja systemów i sieci komputerowych (ASiSK);"
        "stacjonarne;M;6;3\r\n"
    ).encode("utf-8")
    return send_file(
        io.BytesIO(content),
        as_attachment=True,
        download_name="wzor_importu_studentow.csv",
        mimetype="text/csv; charset=utf-8",
    )


@admin_bp.route("/eksport-studentow.csv")
@login_required
def export_students():
    _admin_required()
    content = students_export_csv()
    log_action(
        "export",
        "students_csv",
        after={"count": User.query.filter_by(role="student", is_active=1).count()},
        commit=True,
    )
    return send_file(
        io.BytesIO(content),
        as_attachment=True,
        download_name="studenci.csv",
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
