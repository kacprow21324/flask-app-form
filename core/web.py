from flask import (
    Blueprint, abort, current_app, render_template, request, redirect, session,
    url_for, flash, send_file,
)
from flask_login import login_required, login_user, current_user
from datetime import date as _date, datetime
import os
import uuid
from sqlalchemy import or_

from core.models import (
    db, User, LearningEffect,
    Specialty, Attachment, RoleFormAccess, StudentWorkflowStep,
    SurveyQuestion, SurveyOption, AppConfig, DocumentWorkflow,
    ArchivePackage, GeneratedDocument, Internship, InternshipPart, Notification,
)
from core import workflow
from core import validators
from core.store import (
    delete_form, delete_student_forms, get_form, get_form_revision, get_student_forms,
    load_data, save_form,
)
from core.auth import (
    authenticate_user, get_debug_login_accounts, oauth_provider_status,
    start_user_session, AuthError,
)
from core.audit import log_action
from core.documents import (
    archive_pdf,
    find_generated_document,
    generated_document_path,
    source_checksum,
)
from core.grades import (
    GradeValidationError,
    calculate_final_grade,
    grade_to_text,
    require_approved_diary,
    store_final_grade,
)
from core.gender import gender_for_student, infer_gender, normalize_gender
from core.internships import (
    current_academic_year,
    ensure_internship,
    ensure_default_part,
    get_or_create_internship,
    normalize_academic_year,
    save_internship_part,
    sync_internship_totals,
)
from core.notifications import notify_user, unread_for
from core.progress import summarize_progress
from core.practice_workflow import (
    OPTIONAL_EXPERIENCE_STEPS,
    completion_errors,
    form_visible_for_student,
    overview_phases,
    practice_result,
    step_access,
    step_states,
    steps_for_student,
    unmet_previous_steps,
)
from weasyprint import HTML as WeasyprintHTML
from core.retention import (
    anonymize_expired_archive,
    archive_package_path,
    create_student_archive,
    verify_archive_package,
)
main_bp = Blueprint("main", __name__)
documents_bp = Blueprint("documents", __name__)
forms_bp = Blueprint("forms", __name__)
operations_bp = Blueprint("operations", __name__)


class _BlueprintRouter:
    """Rozdziela istniejące dekoratory tras według obszaru funkcjonalnego."""

    @staticmethod
    def route(rule, *args, **kwargs):
        if rule.startswith("/zal"):
            blueprint = forms_bp
        elif (
            rule.startswith("/dokumenty-wygenerowane/")
            or rule.startswith("/archiwa/")
            or (
                rule.startswith("/student/")
                and any(part in rule for part in (
                    "/zal6/plik/",
                    "/recenzuj",
                    "/pobierz",
                    "/drukuj",
                    "/formularz",
                    "/wyslij",
                    "/zatwierdz",
                    "/odrzuc",
                    "/zakoncz",
                ))
            )
        ):
            blueprint = documents_bp
        elif rule.startswith((
            "/praktyki",
            "/przydzialy",
            "/konfiguracja",
            "/admin/wypelnij/",
        )):
            blueprint = operations_bp
        else:
            blueprint = main_bp
        return blueprint.route(rule, *args, **kwargs)

    @staticmethod
    def template_filter(name=None):
        return main_bp.app_template_filter(name)

    @staticmethod
    def context_processor(function):
        return main_bp.app_context_processor(function)

    @staticmethod
    def before_request(function):
        return main_bp.before_app_request(function)


app = _BlueprintRouter()

@app.template_filter('plec')
def detect_gender(name):
    explicit = normalize_gender(name)
    return explicit or infer_gender(name)

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR    = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")  # pliki załączników zostają na dysku; treść formularzy jest w MongoDB

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx',
    'txt', 'csv',
    'zip',
    'png', 'jpg', 'jpeg',
    'xlsx', 'xls',
    'py', 'js', 'ts', 'java', 'c', 'cpp', 'h', 'cs', 'go', 'rb', 'sh',
}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB

# ZOPZ widzi tylko formularze, w których bezpośrednio uczestniczy
ROLE_VISIBLE_FORMS = {
    'zopz': {'zal2a', 'zal3', 'zal4', 'zal6', 'zal7a'},
}

STATUS_LABELS = {
    'draft':    ('Szkic',            'status-draft'),
    'pending':  ('Oczekuje',         'status-pending'),
    'approved': ('Zatwierdzone',     'status-approved'),
    'rejected': ('Odrzucono',        'status-rejected'),
}


# ── Gettery danych statycznych z bazy ────────────────────────────────────────

def get_specialties():
    return [s.name for s in Specialty.query.order_by(Specialty.sort_order).all()]


def get_attachments():
    return [
        {'key': a.key, 'nr': a.nr, 'title': a.title}
        for a in Attachment.query.order_by(Attachment.sort_order).all()
    ]


def get_document_workflow():
    wf = {}
    for a in Attachment.query.all():
        wf[a.key] = {
            'reviewer': a.reviewer_role,
            'reviewer_label': a.reviewer_label or '',
        }
    return wf


def get_role_form_access():
    result = {}
    for r in RoleFormAccess.query.all():
        result.setdefault(r.role, set()).add(r.form_key)
    return result


def get_student_workflow():
    return [
        {
            'step': s.step, 'key': s.key, 'nr': s.nr,
            'title': s.title, 'when': s.when_label, 'hint': s.hint,
        }
        for s in StudentWorkflowStep.query.order_by(StudentWorkflowStep.step).all()
    ]


def get_survey_questions():
    return [q.text for q in SurveyQuestion.query.order_by(SurveyQuestion.nr).all()]


def get_survey_options():
    return [o.label for o in SurveyOption.query.order_by(SurveyOption.sort_order).all()]


def get_config_value(key, default=None):
    cfg = AppConfig.query.filter_by(key=key).first()
    return cfg.value if cfg else (str(default) if default is not None else None)


def _set_config_value(key, value, label=None):
    cfg = AppConfig.query.filter_by(key=key).first()
    if cfg:
        cfg.value = str(value)
        if label:
            cfg.label = label
    else:
        db.session.add(AppConfig(key=key, value=str(value), label=label))
    db.session.commit()


def get_current_semester():
    """Zwraca aktualny rok akademicki z semestrem, np. '2025/2026 letni'."""
    today = _date.today()
    m, y = today.month, today.year
    summer_start = int(get_config_value('semester_summer_start_month', 3))
    winter_start = int(get_config_value('semester_winter_start_month', 10))
    if summer_start <= m < winter_start:
        return f"{y - 1}/{y} letni"
    elif m >= winter_start:
        return f"{y}/{y + 1} zimowy"
    else:
        return f"{y - 1}/{y} zimowy"


# ── Helpers ───────────────────────────────────────────────────────────────────
# Odczyty zbiorcze korzystają z load_data(); zapisy są zawsze punktowe.

def get_effects():
    return LearningEffect.query.order_by(LearningEffect.nr).all()


def _build_notifications():
    """Zwraca listę aktywnych powiadomień dla zalogowanego użytkownika."""
    return [
        {
            'type': item.type,
            'text': item.title,
            'detail': item.message,
            'url': url_for('notification_open', notification_id=item.id),
        }
        for item in unread_for(current_user)
    ]


def _pending_reviews(album_numbers=None):
    """Zwraca dokumenty oczekujące na decyzję zalogowanego recenzenta."""
    if current_user.role not in ("uopz", "zopz", "dziekanat", "admin"):
        return []

    accessible = accessible_album_numbers()
    if album_numbers is not None:
        accessible &= set(album_numbers)
    if not accessible:
        return []

    attachments = {item["key"]: item for item in get_attachments()}
    document_workflow = get_document_workflow()
    rows = (
        DocumentWorkflow.query.filter(
            DocumentWorkflow.status == "pending",
            DocumentWorkflow.album_number.in_(accessible),
        )
        .order_by(DocumentWorkflow.updated_at.asc(), DocumentWorkflow.id.asc())
        .all()
    )
    users_by_album = {
        user.album_number: user
        for user in User.query.filter(
            User.role == "student",
            User.album_number.in_(accessible),
        ).all()
    }

    pending = []
    for row in rows:
        wf = document_workflow.get(row.form_key, {})
        reviewer = wf.get("reviewer")
        if not reviewer or (
            current_user.role != "admin" and current_user.role != reviewer
        ):
            continue
        att = attachments.get(row.form_key)
        if att is None:
            continue
        student = users_by_album.get(row.album_number)
        pending.append({
            "nr_albumu": row.album_number,
            "student_name": student.full_name if student else row.album_number,
            "zal_key": row.form_key,
            "att": att,
            "reviewer_label": wf.get("reviewer_label", ""),
            "updated_at": row.updated_at,
        })
    return pending


def _notify_reviewers(nr_albumu, zal_key):
    meta = next((a for a in get_attachments() if a["key"] == zal_key), {})
    reviewer = get_document_workflow().get(zal_key, {}).get("reviewer")
    if not reviewer:
        return
    student = User.query.filter_by(album_number=nr_albumu).first()
    title = f"Zał. {meta.get('nr', zal_key)} - do zatwierdzenia"
    link = url_for("student_detail", nr_albumu=nr_albumu) + f"#doc-{zal_key}"
    for user in User.query.filter(
        User.role.in_([reviewer, "admin"]), User.is_active == 1,
    ).all():
        notify_user(
            user, "pending", title, getattr(student, "full_name", nr_albumu), link,
            entity_type="document",
            dedupe_key=f"pending:{nr_albumu}:{zal_key}:{user.id}",
        )
    db.session.commit()


def _notify_student(nr_albumu, zal_key, status, message):
    student = User.query.filter_by(
        role="student", album_number=nr_albumu,
    ).first()
    meta = next((a for a in get_attachments() if a["key"] == zal_key), {})
    if student is not None:
        Notification.query.filter(
            Notification.recipient_id == student.id,
            Notification.related_entity_type == "document",
            Notification.type != status,
            Notification.dedupe_key.like(f"%:{nr_albumu}:{zal_key}:%"),
            Notification.is_read == 0,
        ).update(
            {"is_read": 1, "read_at": datetime.utcnow()},
            synchronize_session=False,
        )
    notify_user(
        student,
        status,
        f"Zał. {meta.get('nr', zal_key)} - "
        + ("zatwierdzony" if status == "approved" else "wymaga poprawy"),
        message,
        url_for("student_detail", nr_albumu=nr_albumu) + f"#doc-{zal_key}",
        entity_type="document",
        dedupe_key=f"{status}:{nr_albumu}:{zal_key}:{getattr(student, 'id', 0)}",
        commit=True,
    )


def _close_reviewer_notifications(nr_albumu, zal_key):
    Notification.query.filter(
        Notification.dedupe_key.like(f"pending:{nr_albumu}:{zal_key}:%"),
        Notification.is_read == 0,
    ).update(
        {"is_read": 1, "read_at": datetime.utcnow()},
        synchronize_session=False,
    )
    db.session.commit()


@app.context_processor
def inject_notifications():
    if not current_user.is_authenticated:
        return {'notifications': [], 'current_semester': ''}
    try:
        return {
            'notifications': _build_notifications(),
            'current_semester': get_current_semester(),
        }
    except Exception:
        return {'notifications': [], 'current_semester': ''}


def is_valid_full_name(v):
    return validators.is_valid_full_name(v)[0]


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_upload(file, nr_albumu):
    """Zapisuje plik na dysk, zwraca dict z metadanymi lub None przy błędzie."""
    if not file or not file.filename:
        return None
    if not _allowed_file(file.filename):
        return None
    original = os.path.basename(file.filename.replace("\\", "/")).strip()
    if (
        not original
        or len(original) > 255
        or any(ord(char) < 32 for char in original)
    ):
        return None
    ext = original.rsplit('.', 1)[1].lower()
    file_id = uuid.uuid4().hex[:16]
    student_dir = os.path.join(UPLOADS_DIR, nr_albumu)
    os.makedirs(student_dir, exist_ok=True)
    path = _upload_path(nr_albumu, file_id, ext)
    if path is None:
        return None
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return None
    file.save(path)
    return {'id': file_id, 'name': original, 'ext': ext, 'size': size}


def is_digits_only(v):
    return validators.is_valid_album(v)[0]


def can_edit_form(form_key):
    """Czy aktualna rola użytkownika może edytować dany formularz."""
    return form_key in get_role_form_access().get(current_user.role, set())


def accessible_album_numbers():
    if not current_user.is_authenticated:
        return set()
    if current_user.role == "student":
        return {current_user.album_number} if current_user.album_number else set()
    if current_user.role in ("admin", "dziekanat"):
        return {
            row[0] for row in User.query.with_entities(User.album_number)
            .filter(User.role == "student", User.album_number.isnot(None)).all()
        }
    if current_user.role not in ("uopz", "zopz"):
        return set()
    parent_column = (
        Internship.uopz_id
        if current_user.role == "uopz"
        else Internship.zopz_id
    )
    part_column = (
        InternshipPart.uopz_id
        if current_user.role == "uopz"
        else InternshipPart.zopz_id
    )
    parent_albums = {
        row[0] for row in db.session.query(User.album_number)
        .join(Internship, Internship.student_id == User.id)
        .filter(parent_column == current_user.id, User.album_number.isnot(None))
        .distinct().all()
    }
    part_albums = {
        row[0] for row in db.session.query(User.album_number)
        .join(Internship, Internship.student_id == User.id)
        .join(InternshipPart, InternshipPart.internship_id == Internship.id)
        .filter(part_column == current_user.id, User.album_number.isnot(None))
        .distinct().all()
    }
    return parent_albums | part_albums


def can_access_student(nr_albumu):
    if current_user.role in ("admin", "dziekanat"):
        return True
    return str(nr_albumu) in accessible_album_numbers()


def _upload_path(nr_albumu, file_id, ext):
    if (
        not validators.is_valid_album(str(nr_albumu))[0]
        or not file_id.isalnum()
        or ext not in ALLOWED_EXTENSIONS
    ):
        return None
    student_dir = os.path.abspath(os.path.join(UPLOADS_DIR, str(nr_albumu)))
    candidate = os.path.abspath(os.path.join(student_dir, f"{file_id}.{ext}"))
    if os.path.commonpath([student_dir, candidate]) != student_dir:
        return None
    return candidate


@app.before_request
def enforce_object_access():
    if not current_user.is_authenticated:
        return None
    view_args = request.view_args or {}
    nr_albumu = (
        view_args.get("nr_albumu")
        or request.args.get("nr")
        or (request.form.get("nr_albumu") if request.method == "POST" else None)
    )
    if nr_albumu:
        if not validators.is_valid_album(str(nr_albumu))[0]:
            abort(400)
        if not can_access_student(str(nr_albumu)):
            abort(403)
    zal_key = view_args.get("zal_key")
    if (
        current_user.role == "zopz"
        and zal_key
        and zal_key not in ROLE_VISIBLE_FORMS["zopz"]
    ):
        abort(403)
    return None


def guard_form(form_key):
    """Zwraca redirect jeśli rola nie ma dostępu, None jeśli OK."""
    if not can_edit_form(form_key):
        flash("Nie masz uprawnień do edycji tego formularza.", "error")
        return redirect(url_for("index"))
    if current_user.role != "admin":
        nr_albumu = (
            (request.view_args or {}).get("nr_albumu")
            or request.args.get("nr")
            or request.form.get("nr_albumu")
            or (
                current_user.album_number
                if current_user.role == "student"
                else None
            )
        )
        if nr_albumu:
            student = User.query.filter_by(
                role="student",
                album_number=str(nr_albumu),
            ).first()
            if student is not None:
                unmet = unmet_previous_steps(
                    student,
                    form_key,
                    workflow.get_statuses(str(nr_albumu)),
                )
                if unmet:
                    first = unmet[0]
                    if first.get("reason") == "wrong_report":
                        expected = "7a" if first["form_key"] == "zal7a" else "7"
                        flash(
                            f"Dla tego trybu studiów obowiązuje Załącznik {expected}.",
                            "error",
                        )
                    else:
                        flash(
                            f"Ten etap jest zablokowany. Najpierw zakończ "
                            f"Załącznik {first['nr']}: {first['title']}.",
                            "warning",
                        )
                    return redirect(
                        url_for("student_detail", nr_albumu=nr_albumu)
                    )
    return None


def guard_edit(nr_albumu, zal_key):
    """Blokuje edycję gdy dokument oczekuje lub jest zatwierdzony (admin może zawsze)."""
    if _record_is_archived(nr_albumu):
        flash("Rekord jest zarchiwizowany i nie można go edytować.", "error")
        return redirect(url_for('student_detail', nr_albumu=nr_albumu))
    if current_user.role == 'admin':
        return None
    status = workflow.get_status(nr_albumu, zal_key)
    if status in ('pending', 'approved'):
        label = STATUS_LABELS.get(status, (status,))[0]
        flash(f"Dokument jest zablokowany do edycji (status: {label}).", "error")
        return redirect(url_for('student_detail', nr_albumu=nr_albumu))
    return None


def student_nr(form_value):
    """Dla studentów zawsze używa ich własnego numeru albumu."""
    if current_user.role == 'student':
        return current_user.album_number or ''
    return form_value


def _agreement_number(album_number):
    return f"ZAL-1-{album_number}" if album_number else ""


def _capitalize_entry(value):
    value = " ".join((value or "").strip().split())
    return value[:1].upper() + value[1:] if value else ""


def _normalize_person_name(value):
    return " ".join((value or "").strip().split()).title()


def _zal1_prefill(nr=""):
    data = dict(build_prefill(nr) or {})
    album_number = data.get("nr_albumu") or nr
    data.update({
        "nr_porozumienia": _agreement_number(album_number),
        "data": _date.today().isoformat(),
        "liczba_godzin": "960",
    })
    return data


def _delete_attachment(nr_albumu, key):
    if (
        workflow.get_status(nr_albumu, key) == "approved"
        or GeneratedDocument.query.filter_by(
            album_number=nr_albumu,
            form_key=key,
        ).first() is not None
    ):
        abort(
            409,
            description=(
                "Zatwierdzonego lub zarchiwizowanego dokumentu nie można usunąć. "
                "Należy zarchiwizować cały rekord."
            ),
        )
    if delete_form(nr_albumu, key):
        workflow.delete_doc(nr_albumu, key)
    return bool(get_student_forms(nr_albumu))


def _record_is_archived(nr_albumu):
    student = User.query.filter_by(
        role="student", album_number=nr_albumu,
    ).first()
    if student is None:
        return False
    archived = Internship.query.filter_by(
        student_id=student.id, is_archived=1,
    ).first()
    active = Internship.query.filter_by(
        student_id=student.id, is_archived=0,
    ).first()
    return archived is not None and active is None


def build_prefill(nr=''):
    """Returns initial form data with pre-filled fields based on the current user's role."""
    if current_user.role == 'student':
        album = current_user.album_number or ''
        name  = current_user.full_name
        result = {
            'nr_albumu': album,
            'imie_nazwisko': name,
            'rok_akademicki': get_current_semester(),
            'rodzaj_studiow': current_user.study_mode or 'stacjonarne',
            'gender': gender_for_student(current_user),
        }
        if current_user.speciality:
            result['specjalnosc'] = current_user.speciality
        if current_user.semester:
            result['semestr'] = current_user.semester
        return result if (album or name) else None
    base = {'nr_albumu': nr} if nr else {}
    if current_user.role == 'uopz':
        base.update({
            'uczelniany_opiekun': current_user.full_name,
            # podpis_uczelniany / podpis_uopz są auto-stemplowane przez _stamp_sigs, nie przez prefill
        })
    elif current_user.role == 'zopz':
        base.update({
            'zakladowy_opiekun_nazwisko': current_user.full_name,
            'opiekun_imie_nazwisko':      current_user.full_name,
        })
    return base or None


def _record_with_gender(record, nr_albumu):
    """Return a form copy enriched with the student's explicit gender."""
    if record is None:
        return None
    student = User.query.filter_by(
        role="student", album_number=nr_albumu,
    ).first()
    enriched = dict(record)
    enriched["gender"] = gender_for_student(student, record)
    return enriched


# ─── Auto-signatures ──────────────────────────────────────────────────────────

def _auto_sig():
    """Returns 'FirstName LastName · DD.MM.YYYY' for the current logged-in user."""
    return f"{current_user.first_name} {current_user.last_name} · {_date.today().strftime('%d.%m.%Y')}"

# Fields auto-stamped when the given role SAVES a form.
_SAVE_SIGS = {
    ('zal1',  'uopz'):      ['podpis_uczelniany'],
    ('zal1',  'admin'):     ['podpis_uczelniany'],
    ('zal1',  'dziekanat'): ['podpis_dziekanatu'],
    ('zal2',  'uopz'):      ['podpis_uczelniany'],
    ('zal2',  'admin'):     ['podpis_uczelniany'],
    ('zal2',  'zopz'):      ['podpis_zakladowy'],
    ('zal2a', 'student'):   ['podpis_studenta'],
    ('zal2a', 'uopz'):      ['podpis_uczelniany'],
    ('zal2a', 'admin'):     ['podpis_uczelniany'],
    ('zal2a', 'zopz'):      ['podpis_zakladowy'],
    ('zal3',  'zopz'):      ['podpis_zakladowy'],
    ('zal3',  'uopz'):      ['podpis_uczelniany', 'podpis_sprawozdanie'],
    ('zal3',  'admin'):     ['podpis_uczelniany', 'podpis_sprawozdanie'],
    ('zal4a', 'uopz'):      ['podpis_uopz'],
    ('zal4a', 'admin'):     ['podpis_uopz'],
    ('zal4b', 'student'):   ['podpis_studenta'],
    ('zal4b', 'uopz'):      ['podpis_komisji'],
    ('zal4b', 'admin'):     ['podpis_dyrektora'],
    ('zal7',  'student'):   ['podpis_studenta'],
    ('zal7a', 'student'):   ['podpis_studenta'],
    ('zal8',  'dziekanat'): ['podpis_s'],
    ('zal8',  'admin'):     ['podpis_s'],
}

# Fields auto-stamped when a reviewer APPROVES a form.
_APPROVE_SIGS = {
    ('zal1',  'uopz'):  ['podpis_uczelniany'],
    ('zal1',  'admin'): ['podpis_uczelniany'],
    ('zal2',  'zopz'):  ['podpis_zakladowy'],
    ('zal2',  'admin'): ['podpis_zakladowy'],
    ('zal2a', 'zopz'):  ['podpis_zakladowy'],
    ('zal2a', 'uopz'):  ['podpis_uczelniany'],
    ('zal2a', 'admin'): ['podpis_uczelniany'],
    ('zal3',  'uopz'):  ['podpis_uczelniany', 'podpis_sprawozdanie'],
    ('zal3',  'admin'): ['podpis_uczelniany', 'podpis_sprawozdanie'],
}


def _stamp_sigs(record, zal_key, existing):
    """
    Auto-stamps the current user's signature fields in record.
    Preserves existing signatures for fields belonging to other roles.
    existing – the previous MongoDB record (or {} if new).
    """
    sig = _auto_sig()
    role = current_user.role

    # All sig fields managed for this form across all roles
    all_sig_fields = {
        f for (key, _), fields in _SAVE_SIGS.items()
        if key == zal_key for f in fields
    }
    my_fields = set(_SAVE_SIGS.get((zal_key, role), []))

    # Preserve sigs set by other roles
    for field in all_sig_fields - my_fields:
        existing_val = (existing or {}).get(field, '')
        record[field] = existing_val

    # Stamp current user's fields
    for field in my_fields:
        record[field] = sig


def _persist(nr_albumu, key, record, label):
    if not can_access_student(nr_albumu):
        abort(403)
    if _record_is_archived(nr_albumu):
        flash("Rekord jest zarchiwizowany i nie można go zmieniać.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    if current_user.role != "admin":
        student = User.query.filter_by(
            role="student", album_number=nr_albumu,
        ).first()
        if student is not None:
            unmet = unmet_previous_steps(
                student, key, workflow.get_statuses(nr_albumu),
            )
            if unmet:
                first = unmet[0]
                if first.get("reason") == "wrong_report":
                    flash("Wybrano sprawozdanie niezgodne z trybem studiów.", "error")
                else:
                    flash(
                        f"Nie można zapisać tego etapu przed zakończeniem "
                        f"Załącznika {first['nr']}.",
                        "error",
                    )
                return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    student = User.query.filter_by(
        role="student", album_number=nr_albumu,
    ).first()
    if student is not None:
        record["gender"] = gender_for_student(student, record)
    existing = get_form(nr_albumu, key) or {}
    existing_status = workflow.get_status(nr_albumu, key)
    if existing_status in ('pending', 'approved') and current_user.role != 'admin':
        status_label = STATUS_LABELS.get(existing_status, (existing_status,))[0]
        flash(f'Nie mozna zapisac - dokument ma status "{status_label}".', "error")
        return redirect(url_for('student_detail', nr_albumu=nr_albumu))
    transition_done = False
    if existing_status in ('draft', 'rejected'):
        from core.fsm import DocumentFSM
        was_rejected = (existing_status == 'rejected')
        wf_meta = get_document_workflow().get(key, {})
        for mk in ('_field_comments', '_diary_comments'):
            record.pop(mk, None)
        if was_rejected and wf_meta.get('reviewer'):
            # FSM: auto-resubmit (rejected → pending); do_transition obsługuje też log
            DocumentFSM.transition('rejected', 'submit')
            save_form(nr_albumu, key, record)
            workflow.do_transition(nr_albumu, key, 'submit',
                                   reviewer_role=wf_meta.get('reviewer'))
            ensure_internship(
                nr_albumu, key, record,
                document_status="pending", commit=True,
            )
            _notify_reviewers(nr_albumu, key)
            transition_done = True
    else:
        for mk in ('_field_comments', '_diary_comments'):
            if mk in existing:
                record[mk] = existing[mk]

    if not transition_done:
        save_form(nr_albumu, key, record)
        target_status = (
            "draft"
            if existing_status == "approved" and current_user.role == "admin"
            else existing_status
        )
        ensure_internship(
            nr_albumu, key, record, document_status=target_status,
        )
        reviewer_role = get_document_workflow().get(key, {}).get('reviewer')
        action = ('created' if existing_status == 'draft' and not existing else 'updated')
        workflow.set_status(nr_albumu, key, target_status,
                            reviewer_role=reviewer_role, action=action)

    if transition_done:
        reviewer_label = get_document_workflow().get(key, {}).get('reviewer_label', 'recenzenta')
        flash(f"{label} poprawiony/a i wysłany/a ponownie do: {reviewer_label}.", "success")
    else:
        if existing_status == "approved" and current_user.role == "admin":
            flash(
                f"{label} został/a zapisany/a jako szkic i wymaga ponownego zatwierdzenia.",
                "warning",
            )
        else:
            flash(f"{label} został/a zapisany/a.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


# ── Strony ogólne ─────────────────────────────────────────────────────────────

@app.route("/student/<nr_albumu>/zal6/plik/<file_id>")
@login_required
def pobierz_plik_zal6(nr_albumu, file_id):
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    if not file_id.replace('-', '').isalnum() or len(file_id) > 40:
        flash("Nieprawidłowy identyfikator pliku.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    rec = load_data().get(nr_albumu, {}).get('zal6', {})
    meta = next((f for f in rec.get('pliki', []) if f['id'] == file_id), None)
    if not meta:
        flash("Plik nie istnieje.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    path = _upload_path(nr_albumu, file_id, meta.get("ext", ""))
    if path is None or not os.path.exists(path):
        flash("Plik nie istnieje na dysku.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    return send_file(path, as_attachment=True, download_name=meta['name'])


@app.route("/student/<nr_albumu>/zal4b/plik/<file_id>")
@login_required
def pobierz_plik_zal4b(nr_albumu, file_id):
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    if not file_id.replace('-', '').isalnum() or len(file_id) > 40:
        flash("Nieprawidłowy identyfikator pliku.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    rec = load_data().get(nr_albumu, {}).get('zal4b', {})
    meta = next((f for f in rec.get('pliki', []) if f['id'] == file_id), None)
    if not meta:
        flash("Plik nie istnieje.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    path = _upload_path(nr_albumu, file_id, meta.get("ext", ""))
    if path is None or not os.path.exists(path):
        flash("Plik nie istnieje na dysku.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    return send_file(path, as_attachment=True, download_name=meta['name'])


@app.route("/zaliczenie")
@login_required
def zaliczenie():
    role = current_user.role
    if role == 'student':
        nr = current_user.album_number or ''
        student_forms = get_student_forms(nr) if nr else {}
        statuses = workflow.get_statuses(nr) if nr else {}
        return render_template("zaliczenie.html",
            role=role, nr_albumu=nr,
            zal4b_data=student_forms.get('zal4b'),
            zal4a_data=student_forms.get('zal4a'),
            zal4b_status=statuses.get('zal4b'),
            zal4a_status=statuses.get('zal4a'),
            status_labels=STATUS_LABELS,
        )
    student_users = User.query.filter_by(role='student', is_active=1).order_by(
        User.last_name, User.first_name,
    ).all()
    album_numbers = [u.album_number for u in student_users if u.album_number]
    all_wf = (
        DocumentWorkflow.query.filter(
            DocumentWorkflow.album_number.in_(album_numbers),
            DocumentWorkflow.form_key.in_({'zal4a', 'zal4b'}),
        ).all()
        if album_numbers else []
    )
    wf_by_student: dict[str, dict] = {}
    for w in all_wf:
        wf_by_student.setdefault(w.album_number, {})[w.form_key] = w.status
    student_data = []
    for user in student_users:
        nr = user.album_number
        if not nr:
            continue
        s = wf_by_student.get(nr, {})
        student_data.append({
            'nr_albumu': nr,
            'imie_nazwisko': user.full_name,
            'zal4b_status': s.get('zal4b'),
            'zal4a_status': s.get('zal4a'),
        })
    return render_template("zaliczenie.html",
        role=role,
        students=student_data,
        status_labels=STATUS_LABELS,
    )


@app.route("/regulamin")
@login_required
def regulamin():
    return render_template("regulamin.html")


@app.route("/regulamin.pdf")
@login_required
def regulamin_pdf():
    pdf_path = os.path.join(current_app.static_folder, "regulamin.pdf")
    response = send_file(pdf_path, mimetype="application/pdf")
    # Pozwól na osadzenie wyłącznie przez tę samą domenę – setdefault w security.py nie nadpisze tych nagłówków.
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'self'"
    return response


@app.route("/powiadomienia")
@login_required
def powiadomienia():
    try:
        notifs = _build_notifications()
    except Exception:
        notifs = []
    return render_template("powiadomienia.html", notifications=notifs)


@app.route("/do-zatwierdzenia")
@login_required
def do_zatwierdzenia():
    if current_user.role not in ("uopz", "zopz", "dziekanat", "admin"):
        abort(403)
    return render_template(
        "do_zatwierdzenia.html",
        pending_reviews=_pending_reviews(),
    )


@app.route("/powiadomienia/<int:notification_id>")
@login_required
def notification_open(notification_id):
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.recipient_id != current_user.id:
        flash("Powiadomienie nie istnieje.", "error")
        return redirect(url_for("powiadomienia"))
    notification.is_read = 1
    notification.read_at = datetime.utcnow()
    db.session.commit()
    target = notification.link or url_for("powiadomienia")
    if not target.startswith("/") or target.startswith("//"):
        target = url_for("powiadomienia")
    return redirect(target)


@app.route("/obieg")
@login_required
def obieg():
    # Zachowujemy stary adres dla powiadomień i zapisanych zakładek.
    # Widok oraz logika danych są teraz wspólne z dashboardem.
    return index()


@app.route("/przydzialy", methods=["GET", "POST"])
@login_required
def przydzialy():
    if current_user.role not in ("dziekanat", "admin"):
        abort(403)

    requested_year = (
        request.form.get("academic_year")
        if request.method == "POST"
        else request.args.get("rok")
    )
    selected_year = normalize_academic_year(
        requested_year,
        default_current=not requested_year,
    )
    if selected_year is None:
        abort(400, description="Nieprawidłowy rok akademicki.")

    if request.method == "POST":
        try:
            student_id = int(request.form.get("student_id", ""))
        except ValueError:
            abort(400)
        student = db.session.get(User, student_id)
        if student is None or student.role != "student":
            abort(404)

        def selected_supervisor(field_name, role):
            raw_id = request.form.get(field_name, "").strip()
            if not raw_id:
                return None
            try:
                user_id = int(raw_id)
            except ValueError:
                abort(400)
            user = db.session.get(User, user_id)
            if user is None or user.role != role or not user.is_active:
                abort(400)
            return user

        uopz = selected_supervisor("uopz_id", "uopz")
        zopz = selected_supervisor("zopz_id", "zopz")
        internship = get_or_create_internship(student, selected_year)
        db.session.flush()
        old_uopz = internship.uopz
        old_zopz = internship.zopz
        before = {
            "uopz_id": internship.uopz_id,
            "zopz_id": internship.zopz_id,
            "academic_year": internship.academic_year,
        }
        internship.uopz_id = uopz.id if uopz else None
        internship.zopz_id = zopz.id if zopz else None
        after = {
            "uopz_id": internship.uopz_id,
            "zopz_id": internship.zopz_id,
            "academic_year": internship.academic_year,
        }
        if before == after:
            db.session.rollback()
            flash("Przydział nie wymagał zmian.", "info")
            return redirect(url_for(
                "praktyki", tab="opiekunowie", rok=selected_year,
            ))

        log_action(
            "assign",
            "internship",
            internship.id,
            before=before,
            after=after,
        )

        link = url_for("index", rok=selected_year)
        for label, old_user, new_user in (
            ("UOPZ", old_uopz, uopz),
            ("ZOPZ", old_zopz, zopz),
        ):
            if old_user and old_user.id != getattr(new_user, "id", None):
                notify_user(
                    old_user,
                    "assignment",
                    "Zmiana przydziału studenta",
                    f"Nie jesteś już opiekunem {label} studenta {student.full_name}.",
                    url_for("index", rok=selected_year),
                    entity_type="internship",
                    entity_id=internship.id,
                )
            if new_user and new_user.id != getattr(old_user, "id", None):
                notify_user(
                    new_user,
                    "assignment",
                    "Nowy przydział studenta",
                    f"Przypisano Ci studenta {student.full_name} jako {label}.",
                    link,
                    entity_type="internship",
                    entity_id=internship.id,
                )

        if before != after:
            uopz_name = uopz.full_name if uopz else "nie przypisano"
            zopz_name = zopz.full_name if zopz else "nie przypisano"
            notify_user(
                student,
                "assignment",
                "Zaktualizowano opiekunów praktyki",
                f"UOPZ: {uopz_name}; ZOPZ: {zopz_name}.",
                url_for("index", rok=selected_year),
                entity_type="internship",
                entity_id=internship.id,
                dedupe_key=f"internship-assignment-student-{internship.id}",
            )
        db.session.commit()
        flash("Przydział opiekunów został zapisany.", "success")
        return redirect(url_for(
            "praktyki", tab="opiekunowie", rok=selected_year,
        ))

    academic_years = sorted(
        {
            row[0]
            for row in db.session.query(Internship.academic_year).distinct().all()
        } | {current_academic_year()},
        reverse=True,
    )
    students = User.query.filter_by(role="student", is_active=1).order_by(
        User.last_name,
        User.first_name,
    ).all()
    internships = Internship.query.filter_by(academic_year=selected_year).all()
    internship_by_student = {item.student_id: item for item in internships}
    uopz_users = User.query.filter_by(role="uopz", is_active=1).order_by(
        User.last_name,
        User.first_name,
    ).all()
    zopz_users = User.query.filter_by(role="zopz", is_active=1).order_by(
        User.last_name,
        User.first_name,
    ).all()
    return render_template(
        "przydzialy.html",
        students=students,
        internship_by_student=internship_by_student,
        uopz_users=uopz_users,
        zopz_users=zopz_users,
        academic_years=academic_years,
        selected_year=selected_year,
    )


@app.route("/czesci-praktyki", methods=["GET", "POST"])
@login_required
def czesci_praktyki():
    requested_album = (
        current_user.album_number
        if current_user.role == "student"
        else request.values.get("nr", "").strip()
    )
    if not requested_album:
        flash("Wybierz studenta na stronie przydziałów.", "info")
        return redirect(url_for("praktyki", tab="opiekunowie"))
    if not validators.is_valid_album(requested_album)[0]:
        abort(400)
    if not can_access_student(requested_album):
        abort(403)

    student = User.query.filter_by(
        role="student", album_number=requested_album,
    ).first_or_404()
    requested_year = request.values.get("academic_year") or request.args.get("rok")
    selected_year = normalize_academic_year(
        requested_year,
        default_current=not requested_year,
    )
    if selected_year is None:
        abort(400, description="Nieprawidłowy rok akademicki.")

    internship = Internship.query.filter_by(
        student_id=student.id,
        academic_year=selected_year,
    ).first()

    if request.method == "POST":
        if current_user.role not in ("dziekanat", "admin"):
            abort(403)
        if internship is None:
            internship = get_or_create_internship(student, selected_year)
            db.session.flush()

        action = request.form.get("action", "save")
        part = None
        raw_part_id = request.form.get("part_id", "").strip()
        if raw_part_id:
            try:
                part_id = int(raw_part_id)
            except ValueError:
                abort(400)
            part = db.session.get(InternshipPart, part_id)
            if part is None or part.internship_id != internship.id:
                abort(404)

        if action == "cancel":
            if part is None:
                abort(400)
            before = {"status": part.status}
            part.status = "cancelled"
            sync_internship_totals(internship)
            log_action(
                "update",
                "internship_part",
                part.id,
                before=before,
                after={"status": part.status},
            )
            db.session.commit()
            flash("Część praktyki została anulowana.", "success")
            return redirect(url_for(
                "praktyki", tab="czesci", nr=requested_album,
                rok=selected_year,
            ))
        if action != "save":
            abort(400)

        def selected_supervisor(field_name, role):
            raw_id = request.form.get(field_name, "").strip()
            if not raw_id:
                return None
            try:
                user_id = int(raw_id)
            except ValueError:
                abort(400)
            user = db.session.get(User, user_id)
            if user is None or user.role != role or not user.is_active:
                abort(400)
            return user

        before = None
        if part is not None:
            before = {
                "name": part.name,
                "company_id": part.company_id,
                "uopz_id": part.uopz_id,
                "zopz_id": part.zopz_id,
                "start_date": str(part.start_date or ""),
                "end_date": str(part.end_date or ""),
                "planned_hours": part.planned_hours,
                "total_hours": part.total_hours,
                "total_days": part.total_days,
                "status": part.status,
            }
        try:
            part = save_internship_part(
                internship,
                part=part,
                name=request.form.get("name"),
                company_name=request.form.get("company_name"),
                start_date=request.form.get("start_date"),
                end_date=request.form.get("end_date"),
                planned_hours=request.form.get("planned_hours"),
                total_hours=request.form.get("total_hours"),
                total_days=request.form.get("total_days"),
                status=request.form.get("status", "planned"),
                uopz=selected_supervisor("uopz_id", "uopz"),
                zopz=selected_supervisor("zopz_id", "zopz"),
            )
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return redirect(url_for(
                "praktyki", tab="czesci", nr=requested_album,
                rok=selected_year,
            ))

        after = {
            "name": part.name,
            "company_id": part.company_id,
            "uopz_id": part.uopz_id,
            "zopz_id": part.zopz_id,
            "start_date": str(part.start_date or ""),
            "end_date": str(part.end_date or ""),
            "planned_hours": part.planned_hours,
            "total_hours": part.total_hours,
            "total_days": part.total_days,
            "status": part.status,
        }
        log_action(
            "update" if before else "create",
            "internship_part",
            part.id,
            before=before,
            after=after,
        )
        notify_user(
            student,
            "assignment",
            "Zaktualizowano część praktyki",
            f"{part.name}: {part.company.name if part.company else 'bez wskazanego miejsca'}.",
            url_for("praktyki", tab="czesci", rok=selected_year),
            entity_type="internship_part",
            entity_id=part.id,
        )
        db.session.commit()
        flash("Część praktyki została zapisana.", "success")
        return redirect(url_for(
            "praktyki", tab="czesci", nr=requested_album,
            rok=selected_year,
        ))

    if internship is not None and not internship.parts:
        ensure_default_part(internship)
        db.session.commit()

    years = {
        row[0]
        for row in db.session.query(Internship.academic_year)
        .filter(Internship.student_id == student.id)
        .distinct().all()
    } | {current_academic_year()}
    uopz_users = User.query.filter_by(role="uopz", is_active=1).order_by(
        User.last_name, User.first_name,
    ).all()
    zopz_users = User.query.filter_by(role="zopz", is_active=1).order_by(
        User.last_name, User.first_name,
    ).all()
    # Odśwież sumy godzin i dni z zatwierdzonego dziennika
    if internship is not None:
        sync_internship_totals(internship)
        db.session.commit()
    part_status_labels = {
        'planned':   'Planowana',
        'active':    'W trakcie',
        'completed': 'Zakończona',
        'cancelled': 'Anulowana',
    }
    return render_template(
        "czesci_praktyki.html",
        student=student,
        internship=internship,
        parts=list(internship.parts) if internship else [],
        academic_years=sorted(years, reverse=True),
        selected_year=selected_year,
        uopz_users=uopz_users,
        zopz_users=zopz_users,
        can_manage=current_user.role in ("dziekanat", "admin"),
        status_labels=part_status_labels,
        status_labels_wf=STATUS_LABELS,
    )


@app.route("/praktyki", methods=["GET", "POST"])
@login_required
def praktyki():
    tab = request.values.get("tab", "").strip().lower()
    if current_user.role == "student" or tab == "czesci":
        return czesci_praktyki()
    return przydzialy()


@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    if request.method == "POST":
        before = {
            "speciality": current_user.speciality,
            "study_mode": current_user.study_mode,
            "gender": current_user.gender,
            "semester": current_user.semester,
            "study_year": current_user.study_year,
        }
        current_user.gender = (
            normalize_gender(request.form.get("gender"))
            or gender_for_student(current_user)
        )
        if current_user.role == 'student':
            speciality = request.form.get("speciality", "").strip()
            study_mode = request.form.get("study_mode", "stacjonarne").strip()
            current_user.speciality = speciality or None
            current_user.study_mode = study_mode
            current_user.semester = (request.form.get("semester", "").strip() or None)
            current_user.study_year = (request.form.get("study_year", "").strip() or None)
        log_action(
            "update", "user_profile", current_user.id,
            before=before,
            after={
                "speciality": current_user.speciality,
                "study_mode": current_user.study_mode,
                "gender": current_user.gender,
                "semester": current_user.semester,
                "study_year": current_user.study_year,
            },
        )
        db.session.commit()
        flash("Profil zaktualizowany.", "success")
        return redirect(url_for("profil"))
    return render_template("profil.html",
                           specialties=get_specialties())


@app.route("/student/<nr_albumu>/<zal_key>/recenzuj")
@login_required
def formularz_recenzuj(nr_albumu, zal_key):
    """Formularz w trybie recenzji – recenzent zaznacza błędne pola checkboxami."""
    wf = get_document_workflow().get(zal_key, {})
    if current_user.role != wf.get('reviewer') and current_user.role != 'admin':
        flash("Brak uprawnień do recenzji tego dokumentu.", "error")
        return redirect(url_for('student_detail', nr_albumu=nr_albumu))
    rec = get_form(nr_albumu, zal_key)
    if not rec or workflow.get_status(nr_albumu, zal_key) != 'pending':
        flash("Dokument nie oczekuje na zatwierdzenie.", "error")
        return redirect(url_for('student_detail', nr_albumu=nr_albumu))
    effects = get_effects() if zal_key in ('zal2a', 'zal4', 'zal4a', 'zal4b', 'zal6') else []
    tpl = 'zal7.html' if zal_key == 'zal7a' else f'{zal_key}.html'
    return render_template(tpl,
        data=_record_with_gender(rec, nr_albumu), edit_nr=nr_albumu,
        specialties=get_specialties(), effects=effects,
        questions=get_survey_questions(), options=get_survey_options(),
        nr_locked=True, sn=(zal_key == 'zal7a'),
        review_mode=True,
        diary_comments=[],
        reject_url=url_for('odrzuc_dokument', nr_albumu=nr_albumu, zal_key=zal_key),
        back_url=url_for('student_detail', nr_albumu=nr_albumu),
    )


@app.route("/student/<nr_albumu>/<zal_key>/pobierz")
@login_required
def pobierz_pdf(nr_albumu, zal_key):
    """Generuje PDF z szablonu HTML wydruku (WeasyPrint)."""
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    attachments = get_attachments()
    valid_keys = {a["key"] for a in attachments}
    if zal_key not in valid_keys:
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    record = get_form(nr_albumu, zal_key)
    if not record:
        flash("Brak danych do pobrania.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    effects = get_effects()
    effect_map = {e.nr: e.opis for e in effects}
    att = next((a for a in attachments if a["key"] == zal_key), None)
    student_user = User.query.filter_by(role="student", album_number=nr_albumu).first()
    pdf_record = dict(record)
    pdf_record["gender"] = gender_for_student(student_user, record)
    ctx = dict(
        data=pdf_record, nr_albumu=nr_albumu, att=att,
        effects=effects, effect_map=effect_map,
        questions=get_survey_questions(), options=get_survey_options(),
        specialties=get_specialties(), sn=(zal_key == "zal7a"),
    )
    import io
    tpl = 'zal7.html' if zal_key == 'zal7a' else f'{zal_key}.html'
    try:
        html_str = render_template(f"print/{tpl}", **ctx)
    except Exception as exc:
        current_app.logger.error("HTML print template error: %s", exc)
        flash("Brak szablonu wydruku dla tego załącznika.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    try:
        buf = io.BytesIO()
        WeasyprintHTML(string=html_str, base_url=request.host_url).write_pdf(buf)
        buf.seek(0)
    except Exception as exc:
        current_app.logger.error("WeasyPrint PDF error: %s", exc)
        flash("Błąd generowania PDF. Spróbuj ponownie.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    filename = f"Zal_{att['nr']}_{nr_albumu}.pdf" if att else f"{zal_key}_{nr_albumu}.pdf"
    from flask import Response
    return Response(
        buf.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _document_internship_part(internship, record, form_key):
    if internship is None or form_key == "zal8":
        return None
    raw_part_id = record.get("internship_part_id")
    if raw_part_id:
        try:
            part_id = int(raw_part_id)
        except (TypeError, ValueError):
            part_id = None
        if part_id is not None:
            part = db.session.get(InternshipPart, part_id)
            if part is not None and part.internship_id == internship.id:
                return part
    active_parts = [
        part for part in internship.parts if part.status != "cancelled"
    ]
    return active_parts[0] if len(active_parts) == 1 else None


def _send_archived_document(document, path):
    document.download_count = (document.download_count or 0) + 1
    log_action(
        "download",
        "generated_document",
        document.id,
        after={
            "document_version": document.document_version,
            "source_revision": document.source_revision,
        },
    )
    db.session.commit()
    return send_file(
        path,
        as_attachment=True,
        download_name=document.file_name,
        mimetype=document.mime_type,
    )


@app.route("/dokumenty-wygenerowane/<int:document_id>/pobierz")
@login_required
def pobierz_wersje_pdf(document_id):
    document = db.session.get(GeneratedDocument, document_id)
    if document is None:
        abort(404)
    if not can_access_student(document.album_number):
        abort(403)
    if (
        current_user.role == "zopz"
        and document.form_key not in ROLE_VISIBLE_FORMS["zopz"]
    ):
        abort(403)
    try:
        path = generated_document_path(document, DATA_DIR)
    except ValueError:
        abort(500)
    if not os.path.isfile(path):
        abort(410, description="Plik wersji archiwalnej nie istnieje.")
    return _send_archived_document(document, path)


@app.route("/student/<nr_albumu>/<zal_key>/drukuj")
@login_required
def drukuj(nr_albumu, zal_key):
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    attachments = get_attachments()
    valid_keys = {a["key"] for a in attachments}
    if zal_key not in valid_keys:
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    record = get_form(nr_albumu, zal_key)
    if not record:
        flash("Brak danych do wydruku.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    effects = get_effects()
    effect_map = {e.nr: e.opis for e in effects}
    att = next((a for a in attachments if a["key"] == zal_key), None)
    sn = (zal_key == "zal7a")
    student_user = User.query.filter_by(
        role="student", album_number=nr_albumu,
    ).first()
    print_record = dict(record)
    print_record["gender"] = gender_for_student(student_user, record)
    return render_template(f"print/{zal_key}.html",
        data=print_record, nr_albumu=nr_albumu, att=att,
        effects=effects, effect_map=effect_map,
        questions=get_survey_questions(), options=get_survey_options(),
        specialties=get_specialties(), sn=sn)


@app.route("/student/<nr_albumu>/<zal_key>/formularz")
@login_required
def formularz_podglad(nr_albumu, zal_key):
    """Podgląd wypełnionego formularza w trybie tylko do odczytu."""
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    attachments = get_attachments()
    valid_keys = {a["key"] for a in attachments}
    if zal_key not in valid_keys:
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    store = load_data()
    existing = store.get(nr_albumu, {}).get(zal_key)
    if not existing:
        flash("Formularz nie został jeszcze wypełniony.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    effects = get_effects() if zal_key in ('zal2a', 'zal4', 'zal4a', 'zal4b', 'zal6') else []
    tpl = 'zal7.html' if zal_key == 'zal7a' else f'{zal_key}.html'
    return render_template(tpl,
        data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu,
        specialties=get_specialties(), effects=effects,
        questions=get_survey_questions(), options=get_survey_options(),
        nr_locked=True, sn=(zal_key == 'zal7a'),
        readonly=True)


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        try:
            user = authenticate_user(email, password)
            session.clear()
            login_user(user)
            start_user_session(user)
            return redirect(url_for("index"))
        except AuthError as exc:
            flash(str(exc), "error")
    return render_template(
        "login.html",
        debug_login_accounts=get_debug_login_accounts(),
        oauth_providers=oauth_provider_status(),
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    role = current_user.role
    attachments = get_attachments()
    if role == "zopz":
        attachments = [
            item for item in attachments
            if item["key"] in ROLE_VISIBLE_FORMS["zopz"]
        ]
    editable = get_role_form_access().get(role, set())

    if role == 'student':
        nr = current_user.album_number or ''
        student_forms = get_student_forms(nr) if nr else {}
        filled = [a["key"] for a in attachments if a["key"] in student_forms]
        name = ""
        for key in ("zal1", "zal2a", "zal6", "zal7", "zal7a"):
            if key in student_forms:
                name = student_forms[key].get("imie_nazwisko", "")
                if name:
                    break
        student_statuses = workflow.get_statuses(nr)
        workflow_steps = []
        for step in step_states(current_user, student_statuses):
            workflow_steps.append({
                **step,
                "done": step["complete"],
                "filled": step["key"] in student_forms,
                "when": f"Faza {step['phase']}",
            })
        internship = Internship.query.filter_by(
            student_id=current_user.id,
            is_archived=0,
        ).order_by(Internship.id.desc()).first()
        return render_template("index.html",
            role=role, nr_albumu=nr, student_forms=student_forms,
            filled=filled, attachments=attachments,
            workflow=workflow_steps, name=name, editable_forms=editable,
            status_labels=STATUS_LABELS,
            practice_state=practice_result(
                current_user, student_statuses, internship,
            ),
        )

    requested_year = request.args.get("rok")
    selected_year = normalize_academic_year(
        requested_year,
        default_current=not requested_year,
    )
    if selected_year is None:
        abort(400, description="Nieprawidłowy rok akademicki.")

    years_query = db.session.query(Internship.academic_year).distinct()
    if role == "uopz":
        years_query = years_query.filter(or_(
            Internship.uopz_id == current_user.id,
            Internship.parts.any(InternshipPart.uopz_id == current_user.id),
        ))
    elif role == "zopz":
        years_query = years_query.filter(or_(
            Internship.zopz_id == current_user.id,
            Internship.parts.any(InternshipPart.zopz_id == current_user.id),
        ))
    academic_years = sorted(
        {row[0] for row in years_query.all()} | {current_academic_year()},
        reverse=True,
    )
    internships_query = Internship.query.filter_by(academic_year=selected_year)
    if role == "uopz":
        internships_query = internships_query.filter(or_(
            Internship.uopz_id == current_user.id,
            Internship.parts.any(InternshipPart.uopz_id == current_user.id),
        ))
    elif role == "zopz":
        internships_query = internships_query.filter(or_(
            Internship.zopz_id == current_user.id,
            Internship.parts.any(InternshipPart.zopz_id == current_user.id),
        ))
    internships = internships_query.all()
    internship_by_student = {item.student_id: item for item in internships}

    users_query = User.query.filter_by(role="student", is_active=1)
    if role in ("uopz", "zopz"):
        users_query = users_query.filter(User.id.in_(set(internship_by_student)))
    student_users = users_query.order_by(User.last_name, User.first_name).all()

    visible_keys = {item["key"] for item in attachments}
    album_numbers = [user.album_number for user in student_users if user.album_number]
    all_wf = (
        DocumentWorkflow.query.filter(
            DocumentWorkflow.album_number.in_(album_numbers),
            DocumentWorkflow.form_key.in_(visible_keys),
        ).all()
        if album_numbers else []
    )
    wf_by_student = {}
    wf_rows_by_student = {}
    for r in all_wf:
        wf_by_student.setdefault(r.album_number, {})[r.form_key] = r.status
        wf_rows_by_student.setdefault(r.album_number, []).append(r)

    students = []
    for user in student_users:
        nr = user.album_number
        student_visible_keys = {
            key for key in visible_keys if form_visible_for_student(user, key)
        }
        rows = [
            row for row in wf_rows_by_student.get(nr, [])
            if row.form_key in student_visible_keys
        ]
        sw = {
            key: status for key, status in wf_by_student.get(nr, {}).items()
            if key in student_visible_keys
        }
        progress = summarize_progress(
            rows,
            len(student_visible_keys),
            internship=internship_by_student.get(user.id),
            reviewer_role=role,
        )
        students.append({
            "nr_albumu": nr,
            "imie_nazwisko": user.full_name,
            "speciality": user.speciality or "",
            "study_mode": user.study_mode or "stacjonarne",
            "filled": list(sw),
            "statuses": sw,
            "document_count": len(student_visible_keys),
            "count": progress["started"],
            "approved": progress["approved"],
            "pending": progress["pending"],
            "rejected": progress["rejected"],
            "hours": progress["hours"],
            "days": progress["days"],
            "pending_for_role": progress["pending_for_role"],
            "internship": internship_by_student.get(user.id),
            "zal8_status": sw.get("zal8"),
        })

    pending_reviews = _pending_reviews(album_numbers)
    attachment_map = {item["key"]: item for item in attachments}
    workflow_phases = []
    for phase in overview_phases():
        keys = [key for key in phase["keys"] if key in attachment_map]
        if keys:
            workflow_phases.append({**phase, "keys": keys})

    return render_template("index.html",
        role=role, students=students, attachments=attachments, editable_forms=editable,
        pending_reviews=pending_reviews, selected_year=selected_year,
        academic_years=academic_years, attachment_map=attachment_map,
        workflow_phases=workflow_phases, status_labels=STATUS_LABELS)


# ── Szczegóły studenta ────────────────────────────────────────────────────────

@app.route("/student/<nr_albumu>")
@login_required
def student_detail(nr_albumu):
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu do tego rekordu.", "error")
        return redirect(url_for("index"))
    student_user = User.query.filter_by(
        role="student", album_number=nr_albumu, is_active=1,
    ).first()
    if student_user is None:
        flash("Nie znaleziono aktywnego konta studenta.", "error")
        return redirect(url_for("index"))
    data = load_data()
    student = data.get(nr_albumu, {})
    effect_map = {e.nr: e.opis for e in get_effects()}
    all_atts = get_attachments()
    visible_keys = ROLE_VISIBLE_FORMS.get(current_user.role)
    filtered_atts = [
        a for a in all_atts
        if (visible_keys is None or a['key'] in visible_keys)
        and form_visible_for_student(student_user, a["key"])
    ]
    optional_keys = {"zal4a", "zal4b"}
    if current_user.role == "student":
        document_sections = [
            {
                "title": "Standardowa ścieżka praktyki",
                "description": "Dokumenty realizowane zgodnie z kolejnością faz.",
                "attachments": [
                    item for item in filtered_atts if item["key"] not in optional_keys
                ],
            },
            {
                "title": "Zaliczenie przez doświadczenie zawodowe",
                "description": (
                    "Załącznik 4b pozwala złożyć wniosek o zaliczenie praktyki "
                    "na podstawie udokumentowanego doświadczenia zawodowego."
                ),
                "attachments": [
                    item for item in filtered_atts if item["key"] in optional_keys
                ],
            },
        ]
    else:
        document_sections = [{
            "title": "Dokumenty",
            "description": "",
            "attachments": filtered_atts,
        }]
    att_nr = {a['key']: a['nr'] for a in all_atts}
    raw_logs = workflow.get_logs(nr_albumu)
    logs_by_key = {}
    approval_by_key = {}
    for ev in raw_logs:
        logs_by_key.setdefault(ev.form_key, []).append(ev)
        if ev.action in ("approve", "approved") and ev.form_key not in approval_by_key:
            approval_by_key[ev.form_key] = ev
    workflow_states = {
        row.form_key: row
        for row in DocumentWorkflow.query.filter_by(album_number=nr_albumu).all()
    }
    statuses = {
        key: row.status for key, row in workflow_states.items()
    }
    internship = (
        Internship.query.filter_by(
            student_id=student_user.id,
            is_archived=0,
        ).order_by(Internship.id.desc()).first()
        if student_user is not None else None
    )
    workflow_access = (
        step_access(student_user, statuses)
        if student_user is not None else {}
    )
    generated_versions = {}
    for document in (
        GeneratedDocument.query.filter_by(album_number=nr_albumu)
        .order_by(
            GeneratedDocument.form_key,
            GeneratedDocument.document_version.desc(),
            GeneratedDocument.id.desc(),
        )
        .all()
    ):
        generated_versions.setdefault(document.form_key, []).append(document)
    archive_packages = (
        ArchivePackage.query.filter_by(original_album_number=nr_albumu)
        .order_by(ArchivePackage.package_version.desc())
        .all()
    )
    record_archived = _record_is_archived(nr_albumu)
    return render_template("podglad.html",
        nr_albumu=nr_albumu,
        student=student,
        attachments=filtered_atts,
        document_sections=document_sections,
        effect_map=effect_map,
        editable_forms=get_role_form_access().get(current_user.role, set()),
        user_role=current_user.role,
        document_workflow=get_document_workflow(),
        workflow_states=workflow_states,
        status_labels=STATUS_LABELS,
        logs_by_key=logs_by_key,
        approval_by_key=approval_by_key,
        generated_versions=generated_versions,
        archive_packages=archive_packages,
        record_archived=record_archived,
        att_nr=att_nr,
        workflow_access=workflow_access,
        practice_state=(
            practice_result(student_user, statuses, internship)
            if student_user is not None
            else {"code": "in_progress", "label": "Praktyka w toku"}
        ),
        optional_experience_steps=OPTIONAL_EXPERIENCE_STEPS,
    )


@app.route("/student/<nr_albumu>/usun", methods=["POST"])
@login_required
def student_delete(nr_albumu):
    if current_user.role not in ('admin', 'dziekanat'):
        flash("Brak uprawnień do archiwizacji rekordów studenta.", "error")
        return redirect(url_for("index"))
    student = User.query.filter_by(
        role="student", album_number=nr_albumu,
    ).first_or_404()
    try:
        package, _ = create_student_archive(
            student=student,
            base_dir=DATA_DIR,
            actor=current_user,
            retention_years=int(get_config_value("data_retention_years", 10)),
            hash_salt=current_app.config["SECRET_KEY"],
        )
    except (ValueError, FileNotFoundError) as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    log_action(
        "archive",
        "student_record",
        package.id,
        before={"album_number": nr_albumu},
        after={
            "package_version": package.package_version,
            "retention_until": package.retention_until.isoformat(),
            "checksum_sha256": package.checksum_sha256,
        },
    )
    db.session.commit()
    flash(
        "Rekord został zarchiwizowany. Dane źródłowe pozostają tylko do odczytu "
        "do końca okresu retencji.",
        "success",
    )
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


@app.route("/archiwa/<int:package_id>/pobierz")
@login_required
def pobierz_archiwum(package_id):
    if current_user.role not in ("admin", "dziekanat"):
        abort(403)
    package = db.session.get(ArchivePackage, package_id)
    if package is None:
        abort(404)
    if package.status != "active" or not verify_archive_package(package, DATA_DIR):
        abort(410, description="Pakiet archiwalny nie istnieje lub jest uszkodzony.")
    path = archive_package_path(package, DATA_DIR)
    log_action(
        "download",
        "archive_package",
        package.id,
        after={"checksum_sha256": package.checksum_sha256},
    )
    db.session.commit()
    return send_file(
        path,
        as_attachment=True,
        download_name=package.file_name,
        mimetype="application/zip",
    )


@app.route("/archiwa/<int:package_id>/anonimizuj", methods=["POST"])
@login_required
def anonimizuj_archiwum(package_id):
    if current_user.role != "admin":
        abort(403)
    package = db.session.get(ArchivePackage, package_id)
    if package is None:
        abort(404)
    try:
        changed = anonymize_expired_archive(package, base_dir=DATA_DIR)
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("index"))
    if changed:
        log_action(
            "anonymize",
            "archive_package",
            package.id,
            after={"album_hash": package.album_hash, "status": package.status},
        )
        db.session.commit()
        flash("Dane zostały zanonimizowane i usunięte po retencji.", "success")
    return redirect(url_for("index"))


# ── Workflow: wysyłanie / zatwierdzanie / odrzucanie ─────────────────────────

@app.route("/student/<nr_albumu>/<zal_key>/wyslij", methods=["POST"])
@login_required
def wyslij_do_oceny(nr_albumu, zal_key):
    from core.fsm import DocumentFSM, InvalidTransition
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    wf = get_document_workflow().get(zal_key, {})
    if not wf.get('reviewer'):
        flash("Ten formularz nie wymaga zatwierdzenia.", "info")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    rec = get_form(nr_albumu, zal_key)
    if not rec:
        flash("Formularz nie został jeszcze wypełniony.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    errors = completion_errors(zal_key, rec)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    student = User.query.filter_by(
        role="student", album_number=nr_albumu,
    ).first()
    if current_user.role != "admin" and student is not None:
        unmet = unmet_previous_steps(
            student, zal_key, workflow.get_statuses(nr_albumu),
        )
        if unmet:
            first = unmet[0]
            flash(
                f"Najpierw zakończ Załącznik "
                f"{first.get('nr', first.get('form_key'))}.",
                "error",
            )
            return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    # FSM: walidacja przejścia
    current_state = workflow.get_status(nr_albumu, zal_key)
    try:
        DocumentFSM.transition(current_state, 'submit')
    except InvalidTransition:
        flash("Dokument jest już w trakcie oceny lub zatwierdzony.", "info")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    rec.pop('_diary_comments', None)
    rec.pop('_field_comments', None)
    save_form(nr_albumu, zal_key, rec)
    workflow.do_transition(nr_albumu, zal_key, 'submit', reviewer_role=wf.get('reviewer'))
    ensure_internship(
        nr_albumu, zal_key, rec, document_status="pending", commit=True,
    )
    _notify_reviewers(nr_albumu, zal_key)
    flash(f"Dokument wysłany do zatwierdzenia przez {wf['reviewer_label']}.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


@app.route("/student/<nr_albumu>/<zal_key>/zakoncz", methods=["POST"])
@login_required
def zakoncz_dokument(nr_albumu, zal_key):
    from core.fsm import DocumentFSM, InvalidTransition

    wf = get_document_workflow().get(zal_key, {})
    if wf.get("reviewer"):
        flash("Ten dokument musi zostać zatwierdzony przez recenzenta.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    if not can_edit_form(zal_key) and current_user.role != "admin":
        abort(403)
    record = get_form(nr_albumu, zal_key)
    if not record:
        flash("Najpierw wypełnij i zapisz formularz.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    errors = completion_errors(zal_key, record)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    student = User.query.filter_by(
        role="student", album_number=nr_albumu,
    ).first_or_404()
    if current_user.role != "admin":
        unmet = unmet_previous_steps(
            student, zal_key, workflow.get_statuses(nr_albumu),
        )
        if unmet:
            first = unmet[0]
            flash(
                f"Najpierw zakończ Załącznik "
                f"{first.get('nr', first.get('form_key'))}.",
                "error",
            )
            return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    current_state = workflow.get_status(nr_albumu, zal_key)
    try:
        DocumentFSM.transition(current_state, "complete")
    except InvalidTransition:
        flash("Dokument nie jest szkicem gotowym do zakończenia.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    if zal_key == "zal8":
        internship = Internship.query.filter_by(
            student_id=student.id,
            is_archived=0,
        ).order_by(Internship.id.desc()).first()
        if internship is None or internship.grade_k is None:
            flash("Protokół musi zawierać obliczoną ocenę końcową.", "error")
            return redirect(url_for("student_detail", nr_albumu=nr_albumu))

    workflow.do_transition(nr_albumu, zal_key, "complete")
    ensure_internship(
        nr_albumu,
        zal_key,
        record,
        document_status="approved",
        commit=True,
    )
    if current_user.role != "student":
        _notify_student(
            nr_albumu,
            zal_key,
            "approved",
            f"Etap zakończył: {current_user.full_name}",
        )
    flash("Etap został zakończony. Odblokowano kolejny dokument.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


@app.route("/student/<nr_albumu>/<zal_key>/zatwierdz", methods=["POST"])
@login_required
def zatwierdz_dokument(nr_albumu, zal_key):
    wf = get_document_workflow().get(zal_key, {})
    if current_user.role != wf.get('reviewer') and current_user.role != 'admin':
        flash("Nie masz uprawnień do zatwierdzania tego dokumentu.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    rec = get_form(nr_albumu, zal_key)
    current_state = workflow.get_status(nr_albumu, zal_key)
    if not rec or current_state != 'pending':
        flash("Dokument nie oczekuje na zatwierdzenie.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    from core.fsm import DocumentFSM, InvalidTransition
    try:
        DocumentFSM.transition(current_state, 'approve')
    except InvalidTransition as e:
        flash(str(e), "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    rec.pop('_diary_comments', None)
    for field in _APPROVE_SIGS.get((zal_key, current_user.role), []):
        if not rec.get(field):
            rec[field] = _auto_sig()
    save_form(nr_albumu, zal_key, rec)
    workflow.do_transition(nr_albumu, zal_key, 'approve', reviewer_role=wf.get('reviewer'))
    ensure_internship(
        nr_albumu, zal_key, rec, document_status="approved", commit=True,
    )
    _close_reviewer_notifications(nr_albumu, zal_key)
    _notify_student(
        nr_albumu, zal_key, "approved",
        f"Zatwierdził: {current_user.full_name}",
    )
    flash("Dokument został zatwierdzony.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


@app.route("/student/<nr_albumu>/zal1/podpisz-dziekanat", methods=["POST"])
@login_required
def podpisz_zal1_dziekanat(nr_albumu):
    if current_user.role not in ("dziekanat", "admin"):
        abort(403)
    record = get_form(nr_albumu, "zal1")
    state = workflow.get_document(nr_albumu, "zal1")
    if not record or state is None or state.status != "approved":
        flash("Dziekanat może podpisać wyłącznie zatwierdzony Załącznik 1.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    if record.get("podpis_dziekanatu"):
        flash("Załącznik 1 ma już podpis dziekanatu.", "warning")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))

    record["podpis_dziekanatu"] = _auto_sig()
    revision = save_form(nr_albumu, "zal1", record)
    state.approved_revision = revision
    workflow.log_event(
        nr_albumu,
        "zal1",
        "signed",
        comment="Podpis dziekanatu",
    )
    db.session.commit()
    flash("Dodano podpis dziekanatu do Załącznika 1.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


@app.route("/student/<nr_albumu>/<zal_key>/odrzuc", methods=["POST"])
@login_required
def odrzuc_dokument(nr_albumu, zal_key):
    wf = get_document_workflow().get(zal_key, {})
    if current_user.role != wf.get('reviewer') and current_user.role != 'admin':
        flash("Nie masz uprawnień do odrzucania tego dokumentu.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    rec = get_form(nr_albumu, zal_key)
    current_state = workflow.get_status(nr_albumu, zal_key)
    if not rec or current_state != 'pending':
        flash("Dokument nie oczekuje na zatwierdzenie.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    comment = request.form.get("comment", "").strip()
    if not comment:
        flash("Podaj powód odrzucenia.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    field_names  = request.form.getlist("field_name[]")
    field_notes  = request.form.getlist("field_note[]")
    field_comments = [
        {"field": fn.strip(), "note": fnt.strip()}
        for fn, fnt in zip(field_names, field_notes)
        if fn.strip() or fnt.strip()
    ]
    from core.fsm import DocumentFSM, InvalidTransition
    try:
        DocumentFSM.transition(current_state, 'reject')
    except InvalidTransition as e:
        flash(str(e), "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    if field_comments:
        rec['_field_comments'] = field_comments
    else:
        rec.pop('_field_comments', None)
    save_form(nr_albumu, zal_key, rec)
    workflow.do_transition(nr_albumu, zal_key, 'reject',
                           reviewer_role=wf.get('reviewer'),
                           comment=comment)
    ensure_internship(
        nr_albumu, zal_key, rec, document_status="rejected", commit=True,
    )
    _close_reviewer_notifications(nr_albumu, zal_key)
    _notify_student(nr_albumu, zal_key, "rejected", comment)
    flash("Dokument został odrzucony – student może go poprawić i przesłać ponownie.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 1 – Porozumienie z zakładem pracy  [student]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal1", methods=["GET", "POST"])
@login_required
def zal1():
    guard = guard_form('zal1')
    if guard: return guard
    if request.method == "POST":
        return _save_zal1(None)
    nr = current_user.album_number if current_user.role == 'student' else request.args.get("nr", "")
    return render_template("zal1.html", data=_zal1_prefill(nr),
                           edit_nr=None, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'))


@app.route("/zal1/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal1_edit(nr_albumu):
    guard = guard_form('zal1')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    guard_e = guard_edit(nr_albumu, 'zal1')
    if guard_e: return guard_e
    if request.method == "POST":
        return _save_zal1(nr_albumu)
    existing = dict(_record_with_gender(
        load_data().get(nr_albumu, {}).get("zal1"), nr_albumu,
    ) or {})
    existing["nr_porozumienia"] = _agreement_number(nr_albumu)
    existing["data"] = existing.get("data") or _date.today().isoformat()
    existing["liczba_godzin"] = "960"
    return render_template("zal1.html", data=existing, edit_nr=nr_albumu, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'))


@app.route("/zal1/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal1_delete(nr_albumu):
    guard = guard_form('zal1')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    has_other = _delete_attachment(nr_albumu, "zal1")
    flash("Załącznik 1 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal1(edit_nr):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = student_nr(f.get("nr_albumu", "").strip())
    nr_locked     = (current_user.role == 'student')
    specialties   = get_specialties()
    existing = load_data().get(nr_albumu, {}).get('zal1', {})
    miejscowosc = _capitalize_entry(f.get("miejscowosc"))
    reprezentant = _normalize_person_name(f.get("reprezentant_nazwisko"))
    adres_zakladu = " ".join(f.get("adres_zakladu", "").strip().split())
    email_zakladu = f.get("email_zakladu", "").strip().lower()
    data_utworzenia = existing.get("data") or _date.today().isoformat()
    submitted_hours = f.get("liczba_godzin", "960")
    errors = []
    for ok, msg in (
        validators.is_valid_full_name(imie_nazwisko),
        validators.is_valid_album(nr_albumu),
        validators.is_valid_date(data_utworzenia, required=True),
        validators.is_valid_address(adres_zakladu, required=True),
        validators.is_valid_full_name(reprezentant),
        validators.validate_email(email_zakladu, required=True),
        validators.validate_nip(f.get("nip_zakladu", ""), required=False),
        validators.validate_date_range(f.get("data_start", ""), f.get("data_end", "")),
        validators.validate_required_hours(submitted_hours),
    ):
        if not ok:
            errors.append(msg)
    if len(miejscowosc) < 2:
        errors.append("Miejscowość jest wymagana.")
    if errors:
        for m in errors:
            flash(m, "error")
        invalid_data = f.to_dict()
        invalid_data.update({
            "nr_albumu": nr_albumu,
            "nr_porozumienia": _agreement_number(nr_albumu),
            "miejscowosc": miejscowosc,
            "data": data_utworzenia,
            "adres_zakladu": adres_zakladu,
            "reprezentant_nazwisko": reprezentant,
            "email_zakladu": email_zakladu,
            "liczba_godzin": "960",
        })
        return render_template(
            "zal1.html",
            data=invalid_data,
            edit_nr=edit_nr,
            specialties=specialties,
            nr_locked=nr_locked,
        )
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "nr_porozumienia": _agreement_number(nr_albumu),
        "miejscowosc": miejscowosc,
        "data": data_utworzenia,
        "kierunek": "Informatyka",
        "specjalnosc": f.get("specjalnosc", "").strip(),
        "rodzaj_studiow": f.get("rodzaj_studiow", "stacjonarne"),
        "nazwa_zakladu": f.get("nazwa_zakladu", "").strip(),
        "adres_zakladu": adres_zakladu,
        "nip_zakladu": f.get("nip_zakladu", "").strip(),
        "reprezentant_nazwisko": reprezentant,
        "reprezentant_stanowisko": f.get("reprezentant_stanowisko", "").strip(),
        "email_zakladu": email_zakladu,
        "uczelniany_opiekun": f.get("uczelniany_opiekun", "").strip(),
        "data_start": f.get("data_start", "").strip(),
        "data_end": f.get("data_end", "").strip(),
        "liczba_godzin": "960",
    }
    _stamp_sigs(record, 'zal1', existing)
    return _persist(nr_albumu, "zal1", record, "Załącznik 1")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 2 – Program praktyki zawodowej  [uopz]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal2", methods=["GET", "POST"])
@login_required
def zal2():
    guard = guard_form('zal2')
    if guard: return guard
    if request.method == "POST":
        return _save_zal2(None)
    nr = request.args.get("nr", "")
    return render_template("zal2.html", data=build_prefill(nr), edit_nr=None, effects=get_effects())


@app.route("/zal2/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal2_edit(nr_albumu):
    guard = guard_form('zal2')
    if guard: return guard
    guard_e = guard_edit(nr_albumu, 'zal2')
    if guard_e: return guard_e
    if request.method == "POST":
        return _save_zal2(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal2")
    return render_template("zal2.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu, effects=get_effects())


@app.route("/zal2/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal2_delete(nr_albumu):
    guard = guard_form('zal2')
    if guard: return guard
    has_other = _delete_attachment(nr_albumu, "zal2")
    flash("Załącznik 2 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal2(edit_nr):
    f = request.form
    effects = get_effects()
    nr_albumu = f.get("nr_albumu", "").strip()
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal2.html", data=f, edit_nr=edit_nr, effects=effects)
    record = {
        "nr_albumu": nr_albumu,
        "zaklad_pracy": f.get("zaklad_pracy", "").strip(),
        "data_start": f.get("data_start", "").strip(),
        "data_end": f.get("data_end", "").strip(),
        "data_uzgodnienia": f.get("data_uzgodnienia", "").strip(),
    }
    existing = load_data().get(nr_albumu, {}).get('zal2', {})
    _stamp_sigs(record, 'zal2', existing)
    return _persist(nr_albumu, "zal2", record, "Załącznik 2")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 2a – Program i harmonogram  [student]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal2a", methods=["GET", "POST"])
@login_required
def zal2a():
    guard = guard_form('zal2a')
    if guard: return guard
    effects = get_effects()
    if request.method == "POST":
        return _save_zal2a(None, effects)
    nr = current_user.album_number if current_user.role == 'student' else request.args.get("nr", "")
    return render_template("zal2a.html", data=build_prefill(nr),
                           edit_nr=None, effects=effects, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'))


@app.route("/zal2a/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal2a_edit(nr_albumu):
    guard = guard_form('zal2a')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    guard_e = guard_edit(nr_albumu, 'zal2a')
    if guard_e: return guard_e
    effects = get_effects()
    if request.method == "POST":
        return _save_zal2a(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal2a")
    return render_template("zal2a.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu,
                           effects=effects, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'))


@app.route("/zal2a/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal2a_delete(nr_albumu):
    guard = guard_form('zal2a')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    has_other = _delete_attachment(nr_albumu, "zal2a")
    flash("Załącznik 2a został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal2a(edit_nr, effects):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = student_nr(f.get("nr_albumu", "").strip())
    nr_locked     = (current_user.role == 'student')
    specialties   = get_specialties()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal2a.html", data=f, edit_nr=edit_nr, effects=effects,
                               specialties=specialties, nr_locked=nr_locked)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal2a.html", data=f, edit_nr=edit_nr, effects=effects,
                               specialties=specialties, nr_locked=nr_locked)
    efekty_plan = [{"nr": e.nr, "dzial_prace": f.get(f"dzial_{e.nr}", "").strip()} for e in effects]
    harmono = []
    for i in range(1, 14):
        dzial = f.get(f"h_dzial_{i}", "").strip()
        dni   = f.get(f"h_dni_{i}", "").strip()
        if dzial or dni:
            harmono.append({"lp": i, "dzial": dzial, "dni": dni})
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "kierunek": "Informatyka",
        "specjalnosc": f.get("specjalnosc", "").strip(),
        "miejsce_praktyki": f.get("miejsce_praktyki", "").strip(),
        "data_start": f.get("data_start", "").strip(),
        "data_end": f.get("data_end", "").strip(),
        "efekty_plan": efekty_plan,
        "harmonogram": harmono,
        "data_uzgodnienia": f.get("data_uzgodnienia", "").strip(),
    }
    existing = load_data().get(nr_albumu, {}).get('zal2a', {})
    _stamp_sigs(record, 'zal2a', existing)
    return _persist(nr_albumu, "zal2a", record, "Załącznik 2a")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 3 – Karta praktyki zawodowej  [zopz]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal3", methods=["GET", "POST"])
@login_required
def zal3():
    guard = guard_form('zal3')
    if guard: return guard
    if request.method == "POST":
        return _save_zal3(None)
    nr = request.args.get("nr", "")
    return render_template("zal3.html", data=build_prefill(nr),
                           edit_nr=None, specialties=get_specialties())


@app.route("/zal3/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal3_edit(nr_albumu):
    guard = guard_form('zal3')
    if guard: return guard
    guard_e = guard_edit(nr_albumu, 'zal3')
    if guard_e: return guard_e
    if request.method == "POST":
        return _save_zal3(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal3")
    return render_template("zal3.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu, specialties=get_specialties())


@app.route("/zal3/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal3_delete(nr_albumu):
    guard = guard_form('zal3')
    if guard: return guard
    has_other = _delete_attachment(nr_albumu, "zal3")
    flash("Załącznik 3 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal3(edit_nr):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    specialties   = get_specialties()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko studenta.", "error")
        return render_template("zal3.html", data=f, edit_nr=edit_nr, specialties=specialties)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal3.html", data=f, edit_nr=edit_nr, specialties=specialties)
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "nr_porozumienia": f.get("nr_porozumienia", "").strip(),
        "data_porozumienia": f.get("data_porozumienia", "").strip(),
        "zaklad_pracy": f.get("zaklad_pracy", "").strip(),
        "kierunek": "Informatyka",
        "specjalnosc": f.get("specjalnosc", "").strip(),
        "rodzaj_studiow": f.get("rodzaj_studiow", "stacjonarne"),
        "uczelniany_opiekun": f.get("uczelniany_opiekun", "").strip(),
        "data_start": f.get("data_start", "").strip(),
        "data_end": f.get("data_end", "").strip(),
        "zakladowy_opiekun_nazwisko": f.get("zakladowy_opiekun_nazwisko", "").strip(),
        "zakladowy_opiekun_funkcja": f.get("zakladowy_opiekun_funkcja", "").strip(),
        "potwierdzenie_zgloszenia": f.get("potwierdzenie_zgloszenia", "").strip(),
        "potwierdzenie_bhp": f.get("potwierdzenie_bhp", "").strip(),
        "zaswiadczenie_zaklad": f.get("zaswiadczenie_zaklad", "").strip(),
        "zaswiadczenie_okres_od": f.get("zaswiadczenie_okres_od", "").strip(),
        "zaswiadczenie_okres_do": f.get("zaswiadczenie_okres_do", "").strip(),
        "zaswiadczenie_uwagi": f.get("zaswiadczenie_uwagi", "").strip(),
        "zaswiadczenie_podpis": f.get("zaswiadczenie_podpis", "").strip(),
        "ocena_zakladowa_param": f.get("ocena_zakladowa_param", "").strip(),
        "ocena_zakladowa_opis": f.get("ocena_zakladowa_opis", "").strip(),
        "ocena_uczelniana_param": f.get("ocena_uczelniana_param", "").strip(),
        "ocena_uczelniana_opis": f.get("ocena_uczelniana_opis", "").strip(),
        "ocena_sprawozdania": f.get("ocena_sprawozdania", "").strip(),
    }
    existing = load_data().get(nr_albumu, {}).get('zal3', {})
    _stamp_sigs(record, 'zal3', existing)
    return _persist(nr_albumu, "zal3", record, "Załącznik 3")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 4 – Potwierdzenie efektów uczenia się  [zopz]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal4", methods=["GET", "POST"])
@login_required
def zal4():
    guard = guard_form('zal4')
    if guard: return guard
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4(None, effects)
    nr = request.args.get("nr", "")
    return render_template("zal4.html", data=build_prefill(nr),
                           edit_nr=None, effects=effects, specialties=get_specialties())


@app.route("/zal4/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal4_edit(nr_albumu):
    guard = guard_form('zal4')
    if guard: return guard
    guard_e = guard_edit(nr_albumu, 'zal4')
    if guard_e: return guard_e
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal4")
    return render_template("zal4.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu,
                           effects=effects, specialties=get_specialties())


@app.route("/zal4/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal4_delete(nr_albumu):
    guard = guard_form('zal4')
    if guard: return guard
    has_other = _delete_attachment(nr_albumu, "zal4")
    flash("Załącznik 4 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal4(edit_nr, effects):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    specialties   = get_specialties()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko studenta.", "error")
        return render_template("zal4.html", data=f, edit_nr=edit_nr, effects=effects, specialties=specialties)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal4.html", data=f, edit_nr=edit_nr, effects=effects, specialties=specialties)
    efekty = [{"nr": e.nr, "status": f.get(f"ef_{e.nr}", "").strip()} for e in effects]
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "kierunek": "Informatyka",
        "specjalnosc": f.get("specjalnosc", "").strip(),
        "wymiar_godzin": f.get("wymiar_godzin", "").strip(),
        "potwierdzenie_opiekuna": f.get("potwierdzenie_opiekuna", "").strip(),
        "opinia_opiekuna": f.get("opinia_opiekuna", "").strip(),
        "efekty": efekty,
    }
    return _persist(nr_albumu, "zal4", record, "Załącznik 4")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 4a – Merytoryczna ocena wniosku  [uopz]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal4a", methods=["GET", "POST"])
@login_required
def zal4a():
    guard = guard_form('zal4a')
    if guard: return guard
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4a(None, effects)
    nr = request.args.get("nr", "")
    existing = None
    if nr:
        store = load_data().get(nr, {})
        zal4b = store.get("zal4b", {})
        existing = build_prefill(nr) or {}
        existing["data_zlozenia"] = zal4b.get("data", "")
    return render_template("zal4a.html", data=existing, edit_nr=None, effects=effects)


@app.route("/zal4a/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal4a_edit(nr_albumu):
    guard = guard_form('zal4a')
    if guard: return guard
    guard_e = guard_edit(nr_albumu, 'zal4a')
    if guard_e: return guard_e
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4a(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal4a")
    return render_template("zal4a.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu, effects=effects)


@app.route("/zal4a/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal4a_delete(nr_albumu):
    guard = guard_form('zal4a')
    if guard: return guard
    has_other = _delete_attachment(nr_albumu, "zal4a")
    flash("Załącznik 4a został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal4a(edit_nr, effects):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko studenta.", "error")
        return render_template("zal4a.html", data=f, edit_nr=edit_nr, effects=effects)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal4a.html", data=f, edit_nr=edit_nr, effects=effects)
    ocena_efektow = [
        {"nr": e.nr,
         "zasadny": f.get(f"zasadny_{e.nr}", "").strip(),
         "uzasadnienie": f.get(f"uzasadnienie_{e.nr}", "").strip()}
        for e in effects
    ]
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "data_zlozenia": f.get("data_zlozenia", "").strip(),
        "ocena_efektow": ocena_efektow,
        "rekomendacja": f.get("rekomendacja", "").strip(),
        "uwagi": f.get("uwagi", "").strip(),
        "data_oceny": f.get("data_oceny", "").strip(),
    }
    existing = load_data().get(nr_albumu, {}).get('zal4a', {})
    _stamp_sigs(record, 'zal4a', existing)
    return _persist(nr_albumu, "zal4a", record, "Załącznik 4a")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 4b – Wniosek studenta o zaliczenie efektów  [student]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal4b", methods=["GET", "POST"])
@login_required
def zal4b():
    guard = guard_form('zal4b')
    if guard: return guard
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4b(None, effects)
    nr = current_user.album_number if current_user.role == 'student' else request.args.get("nr", "")
    return render_template("zal4b.html", data=build_prefill(nr),
                           edit_nr=None, effects=effects, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'),
                           today=_date.today().isoformat())


@app.route("/zal4b/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal4b_edit(nr_albumu):
    guard = guard_form('zal4b')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    guard_e = guard_edit(nr_albumu, 'zal4b')
    if guard_e: return guard_e
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4b(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal4b")
    return render_template("zal4b.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu,
                           effects=effects, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'),
                           today=_date.today().isoformat())


@app.route("/zal4b/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal4b_delete(nr_albumu):
    guard = guard_form('zal4b')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    has_other = _delete_attachment(nr_albumu, "zal4b")
    flash("Załącznik 4b został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal4b(edit_nr, effects):
    f = request.form
    role = current_user.role
    specialties = get_specialties()

    # nr_albumu: student_nr() zwraca własny album studenta lub wartość z formularza
    nr_albumu = student_nr(f.get("nr_albumu", "").strip())
    existing  = load_data().get(nr_albumu, {}).get('zal4b', {}) if nr_albumu else {}
    nr_locked = (role == 'student')

    if role == 'student':
        # Student wypełnia sekcje A–D; walidujemy tylko wtedy gdy student zapisuje
        imie_nazwisko = f.get("imie_nazwisko", "").strip()
        if not is_valid_full_name(imie_nazwisko):
            flash("Podaj imię i nazwisko.", "error")
            return render_template("zal4b.html", data=f, edit_nr=edit_nr, effects=effects,
                                   specialties=specialties, nr_locked=nr_locked,
                                   today=_date.today().isoformat())
        if not nr_albumu or not is_digits_only(nr_albumu):
            flash("Numer albumu może zawierać tylko cyfry.", "error")
            return render_template("zal4b.html", data=f, edit_nr=edit_nr, effects=effects,
                                   specialties=specialties, nr_locked=nr_locked,
                                   today=_date.today().isoformat())
        efekty_wniosek = [
            {"nr": e.nr,
             "uzasadnienie": f.get(f"uzasadnienie_{e.nr}", "").strip(),
             "dowody": f.get(f"dowody_{e.nr}", "").strip()}
            for e in effects
        ]
        # ── Obsługa plików dowodów ──────────────────────────────────────────
        pliki = list(existing.get("pliki", []))
        delete_ids = set(f.getlist("delete_file[]"))
        if delete_ids:
            for p in pliki:
                if p['id'] in delete_ids:
                    try:
                        path = _upload_path(nr_albumu, str(p.get("id", "")), str(p.get("ext", "")))
                        if path:
                            os.remove(path)
                    except OSError:
                        pass
            pliki = [p for p in pliki if p['id'] not in delete_ids]
        for uploaded in request.files.getlist("zalaczniki[]"):
            meta = _save_upload(uploaded, nr_albumu)
            if meta:
                pliki.append(meta)
            elif uploaded.filename:
                flash(f"Plik '{uploaded.filename}' odrzucony (nieobsługiwany format lub za duży).", "warning")
        record = {
            "imie_nazwisko": imie_nazwisko,
            "nr_albumu": nr_albumu,
            "kierunek": "Informatyka",
            "specjalnosc": f.get("specjalnosc", "").strip(),
            "pracodawca": f.get("pracodawca", "").strip(),
            "adres_pracodawcy": f.get("adres_pracodawcy", "").strip(),
            "stanowisko": f.get("stanowisko", "").strip(),
            "okres_od": f.get("okres_od", "").strip(),
            "okres_do": f.get("okres_do", "").strip(),
            "efekty_wniosek": efekty_wniosek,
            "pliki": pliki,
            "data": f.get("data", "").strip(),
            # Sekcje E i F — zachowaj istniejące (student nie edytuje)
            "opinia_komisji": existing.get("opinia_komisji", ""),
            "data_opinii":    existing.get("data_opinii", ""),
            "decyzja_dyrektora": existing.get("decyzja_dyrektora", ""),
            "data_decyzji":   existing.get("data_decyzji", ""),
        }
    else:
        # uopz (sekcja E) lub admin (sekcja F) — nie dotykaj danych studenta (A–D)
        if not nr_albumu or not is_digits_only(nr_albumu):
            flash("Numer albumu może zawierać tylko cyfry.", "error")
            return render_template("zal4b.html", data=existing or f, edit_nr=edit_nr,
                                   effects=effects, specialties=specialties, nr_locked=nr_locked,
                                   today=_date.today().isoformat())
        record = {
            # Sekcje A–D — tylko z istniejącego rekordu (nie z formularza)
            "imie_nazwisko":    existing.get("imie_nazwisko", ""),
            "nr_albumu":        nr_albumu,
            "kierunek":         "Informatyka",
            "specjalnosc":      existing.get("specjalnosc", ""),
            "pracodawca":       existing.get("pracodawca", ""),
            "adres_pracodawcy": existing.get("adres_pracodawcy", ""),
            "stanowisko":       existing.get("stanowisko", ""),
            "okres_od":         existing.get("okres_od", ""),
            "okres_do":         existing.get("okres_do", ""),
            "efekty_wniosek":   existing.get("efekty_wniosek", []),
            "pliki":            existing.get("pliki", []),
            "data":             existing.get("data", ""),
            # Sekcja E — uopz wypełnia
            "opinia_komisji": f.get("opinia_komisji", "").strip(),
            "data_opinii":    f.get("data_opinii", "").strip(),
            # Sekcja F — admin wypełnia; radio disabled nie przesyła wartości, zachowaj z existing
            "decyzja_dyrektora": f.get("decyzja_dyrektora", "").strip() or existing.get("decyzja_dyrektora", ""),
            "data_decyzji":      f.get("data_decyzji", "").strip(),
        }

    _stamp_sigs(record, 'zal4b', existing)
    return _persist(nr_albumu, "zal4b", record, "Załącznik 4b")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 5 – Kwestionariusz ankiety  [student]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal5", methods=["GET", "POST"])
@login_required
def zal5():
    guard = guard_form('zal5')
    if guard: return guard
    if request.method == "POST":
        return _save_zal5(None)
    nr = current_user.album_number if current_user.role == 'student' else request.args.get("nr", "")
    return render_template("zal5.html", data=build_prefill(nr),
                           edit_nr=None, questions=get_survey_questions(), options=get_survey_options(),
                           nr_locked=(current_user.role == 'student'))


@app.route("/zal5/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal5_edit(nr_albumu):
    guard = guard_form('zal5')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    guard_e = guard_edit(nr_albumu, 'zal5')
    if guard_e: return guard_e
    if request.method == "POST":
        return _save_zal5(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal5")
    return render_template("zal5.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu,
                           questions=get_survey_questions(), options=get_survey_options(),
                           nr_locked=(current_user.role == 'student'))


@app.route("/zal5/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal5_delete(nr_albumu):
    guard = guard_form('zal5')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    has_other = _delete_attachment(nr_albumu, "zal5")
    flash("Załącznik 5 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal5(edit_nr):
    f = request.form
    nr_albumu = student_nr(f.get("nr_albumu", "").strip())
    nr_locked = (current_user.role == 'student')
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal5.html", data=f, edit_nr=edit_nr,
                               questions=get_survey_questions(), options=get_survey_options(), nr_locked=nr_locked)
    pytania = [{"nr": i + 1, "odpowiedz": f.get(f"q{i+1}", "")} for i in range(14)]
    record = {
        "nr_albumu": nr_albumu,
        "rok_akademicki": f.get("rok_akademicki", "").strip(),
        "kierunek": "Informatyka",
        "forma_studiow": f.get("forma_studiow", "stacjonarne"),
        "semestr": f.get("semestr", "").strip(),
        "liczba_godzin": f.get("liczba_godzin", "").strip(),
        "pytania": pytania,
        "uwagi": f.get("uwagi", "").strip(),
    }
    return _persist(nr_albumu, "zal5", record, "Załącznik 5")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 6 – Dziennik praktyki zawodowej  [student]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal6", methods=["GET", "POST"])
@login_required
def zal6():
    guard = guard_form('zal6')
    if guard: return guard
    effects = get_effects()
    if request.method == "POST":
        return _save_zal6(None, effects)
    nr = current_user.album_number if current_user.role == 'student' else request.args.get("nr", "")
    return render_template("zal6.html", data=build_prefill(nr),
                           edit_nr=None, effects=effects, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'))


@app.route("/zal6/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal6_edit(nr_albumu):
    guard = guard_form('zal6')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    guard_e = guard_edit(nr_albumu, 'zal6')
    if guard_e: return guard_e
    effects = get_effects()
    if request.method == "POST":
        return _save_zal6(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal6")
    diary_comments = existing.get('_diary_comments', []) if existing else []
    return render_template("zal6.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu,
                           effects=effects, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'),
                           diary_comments=diary_comments)


@app.route("/zal6/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal6_delete(nr_albumu):
    guard = guard_form('zal6')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    has_other = _delete_attachment(nr_albumu, "zal6")
    flash("Załącznik 6 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal6(edit_nr, effects):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = student_nr(f.get("nr_albumu", "").strip())
    nr_locked     = (current_user.role == 'student')
    specialties   = get_specialties()

    # Wpisy dziennika przychodzą jako pola tablicowe (dzien[], data[], opis[]...)
    dni     = request.form.getlist("dzien[]")
    datas   = request.form.getlist("data[]")
    godziny_l = request.form.getlist("godziny[]")
    opisy   = request.form.getlist("opis[]")
    efekty_l = request.form.getlist("efekty[]")
    podpisy = request.form.getlist("podpis[]")
    dziennik = []
    diary_errors = []
    seen_days = set()
    total_hours = 0
    for idx in range(len(opisy)):
        dzien  = (dni[idx]     if idx < len(dni) else "").strip()
        data_d = (datas[idx]   if idx < len(datas) else "").strip()
        godziny = (godziny_l[idx] if idx < len(godziny_l) else "").strip()
        opis   = (opisy[idx]   if idx < len(opisy) else "").strip()
        efekty = (efekty_l[idx] if idx < len(efekty_l) else "").strip()
        podpis = (podpisy[idx] if idx < len(podpisy) else "").strip()
        if not (dzien or data_d or opis):
            continue
        etykieta = f"Dzień {dzien or (idx + 1)}"
        ok_o, msg_o = validators.validate_diary_opis(opis)
        if not ok_o:
            diary_errors.append(f"{etykieta}: {msg_o}")
        ok_d, msg_d = validators.is_valid_date(data_d, required=True)
        if not ok_d:
            diary_errors.append(f"{etykieta} (data): {msg_d}")
        ok_day, msg_day = validators.validate_diary_day(dzien)
        if not ok_day:
            diary_errors.append(f"{etykieta}: {msg_day}")
        else:
            day_number = int(dzien)
            if day_number in seen_days:
                diary_errors.append(f"{etykieta}: ten numer dnia występuje więcej niż raz.")
            seen_days.add(day_number)
        ok_hours, msg_hours = validators.validate_diary_hours(godziny)
        if not ok_hours:
            diary_errors.append(f"{etykieta} (godziny): {msg_hours}")
        else:
            total_hours += int(godziny)
        dziennik.append({
            "dzien": dzien,
            "data": data_d,
            "godziny": godziny,
            "opis": opis,
            "efekty": efekty,
            "podpis": podpis,
        })

    if len(dziennik) > 120:
        diary_errors.append("Dziennik może zawierać maksymalnie 120 dni praktyki.")
    if total_hours > 960:
        diary_errors.append("Łączna liczba godzin praktyki nie może przekroczyć 960.")

    errors = []
    for ok, msg in (
        validators.is_valid_full_name(imie_nazwisko),
        validators.is_valid_album(nr_albumu),
        validators.validate_date_range(f.get("data_start", ""), f.get("data_end", "")),
    ):
        if not ok:
            errors.append(msg)
    errors.extend(diary_errors)
    if errors:
        for m in errors:
            flash(m, "error")
        redisplay = f.to_dict()
        redisplay["dziennik"] = dziennik
        return render_template("zal6.html", data=redisplay, edit_nr=edit_nr, effects=effects,
                               specialties=specialties, nr_locked=nr_locked, diary_comments=[])
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "kierunek": "Informatyka",
        "specjalnosc": f.get("specjalnosc", "").strip(),
        "rodzaj_studiow": f.get("rodzaj_studiow", "stacjonarne"),
        "rok_akademicki": f.get("rok_akademicki", "").strip(),
        "miejsce_praktyki": f.get("miejsce_praktyki", "").strip(),
        "data_start": f.get("data_start", "").strip(),
        "data_end": f.get("data_end", "").strip(),
        "wykaz_zalacznikow": f.get("wykaz_zalacznikow", "").strip(),
        "dziennik": dziennik,
    }
    # ── Obsługa plików załączników ─────────────────────────────────────────
    existing_data = load_data().get(nr_albumu, {}).get("zal6", {})
    pliki = list(existing_data.get("pliki", []))
    delete_ids = set(request.form.getlist("delete_file[]"))
    if delete_ids:
        for p in pliki:
            if p['id'] in delete_ids:
                try:
                    path = _upload_path(
                        nr_albumu, str(p.get("id", "")), str(p.get("ext", "")),
                    )
                    if path:
                        os.remove(path)
                except OSError:
                    pass
        pliki = [p for p in pliki if p['id'] not in delete_ids]
    for uploaded in request.files.getlist("zalaczniki[]"):
        meta = _save_upload(uploaded, nr_albumu)
        if meta:
            pliki.append(meta)
        elif uploaded.filename:
            flash(f"Plik '{uploaded.filename}' został odrzucony (nieobsługiwany format lub za duży).", "warning")
    record["pliki"] = pliki
    return _persist(nr_albumu, "zal6", record, "Załącznik 6")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 7 / 7a – Sprawozdanie  [student]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal7", methods=["GET", "POST"])
@login_required
def zal7():
    guard = guard_form('zal7')
    if guard: return guard
    if request.method == "POST":
        return _save_zal7(None, sn=False)
    nr = current_user.album_number if current_user.role == 'student' else request.args.get("nr", "")
    return render_template("zal7.html", data=build_prefill(nr),
                           edit_nr=None, specialties=get_specialties(), sn=False,
                           nr_locked=(current_user.role == 'student'))


@app.route("/zal7/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal7_edit(nr_albumu):
    guard = guard_form('zal7')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    guard_e = guard_edit(nr_albumu, 'zal7')
    if guard_e: return guard_e
    if request.method == "POST":
        return _save_zal7(nr_albumu, sn=False)
    existing = load_data().get(nr_albumu, {}).get("zal7")
    return render_template("zal7.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu, specialties=get_specialties(),
                           sn=False, nr_locked=(current_user.role == 'student'))


@app.route("/zal7/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal7_delete(nr_albumu):
    guard = guard_form('zal7')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    has_other = _delete_attachment(nr_albumu, "zal7")
    flash("Załącznik 7 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal7(edit_nr, sn=False):
    f = request.form
    key = "zal7a" if sn else "zal7"
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = student_nr(f.get("nr_albumu", "").strip())
    nr_locked     = (current_user.role == 'student')
    specialties   = get_specialties()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal7.html", data=f, edit_nr=edit_nr, specialties=specialties,
                               sn=sn, nr_locked=nr_locked)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal7.html", data=f, edit_nr=edit_nr, specialties=specialties,
                               sn=sn, nr_locked=nr_locked)
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "kierunek": "Informatyka",
        "specjalnosc": f.get("specjalnosc", "").strip(),
        "rodzaj_studiow": f.get("rodzaj_studiow", "stacjonarne"),
        "rok_akademicki": f.get("rok_akademicki", "").strip(),
        "miejsce_praktyki": f.get("miejsce_praktyki", "").strip(),
        "charakterystyka": f.get("charakterystyka", "").strip(),
        "opis_prac": f.get("opis_prac", "").strip(),
        "wiedza_umiejetnosci": f.get("wiedza_umiejetnosci", "").strip(),
        "data": f.get("data", "").strip(),
        "podpis_przelozonego": f.get("podpis_przelozonego", "").strip(),
    }
    existing = load_data().get(nr_albumu, {}).get(key, {})
    _stamp_sigs(record, key, existing)
    return _persist(nr_albumu, key, record, f"Załącznik {'7a' if sn else '7'}")


# ── Zał. 7a (SN – niestacjonarne)  [student] ─────────────────────────────────

@app.route("/zal7a", methods=["GET", "POST"])
@login_required
def zal7a():
    guard = guard_form('zal7a')
    if guard: return guard
    if request.method == "POST":
        return _save_zal7(None, sn=True)
    nr = current_user.album_number if current_user.role == 'student' else request.args.get("nr", "")
    return render_template("zal7.html", data=build_prefill(nr),
                           edit_nr=None, specialties=get_specialties(), sn=True,
                           nr_locked=(current_user.role == 'student'))


@app.route("/zal7a/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal7a_edit(nr_albumu):
    guard = guard_form('zal7a')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    guard_e = guard_edit(nr_albumu, 'zal7a')
    if guard_e: return guard_e
    if request.method == "POST":
        return _save_zal7(nr_albumu, sn=True)
    existing = load_data().get(nr_albumu, {}).get("zal7a")
    return render_template("zal7.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu, specialties=get_specialties(),
                           sn=True, nr_locked=(current_user.role == 'student'))


@app.route("/zal7a/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal7a_delete(nr_albumu):
    guard = guard_form('zal7a')
    if guard: return guard
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    has_other = _delete_attachment(nr_albumu, "zal7a")
    flash("Załącznik 7a został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 8 – Protokół zaliczenia praktyki  [dziekanat]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal8", methods=["GET", "POST"])
@login_required
def zal8():
    guard = guard_form('zal8')
    if guard: return guard
    if request.method == "POST":
        return _save_zal8(None)
    nr = request.args.get("nr", "")
    existing_data = {}
    if nr:
        store = load_data().get(nr, {})
        existing_data["nr_albumu"] = nr
        z3 = store.get("zal3", {})
        existing_data["imie_nazwisko"] = z3.get("imie_nazwisko", "")
        existing_data["ocena_u"] = z3.get("ocena_uczelniana_param", "")
        existing_data["ocena_z"] = z3.get("ocena_zakladowa_param", "")
        internship = ensure_internship(nr)
        existing_data["miejsca_praktyki"] = _internship_places(internship)
    return render_template("zal8.html", data=existing_data or None, edit_nr=None)


@app.route("/zal8/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal8_edit(nr_albumu):
    guard = guard_form('zal8')
    if guard: return guard
    guard_e = guard_edit(nr_albumu, 'zal8')
    if guard_e: return guard_e
    if request.method == "POST":
        return _save_zal8(nr_albumu)
    store = load_data().get(nr_albumu, {})
    existing = store.get("zal8")
    if not existing:
        existing = {"nr_albumu": nr_albumu}
        z3 = store.get("zal3", {})
        existing["imie_nazwisko"] = z3.get("imie_nazwisko", "")
        existing["ocena_u"] = z3.get("ocena_uczelniana_param", "")
        existing["ocena_z"] = z3.get("ocena_zakladowa_param", "")
        internship = ensure_internship(nr_albumu)
        existing["miejsca_praktyki"] = _internship_places(internship)
    return render_template("zal8.html", data=_record_with_gender(existing, nr_albumu), edit_nr=nr_albumu)


@app.route("/zal8/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal8_delete(nr_albumu):
    guard = guard_form('zal8')
    if guard: return guard
    has_other = _delete_attachment(nr_albumu, "zal8")
    flash("Załącznik 8 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _internship_places(internship):
    if internship is None:
        return []
    return [
        {
            "nazwa": part.company.name if part.company else part.name,
            "okres": (
                f"{part.start_date or '—'} – {part.end_date or '—'}"
            ),
            "dni": part.total_days,
        }
        for part in internship.parts
        if part.status != "cancelled"
    ]


def _save_zal8(edit_nr):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal8.html", data=f, edit_nr=edit_nr)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal8.html", data=f, edit_nr=edit_nr)
    miejsca = []
    for i in range(1, 6):
        nazwa  = f.get(f"miejsce_nazwa_{i}", "").strip()
        okres  = f.get(f"miejsce_okres_{i}", "").strip()
        dni    = f.get(f"miejsce_dni_{i}", "").strip()
        if nazwa or okres or dni:
            miejsca.append({"nazwa": nazwa, "okres": okres, "dni": dni})
    mini = [
        {"tresc": f.get(f"mini_{i}", "").strip(), "ocena": f.get(f"mini_ocena_{i}", "").strip()}
        for i in range(1, 4)
    ]
    try:
        calculation = calculate_final_grade(
            grade_e=f.get("ocena_e"),
            grade_s=f.get("ocena_s"),
            grade_u=f.get("ocena_u"),
            grade_z=f.get("ocena_z"),
        )
    except GradeValidationError as exc:
        flash(str(exc), "error")
        return render_template("zal8.html", data=f, edit_nr=edit_nr)

    internship = ensure_internship(nr_albumu)
    if internship is None:
        flash("Nie znaleziono konta studenta o podanym numerze albumu.", "error")
        return render_template("zal8.html", data=f, edit_nr=edit_nr)
    if calculation is not None:
        try:
            require_approved_diary(workflow.get_status(nr_albumu, "zal6"))
        except GradeValidationError as exc:
            flash(str(exc), "error")
            return render_template("zal8.html", data=f, edit_nr=edit_nr)
        previous_grade = getattr(internship, "grade_k", None)
        store_final_grade(internship, calculation, actor=current_user)
        log_action(
            "calculate",
            "internship_grade",
            internship.id,
            before={"grade_k": str(previous_grade) if previous_grade is not None else None},
            after={
                "grade_e": grade_to_text(calculation["grades"]["e"]),
                "grade_s": grade_to_text(calculation["grades"]["s"]),
                "grade_u": grade_to_text(calculation["grades"]["u"]),
                "grade_z": grade_to_text(calculation["grades"]["z"]),
                "weighted_result": str(calculation["weighted_result"]),
                "grade_k": grade_to_text(calculation["final_grade"]),
            },
        )
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "miejsca_praktyki": miejsca,
        "ocena_s": f.get("ocena_s", "").strip(),
        "data_s": f.get("data_s", "").strip(),
        "ocena_u": f.get("ocena_u", "").strip(),
        "ocena_z": f.get("ocena_z", "").strip(),
        "sklad_komisji": f.get("sklad_komisji", "").strip(),
        "data_zaliczenia": f.get("data_zaliczenia", "").strip(),
        "przewodniczacy": f.get("przewodniczacy", "").strip(),
        "czlonek_2": f.get("czlonek_2", "").strip(),
        "czlonek_3": f.get("czlonek_3", "").strip(),
        "czlonek_4": f.get("czlonek_4", "").strip(),
        "mini_zadania": mini,
        "ocena_e": f.get("ocena_e", "").strip(),
        "ocena_k": (
            grade_to_text(calculation["final_grade"])
            if calculation is not None
            else ""
        ),
    }
    existing = load_data().get(nr_albumu, {}).get('zal8', {})
    _stamp_sigs(record, 'zal8', existing)
    return _persist(nr_albumu, "zal8", record, "Załącznik 8")




# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – wypełnianie danymi testowymi
# ═══════════════════════════════════════════════════════════════════════════════

def _build_test_data(nr_albumu, effects):
    y = _date.today().year
    uopz_u = User.query.filter_by(role='uopz').first()
    zopz_u = User.query.filter_by(role='zopz').first()
    dziek_u = User.query.filter_by(role='dziekanat').first()
    stud_u = User.query.filter_by(album_number=nr_albumu).first()

    sn = stud_u.full_name if stud_u else "Aleksandra Kowalska"
    un = uopz_u.full_name if uopz_u else "Irena Malinowska"
    zn = zopz_u.full_name if zopz_u else "Zbigniew Ostrowski"
    dn = dziek_u.full_name if dziek_u else "Dorota Kamińska"

    rok = f"{y-1}/{y}"
    ds = f"{y}-04-01"
    de = f"{y}-05-31"
    zaklad = "Techno Systems Sp. z o.o."
    adres = "ul. Portowa 12, 80-001 Gdańsk"
    spec = "Administracja systemów i sieci komputerowych (ASiSK)"

    return {
        "zal1": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "nr_porozumienia": f"ZAL-1-{nr_albumu}", "miejscowosc": "Elbląg",
            "data": _date.today().isoformat(), "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": stud_u.study_mode if stud_u else "stacjonarne", "nazwa_zakladu": zaklad,
            "adres_zakladu": adres, "nip_zakladu": "583-000-11-22",
            "reprezentant_nazwisko": "Jan Wiśniewski",
            "reprezentant_stanowisko": "Prezes Zarządu",
            "email_zakladu": "kontakt@techsolutions.pl",
            "uczelniany_opiekun": un, "data_start": ds, "data_end": de,
            "liczba_godzin": "960",
            "podpis_uczelniany": un,
            "podpis_dziekanatu": dn,
        },
        "zal2": {
            "nr_albumu": nr_albumu, "zaklad_pracy": zaklad,
            "data_start": ds, "data_end": de,
            "data_uzgodnienia": f"{y}-03-20",
            "podpis_zakladowy": "Jan Wiśniewski", "podpis_uczelniany": un,
        },
        "zal2a": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "miejsce_praktyki": f"{zaklad}, {adres}",
            "data_start": ds, "data_end": de,
            "efekty_plan": [{"nr": e.nr, "dzial_prace": "Administracja serwerami i sieciami LAN/WAN"} for e in effects],
            "harmonogram": [
                {"lp": 1, "dzial": "Zapoznanie z infrastrukturą IT", "dni": "5"},
                {"lp": 2, "dzial": "Administracja serwerami Windows Server", "dni": "10"},
                {"lp": 3, "dzial": "Konfiguracja urządzeń sieciowych Cisco", "dni": "10"},
                {"lp": 4, "dzial": "Monitoring sieci i systemy backupu", "dni": "5"},
            ],
            "data_uzgodnienia": f"{y}-03-25",
            "podpis_uczelniany": un, "podpis_zakladowy": zn, "podpis_studenta": sn,
        },
        "zal3": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "nr_porozumienia": f"ZAL-1-{nr_albumu}", "data_porozumienia": f"{y}-03-15",
            "zaklad_pracy": f"{zaklad}, {adres}", "kierunek": "Informatyka",
            "specjalnosc": spec, "rodzaj_studiow": "stacjonarne",
            "uczelniany_opiekun": un, "data_start": ds, "data_end": de,
            "zakladowy_opiekun_nazwisko": zn, "zakladowy_opiekun_funkcja": "Kierownik Działu IT",
            "potwierdzenie_zgloszenia": ds, "potwierdzenie_bhp": ds,
            "zaswiadczenie_zaklad": zaklad, "zaswiadczenie_okres_od": ds,
            "zaswiadczenie_okres_do": de,
            "zaswiadczenie_uwagi": "Student zrealizował program praktyki w całości.",
            "zaswiadczenie_podpis": zn,
            "ocena_zakladowa_param": "bardzo dobry (5)",
            "ocena_zakladowa_opis": "Studentka wykazała się dużym zaangażowaniem i inicjatywą.",
            "podpis_zakladowy": zn,
            "ocena_uczelniana_param": "bardzo dobry (5)",
            "ocena_uczelniana_opis": "Dokumentacja kompletna i rzetelnie wypełniona.",
            "podpis_uczelniany": un,
            "ocena_sprawozdania": "bardzo dobry (5)", "podpis_sprawozdanie": un,
        },
        "zal4": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "wymiar_godzin": "960", "potwierdzenie_opiekuna": zn,
            "opinia_opiekuna": "Studentka w pełni zrealizowała zaplanowane efekty uczenia się.",
            "efekty": [{"nr": e.nr, "status": "osiągnięty"} for e in effects],
        },
        "zal4a": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "data_zlozenia": f"{y}-04-05",
            "ocena_efektow": [{"nr": e.nr, "zasadny": "tak", "uzasadnienie": "Efekt zrealizowany w ramach praktyki."} for e in effects],
            "rekomendacja": "Zalecam zaliczenie efektów w całości.", "uwagi": "",
            "data_oceny": f"{y}-04-10", "podpis_uopz": un,
        },
        "zal4b": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "pracodawca": zaklad, "adres_pracodawcy": adres,
            "stanowisko": "Specjalista ds. systemów IT",
            "okres_od": ds, "okres_do": de,
            "efekty_wniosek": [{"nr": e.nr, "uzasadnienie": "Realizowałam zadania zgodnie z opisem efektu.", "dowody": "Zaświadczenie od pracodawcy"} for e in effects],
            "wykaz_dokumentow": "1. Zaświadczenie o zatrudnieniu\n2. Zakres obowiązków",
            "data": f"{y}-04-05", "podpis_studenta": sn,
        },
        "zal5": {
            "nr_albumu": nr_albumu, "rok_akademicki": rok,
            "kierunek": "Informatyka", "forma_studiow": "stacjonarne",
            "semestr": "6", "liczba_godzin": "960",
            "pytania": [{"nr": i+1, "odpowiedz": "zdecydowanie tak" if i < 12 else "raczej tak"} for i in range(14)],
            "uwagi": "Praktyka przebiegła sprawnie i w miłej atmosferze.",
        },
        "zal6": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne", "rok_akademicki": rok,
            "miejsce_praktyki": f"{zaklad}, {adres}",
            "data_start": ds, "data_end": de,
            "wykaz_zalacznikow": "Zaświadczenie od pracodawcy",
            "dziennik": [
                {"dzien": str(i+1), "data": f"{y}-04-{i+1:02d}",
                 "opis": "Realizacja zadań zgodnie z harmonogramem – administracja systemami IT.",
                 "efekty": "1,2,3", "podpis": ""}
                for i in range(5)
            ],
        },
        "zal7": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne", "rok_akademicki": rok,
            "miejsce_praktyki": f"{zaklad}, {adres}",
            "charakterystyka": f"{zaklad} to firma informatyczna specjalizująca się w administracji infrastrukturą IT i bezpieczeństwie sieci.",
            "opis_prac": "Administracja serwerami Windows Server 2019, konfiguracja przełączników sieciowych Cisco, monitoring sieci Zabbix.",
            "wiedza_umiejetnosci": "Praktyka pozwoliła rozwinąć umiejętności administracji Windows Server i monitoringu infrastruktury IT.",
            "data": f"{y}-06-01", "podpis_studenta": sn, "podpis_przelozonego": "",
        },
        "zal7a": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "niestacjonarne", "rok_akademicki": rok,
            "miejsce_praktyki": f"{zaklad}, {adres}",
            "charakterystyka": f"{zaklad} to firma informatyczna specjalizująca się w administracji infrastrukturą IT.",
            "opis_prac": "Administracja serwerami i sieciami komputerowymi.",
            "wiedza_umiejetnosci": "Pogłębienie wiedzy z zakresu administracji systemami IT.",
            "data": f"{y}-06-01", "podpis_studenta": sn, "podpis_przelozonego": zn,
        },
        "zal8": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "miejsca_praktyki": [{"nazwa": zaklad, "okres": f"{ds} – {de}", "dni": "43"}],
            "ocena_s": "bardzo dobry (5)", "data_s": f"{y}-06-01", "podpis_s": sn,
            "ocena_u": "bardzo dobry (5)", "ocena_z": "bardzo dobry (5)",
            "sklad_komisji": f"1. {dn}\n2. {un}",
            "data_zaliczenia": f"{y}-06-15", "przewodniczacy": dn,
            "czlonek_2": un, "czlonek_3": "", "czlonek_4": "",
            "mini_zadania": [
                {"tresc": "Omów strukturę sieci komputerowej w miejscu praktyki.", "ocena": "bardzo dobry (5)"},
                {"tresc": "Przedstaw zasady administracji serwerem Windows Server.", "ocena": "bardzo dobry (5)"},
                {"tresc": "Opisz zastosowane systemy monitoringu infrastruktury.", "ocena": "bardzo dobry (5)"},
            ],
            "ocena_e": "bardzo dobry (5)", "ocena_k": "bardzo dobry (5)",
        },
    }


@app.route("/admin/wypelnij/<nr_albumu>", methods=["POST"])
@login_required
def admin_fill_test_data(nr_albumu):
    if current_user.role != 'admin':
        flash("Brak uprawnień.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    effects = get_effects()
    test_data = _build_test_data(nr_albumu, effects)
    doc_wf = get_document_workflow()
    for key, record in test_data.items():
        save_form(nr_albumu, key, record)
    for key, record in test_data.items():
        ensure_internship(nr_albumu, key, record, document_status="draft")
        workflow.set_status(nr_albumu, key, "draft",
                            reviewer_role=doc_wf.get(key, {}).get('reviewer'),
                            action='updated', log_comment='dane testowe (admin)')
    flash("Dane testowe wypełnione dla wszystkich formularzy.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURACJA – ustawienia semestru  [dziekanat, admin]
# ═══════════════════════════════════════════════════════════════════════════════

MONTHS_PL = {
    1: 'Styczeń', 2: 'Luty', 3: 'Marzec', 4: 'Kwiecień',
    5: 'Maj', 6: 'Czerwiec', 7: 'Lipiec', 8: 'Sierpień',
    9: 'Wrzesień', 10: 'Październik', 11: 'Listopad', 12: 'Grudzień',
}


@app.route("/konfiguracja", methods=["GET", "POST"])
@login_required
def konfiguracja():
    if current_user.role not in ('dziekanat', 'admin'):
        flash("Brak uprawnień.", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        try:
            summer = max(1, min(12, int(request.form.get('semester_summer_start_month', 3))))
            winter = max(1, min(12, int(request.form.get('semester_winter_start_month', 10))))
        except ValueError:
            summer, winter = 3, 10
        if summer >= winter:
            flash("Miesiąc startu semestru letniego musi być wcześniejszy niż zimowego.", "error")
        else:
            before = {
                "semester_summer_start_month": get_config_value(
                    "semester_summer_start_month", 3,
                ),
                "semester_winter_start_month": get_config_value(
                    "semester_winter_start_month", 10,
                ),
            }
            _set_config_value('semester_summer_start_month', summer,
                              'Miesiąc początku semestru letniego')
            _set_config_value('semester_winter_start_month', winter,
                              'Miesiąc początku semestru zimowego')
            log_action(
                "update", "app_config", "semester",
                before=before,
                after={
                    "semester_summer_start_month": summer,
                    "semester_winter_start_month": winter,
                },
                commit=True,
            )
            flash("Konfiguracja zapisana.", "success")
        if request.args.get("next") == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("konfiguracja"))
    summer = int(get_config_value('semester_summer_start_month', 3))
    winter = int(get_config_value('semester_winter_start_month', 10))
    return render_template("konfiguracja.html",
                           summer_month=summer,
                           winter_month=winter,
                           months=MONTHS_PL,
                           current_semester=get_current_semester())
