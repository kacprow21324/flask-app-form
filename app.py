from flask import (
    Flask, abort, render_template, request, redirect, session, url_for, flash,
    send_file,
)
from flask_login import login_required, login_user, current_user
from flask_migrate import Migrate
from datetime import date as _date, datetime
import os
import uuid

from core.config import Config
from core.models import (
    db, User, LearningEffect,
    Specialty, Attachment, RoleFormAccess, StudentWorkflowStep,
    SurveyQuestion, SurveyOption, AppConfig, DocumentWorkflow,
    Internship, Notification,
)
from core import workflow
from core import validators
from core.store import (
    delete_form, delete_student_forms, get_form, get_student_forms,
    load_data, save_form,
)
from core.auth import (
    auth_bp, login_manager, authenticate_user, get_debug_login_accounts,
    init_oauth, oauth_provider_status, start_user_session, AuthError,
)
from core.audit import log_action
from core.documents import archive_pdf
from core.internships import (
    current_academic_year,
    ensure_internship,
    get_or_create_internship,
    normalize_academic_year,
)
from core.notifications import notify_user, unread_for
from core.progress import summarize_progress
from core.security import init_security

app = Flask(__name__)
app.config.from_object(Config)
init_security(app)

db.init_app(app)
migrate = Migrate(app, db, compare_type=True)

@app.template_filter('plec')
def detect_gender(name):
    if not name:
        return 'M'
    first = name.strip().split()[0].lower()
    male_a_exceptions = {'kuba', 'seba', 'bonawentura', 'barnaba', 'kosma'}
    if first.endswith('a') and first not in male_a_exceptions:
        return 'K'
    return 'M'

login_manager.init_app(app)
init_oauth(app)
app.register_blueprint(auth_bp)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")  # pliki załączników zostają na dysku; treść formularzy jest w MongoDB

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx',
    'txt', 'csv',
    'zip',
    'png', 'jpg', 'jpeg',
    'xlsx', 'xls',
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# ZOPZ widzi tylko formularze, w których bezpośrednio uczestniczy
ROLE_VISIBLE_FORMS = {
    'zopz': {'zal2a', 'zal3', 'zal4', 'zal6', 'zal7a', 'zal9'},
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
    column = (
        Internship.uopz_id if current_user.role == "uopz"
        else Internship.zopz_id if current_user.role == "zopz"
        else None
    )
    if column is None:
        return set()
    return {
        row[0] for row in db.session.query(User.album_number)
        .join(Internship, Internship.student_id == User.id)
        .filter(column == current_user.id, User.album_number.isnot(None))
        .distinct().all()
    }


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
    return None


def guard_edit(nr_albumu, zal_key):
    """Blokuje edycję gdy dokument oczekuje lub jest zatwierdzony (admin może zawsze)."""
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


def _delete_attachment(nr_albumu, key):
    if delete_form(nr_albumu, key):
        workflow.delete_doc(nr_albumu, key)
    return bool(get_student_forms(nr_albumu))


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


# ─── Fazy obiegu dokumentów ───────────────────────────────────────────────────

WORKFLOW_PHASES = [
    {'nr': 0, 'label': 'Faza 0', 'subtitle': 'Pre-setup',
     'keys': ['zal9', 'zal2']},
    {'nr': 1, 'label': 'Faza 1', 'subtitle': 'Przygotowanie',
     'keys': ['zal1', 'zal2a', 'zal4b', 'zal4a']},
    {'nr': 2, 'label': 'Faza 2', 'subtitle': 'Realizacja',
     'keys': ['zal6']},
    {'nr': 3, 'label': 'Faza 3', 'subtitle': 'Po praktyce',
     'keys': ['zal7', 'zal7a', 'zal5', 'zal3', 'zal4']},
    {'nr': 4, 'label': 'Faza 4', 'subtitle': 'Zaliczenie',
     'keys': ['zal8']},
]

# ─── Auto-signatures ──────────────────────────────────────────────────────────

def _auto_sig():
    """Returns 'FirstName LastName · DD.MM.YYYY' for the current logged-in user."""
    return f"{current_user.first_name} {current_user.last_name} · {_date.today().strftime('%d.%m.%Y')}"

# Fields auto-stamped when the given role SAVES a form.
_SAVE_SIGS = {
    ('zal1',  'uopz'):      ['podpis_uczelniany'],
    ('zal1',  'admin'):     ['podpis_uczelniany'],
    ('zal1',  'zopz'):      ['podpis_zakladowy'],
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
    ('zal9',  'zopz'):      ['podpis'],
    ('zal9',  'admin'):     ['podpis'],
}

# Fields auto-stamped when a reviewer APPROVES a form.
_APPROVE_SIGS = {
    ('zal1',  'uopz'):  ['podpis_uczelniany'],
    ('zal1',  'zopz'):  ['podpis_zakladowy'],
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
        ensure_internship(
            nr_albumu, key, record, document_status=existing_status,
        )
        reviewer_role = get_document_workflow().get(key, {}).get('reviewer')
        action = ('created' if existing_status == 'draft' and not existing else 'updated')
        workflow.set_status(nr_albumu, key, existing_status,
                            reviewer_role=reviewer_role, action=action)

    if transition_done:
        reviewer_label = get_document_workflow().get(key, {}).get('reviewer_label', 'recenzenta')
        flash(f"{label} poprawiony/a i wysłany/a ponownie do: {reviewer_label}.", "success")
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


@app.route("/regulamin")
@login_required
def regulamin():
    return render_template("regulamin.html")


@app.route("/powiadomienia")
@login_required
def powiadomienia():
    try:
        notifs = _build_notifications()
    except Exception:
        notifs = []
    return render_template("powiadomienia.html", notifications=notifs)


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
    requested_year = request.args.get("rok")
    selected_year = normalize_academic_year(
        requested_year,
        default_current=not requested_year,
    )
    if selected_year is None:
        abort(400, description="Nieprawidłowy rok akademicki.")

    attachments = get_attachments()
    if current_user.role == "zopz":
        attachments = [
            item for item in attachments
            if item["key"] in ROLE_VISIBLE_FORMS["zopz"]
        ]
    att_map = {a['key']: a for a in attachments}
    visible_keys = set(att_map)
    phases = [
        {**phase, "keys": [key for key in phase["keys"] if key in visible_keys]}
        for phase in WORKFLOW_PHASES
    ]
    phases = [phase for phase in phases if phase["keys"]]

    years_query = db.session.query(Internship.academic_year).distinct()
    if current_user.role == "student":
        years_query = years_query.filter(Internship.student_id == current_user.id)
    elif current_user.role == "uopz":
        years_query = years_query.filter(Internship.uopz_id == current_user.id)
    elif current_user.role == "zopz":
        years_query = years_query.filter(Internship.zopz_id == current_user.id)
    academic_years = sorted(
        {row[0] for row in years_query.all()} | {current_academic_year()},
        reverse=True,
    )

    if current_user.role == 'student':
        nr = current_user.album_number
        if not nr:
            flash("Brak numeru albumu — skontaktuj się z administratorem.", "error")
            return redirect(url_for("index"))
        wf_rows = DocumentWorkflow.query.filter(
            DocumentWorkflow.album_number == nr,
            DocumentWorkflow.form_key.in_(visible_keys),
        ).all()
        status_map = {r.form_key: r.status for r in wf_rows}
        internship = Internship.query.filter_by(
            student_id=current_user.id,
            academic_year=selected_year,
        ).first()
        progress = summarize_progress(
            wf_rows,
            len(visible_keys),
            internship=internship,
        )
        return render_template("obieg.html",
            phases=phases, att_map=att_map,
            status_map=status_map, nr_albumu=nr,
            role=current_user.role, progress=progress,
            internship=internship, academic_years=academic_years,
            selected_year=selected_year,
        )

    internships_query = Internship.query.filter_by(academic_year=selected_year)
    if current_user.role == "uopz":
        internships_query = internships_query.filter_by(uopz_id=current_user.id)
    elif current_user.role == "zopz":
        internships_query = internships_query.filter_by(zopz_id=current_user.id)
    internships = internships_query.all()
    internship_by_student = {item.student_id: item for item in internships}

    students_query = User.query.filter_by(role="student")
    if current_user.role in ("uopz", "zopz"):
        students_query = students_query.filter(
            User.id.in_(set(internship_by_student))
        )
    students = students_query.order_by(User.last_name, User.first_name).all()
    album_numbers = [
        student.album_number for student in students if student.album_number
    ]
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

    progress_by_student = {
        student.album_number: summarize_progress(
            wf_rows_by_student.get(student.album_number, []),
            len(visible_keys),
            internship=internship_by_student.get(student.id),
            reviewer_role=current_user.role,
        )
        for student in students
    }

    # Podsumowanie per klucz formularza
    all_keys = [k for ph in phases for k in ph['keys']]
    summary = {}
    for key in all_keys:
        counts = {'approved': 0, 'pending': 0, 'rejected': 0, 'draft': 0, 'none': 0}
        for s in students:
            st = wf_by_student.get(s.album_number, {}).get(key)
            counts[st if st else 'none'] += 1
        summary[key] = counts

    return render_template("obieg.html",
        phases=phases, att_map=att_map,
        students=students, wf_by_student=wf_by_student,
        summary=summary, role=current_user.role,
        progress_by_student=progress_by_student,
        internship_by_student=internship_by_student,
        academic_years=academic_years,
        selected_year=selected_year,
    )


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
            return redirect(url_for("przydzialy", rok=selected_year))

        log_action(
            "assign",
            "internship",
            internship.id,
            before=before,
            after=after,
        )

        link = url_for("obieg", rok=selected_year)
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
                    url_for("obieg", rok=selected_year),
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
                url_for("obieg", rok=selected_year),
                entity_type="internship",
                entity_id=internship.id,
                dedupe_key=f"internship-assignment-student-{internship.id}",
            )
        db.session.commit()
        flash("Przydział opiekunów został zapisany.", "success")
        return redirect(url_for("przydzialy", rok=selected_year))

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


@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    if request.method == "POST":
        before = {
            "speciality": current_user.speciality,
            "study_mode": current_user.study_mode,
            "semester": current_user.semester,
            "study_year": current_user.study_year,
        }
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
        data=rec, edit_nr=nr_albumu,
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
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    attachments = get_attachments()
    valid_keys = {a["key"] for a in attachments}
    if zal_key not in valid_keys:
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    store = load_data()
    record = store.get(nr_albumu, {}).get(zal_key)
    if not record:
        flash("Brak danych do pobrania.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    effects = get_effects()
    effect_map = {e.nr: e.opis for e in effects}
    att = next((a for a in attachments if a["key"] == zal_key), None)
    from core.generate_pdf_latex import generate_pdf_latex
    ctx = dict(
        data=record, nr_albumu=nr_albumu, att=att,
        effects=effects, effect_map=effect_map,
        questions=get_survey_questions(), options=get_survey_options(),
        specialties=get_specialties(), sn=(zal_key == "zal7a"),
    )
    try:
        buf = generate_pdf_latex(zal_key, ctx)
    except FileNotFoundError:
        flash("Brak szablonu LaTeX dla tego załącznika.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    except RuntimeError as exc:
        app.logger.error("xelatex failed: %s", exc)
        flash("Błąd generowania PDF przez LaTeX. Sprawdź logi serwera.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    filename = f"Zal_{att['nr']}_{nr_albumu}.pdf" if att else f"{zal_key}_{nr_albumu}.pdf"
    pdf_bytes = buf.getvalue()
    internship = ensure_internship(nr_albumu, zal_key, record)
    document, _ = archive_pdf(
        pdf_bytes,
        base_dir=DATA_DIR,
        album_number=nr_albumu,
        form_key=zal_key,
        file_name=filename,
        generated_by=current_user,
        internship=internship,
    )
    db.session.flush()
    log_action(
        "download",
        "generated_document",
        document.id,
        after={
            "album_number": nr_albumu,
            "form_key": zal_key,
            "checksum_sha256": document.checksum_sha256,
        },
    )
    db.session.commit()
    return send_file(buf, as_attachment=True, download_name=filename, mimetype="application/pdf")


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
    store = load_data()
    student = store.get(nr_albumu, {})
    record = student.get(zal_key)
    if not record:
        flash("Brak danych do wydruku.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    effects = get_effects()
    effect_map = {e.nr: e.opis for e in effects}
    att = next((a for a in attachments if a["key"] == zal_key), None)
    sn = (zal_key == "zal7a")
    return render_template(f"print/{zal_key}.html",
        data=record, nr_albumu=nr_albumu, att=att,
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
        data=existing, edit_nr=nr_albumu,
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
        student_workflow = get_student_workflow()
        student_statuses = workflow.get_statuses(nr)
        workflow_steps = [
            {**step,
             "done": step["key"] in student_forms,
             "status": student_statuses.get(step["key"], "draft") if step["key"] in student_forms else ''}
            for step in student_workflow
        ]
        return render_template("index.html",
            role=role, nr_albumu=nr, student_forms=student_forms,
            filled=filled, attachments=attachments,
            workflow=workflow_steps, name=name, editable_forms=editable,
            status_labels=STATUS_LABELS)

    selected_year = current_academic_year()
    internships_query = Internship.query.filter_by(academic_year=selected_year)
    if role == "uopz":
        internships_query = internships_query.filter_by(uopz_id=current_user.id)
    elif role == "zopz":
        internships_query = internships_query.filter_by(zopz_id=current_user.id)
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
        rows = wf_rows_by_student.get(nr, [])
        sw = wf_by_student.get(nr, {})
        progress = summarize_progress(
            rows,
            len(visible_keys),
            internship=internship_by_student.get(user.id),
            reviewer_role=role,
        )
        students.append({
            "nr_albumu": nr,
            "imie_nazwisko": user.full_name,
            "speciality": user.speciality or "",
            "study_mode": user.study_mode or "stacjonarne",
            "filled": list(sw),
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

    pending_reviews = []
    document_workflow = get_document_workflow()
    if role in ('uopz', 'zopz', 'admin'):
        users_by_album = {
            user.album_number: user for user in student_users if user.album_number
        }
        for row in all_wf:
            if row.status == "pending":
                wf = document_workflow.get(row.form_key, {})
                rev = wf.get('reviewer')
                if rev and (role == 'admin' or role == rev):
                    att = next(
                        (a for a in attachments if a['key'] == row.form_key),
                        None,
                    )
                    if att:
                        student_user = users_by_album.get(row.album_number)
                        pending_reviews.append({
                            'nr_albumu': row.album_number,
                            'student_name': (
                                student_user.full_name
                                if student_user else row.album_number
                            ),
                            'zal_key': row.form_key,
                            'att': att,
                            'reviewer_label': wf.get('reviewer_label', ''),
                        })

    return render_template("index.html",
        role=role, students=students, attachments=attachments, editable_forms=editable,
        pending_reviews=pending_reviews, selected_year=selected_year)


# ── Szczegóły studenta ────────────────────────────────────────────────────────

@app.route("/student/<nr_albumu>")
@login_required
def student_detail(nr_albumu):
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu do tego rekordu.", "error")
        return redirect(url_for("index"))
    data = load_data()
    student = data.get(nr_albumu)
    if not student:
        flash("Brak danych dla tego numeru albumu.", "error")
        return redirect(url_for("index"))
    effect_map = {e.nr: e.opis for e in get_effects()}
    all_atts = get_attachments()
    visible_keys = ROLE_VISIBLE_FORMS.get(current_user.role)
    filtered_atts = [a for a in all_atts if visible_keys is None or a['key'] in visible_keys]
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
    return render_template("podglad.html",
        nr_albumu=nr_albumu,
        student=student,
        attachments=filtered_atts,
        effect_map=effect_map,
        editable_forms=get_role_form_access().get(current_user.role, set()),
        user_role=current_user.role,
        document_workflow=get_document_workflow(),
        workflow_states=workflow_states,
        status_labels=STATUS_LABELS,
        logs_by_key=logs_by_key,
        approval_by_key=approval_by_key,
        att_nr=att_nr,
    )


@app.route("/student/<nr_albumu>/usun", methods=["POST"])
@login_required
def student_delete(nr_albumu):
    if current_user.role not in ('admin', 'dziekanat'):
        flash("Brak uprawnień do usuwania rekordów studenta.", "error")
        return redirect(url_for("index"))
    keys = delete_student_forms(nr_albumu)
    if keys:
        for k in keys:
            workflow.delete_doc(nr_albumu, k)
        flash("Rekord studenta został usunięty.", "success")
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
    # FSM: walidacja przejścia
    current_state = workflow.get_status(nr_albumu, zal_key)
    try:
        DocumentFSM.transition(current_state, 'submit')
    except InvalidTransition:
        flash("Dokument jest już w trakcie oceny lub zatwierdzony.", "info")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    # FSM: ostrzeżenia o niespełnionych zależnościach fazowych (miękkie)
    statuses = workflow.get_statuses(nr_albumu)
    unmet = DocumentFSM.check_prerequisites(zal_key, statuses)
    for u in unmet:
        zal_nr = next((a['nr'] for a in get_attachments() if a['key'] == u['form_key']), u['form_key'])
        flash(
            f"Uwaga: Zał. {zal_nr} powinien mieć status "
            f"'{DocumentFSM.STATE_LABELS.get(u['required_status'], u['required_status'])}' "
            f"przed wysłaniem tego dokumentu (teraz: '{DocumentFSM.STATE_LABELS.get(u['actual'], u['actual'])}').",
            "warning"
        )
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
    return render_template("zal1.html", data=build_prefill(nr),
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
    existing = load_data().get(nr_albumu, {}).get("zal1")
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
    errors = []
    for ok, msg in (
        validators.is_valid_full_name(imie_nazwisko),
        validators.is_valid_album(nr_albumu),
        validators.is_valid_date(f.get("data", ""), required=False),
        validators.validate_nip(f.get("nip_zakladu", ""), required=False),
        validators.validate_date_range(f.get("data_start", ""), f.get("data_end", "")),
    ):
        if not ok:
            errors.append(msg)
    if errors:
        for m in errors:
            flash(m, "error")
        return render_template("zal1.html", data=f, edit_nr=edit_nr, specialties=specialties, nr_locked=nr_locked)
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "nr_porozumienia": f.get("nr_porozumienia", "").strip(),
        "miejscowosc": f.get("miejscowosc", "").strip(),
        "data": f.get("data", "").strip(),
        "kierunek": "Informatyka",
        "specjalnosc": f.get("specjalnosc", "").strip(),
        "rodzaj_studiow": f.get("rodzaj_studiow", "stacjonarne"),
        "nazwa_zakladu": f.get("nazwa_zakladu", "").strip(),
        "adres_zakladu": f.get("adres_zakladu", "").strip(),
        "nip_zakladu": f.get("nip_zakladu", "").strip(),
        "reprezentant_nazwisko": f.get("reprezentant_nazwisko", "").strip(),
        "reprezentant_stanowisko": f.get("reprezentant_stanowisko", "").strip(),
        "uczelniany_opiekun": f.get("uczelniany_opiekun", "").strip(),
        "data_start": f.get("data_start", "").strip(),
        "data_end": f.get("data_end", "").strip(),
        "liczba_godzin": f.get("liczba_godzin", "960").strip(),
    }
    existing = load_data().get(nr_albumu, {}).get('zal1', {})
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
    return render_template("zal2.html", data=existing, edit_nr=nr_albumu, effects=get_effects())


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
    return render_template("zal2a.html", data=existing, edit_nr=nr_albumu,
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
    return render_template("zal3.html", data=existing, edit_nr=nr_albumu, specialties=get_specialties())


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
    return render_template("zal4.html", data=existing, edit_nr=nr_albumu,
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
    return render_template("zal4a.html", data=existing, edit_nr=nr_albumu, effects=effects)


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
                           nr_locked=(current_user.role == 'student'))


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
    return render_template("zal4b.html", data=existing, edit_nr=nr_albumu,
                           effects=effects, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'))


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
                                   specialties=specialties, nr_locked=nr_locked)
        if not nr_albumu or not is_digits_only(nr_albumu):
            flash("Numer albumu może zawierać tylko cyfry.", "error")
            return render_template("zal4b.html", data=f, edit_nr=edit_nr, effects=effects,
                                   specialties=specialties, nr_locked=nr_locked)
        efekty_wniosek = [
            {"nr": e.nr,
             "uzasadnienie": f.get(f"uzasadnienie_{e.nr}", "").strip(),
             "dowody": f.get(f"dowody_{e.nr}", "").strip()}
            for e in effects
        ]
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
            "wykaz_dokumentow": f.get("wykaz_dokumentow", "").strip(),
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
                                   effects=effects, specialties=specialties, nr_locked=nr_locked)
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
            "wykaz_dokumentow": existing.get("wykaz_dokumentow", ""),
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
    return render_template("zal5.html", data=existing, edit_nr=nr_albumu,
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
    return render_template("zal6.html", data=existing, edit_nr=nr_albumu,
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
    return render_template("zal7.html", data=existing, edit_nr=nr_albumu, specialties=get_specialties(),
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
    return render_template("zal7.html", data=existing, edit_nr=nr_albumu, specialties=get_specialties(),
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
    return render_template("zal8.html", data=existing, edit_nr=nr_albumu)


@app.route("/zal8/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal8_delete(nr_albumu):
    guard = guard_form('zal8')
    if guard: return guard
    has_other = _delete_attachment(nr_albumu, "zal8")
    flash("Załącznik 8 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


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
        "ocena_k": f.get("ocena_k", "").strip(),
    }
    existing = load_data().get(nr_albumu, {}).get('zal8', {})
    _stamp_sigs(record, 'zal8', existing)
    return _persist(nr_albumu, "zal8", record, "Załącznik 8")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 9 – Oświadczenie instytucji  [zopz]
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal9", methods=["GET", "POST"])
@login_required
def zal9():
    guard = guard_form('zal9')
    if guard: return guard
    if request.method == "POST":
        return _save_zal9(None)
    nr = request.args.get("nr", "")
    return render_template("zal9.html", data=build_prefill(nr), edit_nr=None)


@app.route("/zal9/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal9_edit(nr_albumu):
    guard = guard_form('zal9')
    if guard: return guard
    guard_e = guard_edit(nr_albumu, 'zal9')
    if guard_e: return guard_e
    if request.method == "POST":
        return _save_zal9(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal9")
    return render_template("zal9.html", data=existing, edit_nr=nr_albumu)


@app.route("/zal9/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal9_delete(nr_albumu):
    guard = guard_form('zal9')
    if guard: return guard
    has_other = _delete_attachment(nr_albumu, "zal9")
    flash("Załącznik 9 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal9(edit_nr):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko studenta.", "error")
        return render_template("zal9.html", data=f, edit_nr=edit_nr)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal9.html", data=f, edit_nr=edit_nr)
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "miejscowosc": f.get("miejscowosc", "").strip(),
        "data": f.get("data", "").strip(),
        "nazwa_instytucji": f.get("nazwa_instytucji", "").strip(),
        "termin_od": f.get("termin_od", "").strip(),
        "termin_do": f.get("termin_do", "").strip(),
        "opiekun_imie_nazwisko": f.get("opiekun_imie_nazwisko", "").strip(),
        "opiekun_stanowisko": f.get("opiekun_stanowisko", "").strip(),
        "opiekun_telefon": f.get("opiekun_telefon", "").strip(),
        "opiekun_email": f.get("opiekun_email", "").strip(),
        "upowazniont_imie_nazwisko": f.get("upowazniont_imie_nazwisko", "").strip(),
        "upowazniont_stanowisko": f.get("upowazniont_stanowisko", "").strip(),
    }
    existing = load_data().get(nr_albumu, {}).get('zal9', {})
    _stamp_sigs(record, 'zal9', existing)
    return _persist(nr_albumu, "zal9", record, "Załącznik 9")


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
            "nr_porozumienia": f"PZ/{y}/001", "miejscowosc": "Elbląg",
            "data": f"{y}-03-15", "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne", "nazwa_zakladu": zaklad,
            "adres_zakladu": adres, "nip_zakladu": "583-000-11-22",
            "reprezentant_nazwisko": "Jan Wiśniewski",
            "reprezentant_stanowisko": "Prezes Zarządu",
            "uczelniany_opiekun": un, "data_start": ds, "data_end": de,
            "liczba_godzin": "240", "podpis_zakladowy": "Jan Wiśniewski",
            "podpis_uczelniany": un,
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
            "nr_porozumienia": f"PZ/{y}/001", "data_porozumienia": f"{y}-03-15",
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
            "wymiar_godzin": "240", "potwierdzenie_opiekuna": zn,
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
            "semestr": "6", "liczba_godzin": "240",
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
        "zal9": {
            "imie_nazwisko": sn, "nr_albumu": nr_albumu,
            "miejscowosc": "Gdańsk", "data": ds,
            "nazwa_instytucji": zaklad,
            "termin_od": ds, "termin_do": de,
            "opiekun_imie_nazwisko": zn, "opiekun_stanowisko": "Kierownik Działu IT",
            "opiekun_telefon": "+48 58 123 45 67",
            "opiekun_email": "z.ostrowski@technosystems.pl",
            "upowazniont_imie_nazwisko": "Jan Wiśniewski",
            "upowazniont_stanowisko": "Prezes Zarządu",
            "podpis": "Jan Wiśniewski",
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
        return redirect(url_for("konfiguracja"))
    summer = int(get_config_value('semester_summer_start_month', 3))
    winter = int(get_config_value('semester_winter_start_month', 10))
    return render_template("konfiguracja.html",
                           summer_month=summer,
                           winter_month=winter,
                           months=MONTHS_PL,
                           current_semester=get_current_semester())


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )
