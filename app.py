from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, login_user, current_user
from datetime import date as _date
import json
import os

from config import Config
from models import (
    db, User, LearningEffect,
    Specialty, Attachment, RoleFormAccess, StudentWorkflowStep,
    SurveyQuestion, SurveyOption, FormField,
)
from auth import auth_bp, login_manager, authenticate_user, AuthError

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

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
app.register_blueprint(auth_bp)

with app.app_context():
    db.create_all()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_FILE  = os.path.join(DATA_DIR, "studenci.json")

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


def get_form_fields():
    result = {}
    for ff in FormField.query.order_by(FormField.form_key, FormField.sort_order).all():
        result.setdefault(ff.form_key, []).append(ff.field_name)
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    for enc in ('utf-8', 'utf-8-sig', 'cp1250', 'latin-1'):
        try:
            with open(DB_FILE, 'r', encoding=enc) as f:
                data = json.load(f)
            if enc != 'utf-8':
                save_data(data)
            return data
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return {}


def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_effects():
    return LearningEffect.query.order_by(LearningEffect.nr).all()


def is_valid_full_name(v):
    return len(v.split()) >= 2


def is_digits_only(v):
    return v.isdigit()


def can_edit_form(form_key):
    """Czy aktualna rola użytkownika może edytować dany formularz."""
    return form_key in get_role_form_access().get(current_user.role, set())


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
    status = load_data().get(nr_albumu, {}).get(zal_key, {}).get('_status', 'draft')
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
    data = load_data()
    has_other = False
    if nr_albumu in data:
        data[nr_albumu].pop(key, None)
        has_other = bool(data[nr_albumu])
        if not has_other:
            del data[nr_albumu]
        save_data(data)
    return has_other


def build_prefill(nr=''):
    """Returns initial form data with pre-filled fields based on the current user's role."""
    if current_user.role == 'student':
        album = current_user.album_number or ''
        name  = current_user.full_name
        return {'nr_albumu': album, 'imie_nazwisko': name} if (album or name) else None
    base = {'nr_albumu': nr} if nr else {}
    if current_user.role == 'uopz':
        base.update({
            'uczelniany_opiekun': current_user.full_name,
            'podpis_uczelniany':  current_user.full_name,
            'podpis_uopz':        current_user.full_name,
        })
    elif current_user.role == 'zopz':
        base.update({
            'zakladowy_opiekun_nazwisko': current_user.full_name,
            'opiekun_imie_nazwisko':      current_user.full_name,
        })
    return base or None


def _persist(nr_albumu, key, record, label):
    data = load_data()
    data.setdefault(nr_albumu, {})
    existing = data[nr_albumu].get(key, {})
    existing_status = existing.get('_status', 'draft')
    if existing_status in ('pending', 'approved') and current_user.role != 'admin':
        status_label = STATUS_LABELS.get(existing_status, (existing_status,))[0]
        flash(f'Nie mozna zapisac - dokument ma status "{status_label}".', "error")
        return redirect(url_for('student_detail', nr_albumu=nr_albumu))
    if existing_status in ('draft', 'rejected'):
        record['_status'] = 'draft'
        for mk in ('_rejection_comment', '_rejection_by', '_field_comments'):
            record.pop(mk, None)
    else:
        record['_status'] = existing_status
        for mk in ('_rejection_comment', '_rejection_by', '_field_comments'):
            if mk in existing:
                record[mk] = existing[mk]
    data[nr_albumu][key] = record
    save_data(data)
    flash(f"{label} został/a zapisany/a.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


# ── Strony ogólne ─────────────────────────────────────────────────────────────

@app.route("/regulamin")
@login_required
def regulamin():
    return render_template("regulamin.html")


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
    from generate_pdf import generate_pdf
    ctx = dict(
        data=record, nr_albumu=nr_albumu, att=att,
        effects=effects, effect_map=effect_map,
        questions=get_survey_questions(), options=get_survey_options(),
        specialties=get_specialties(), sn=(zal_key == "zal7a"),
    )
    buf = generate_pdf(app, zal_key, ctx)
    filename = f"Zal_{att['nr']}_{nr_albumu}.pdf" if att else f"{zal_key}_{nr_albumu}.pdf"
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
            login_user(user)
            return redirect(url_for("index"))
        except AuthError as exc:
            flash(str(exc), "error")
    return render_template("login.html")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    data = load_data()
    role = current_user.role
    attachments = get_attachments()
    editable = get_role_form_access().get(role, set())

    if role == 'student':
        nr = current_user.album_number or ''
        student_forms = data.get(nr, {}) if nr else {}
        filled = [a["key"] for a in attachments if a["key"] in student_forms]
        name = ""
        for key in ("zal1", "zal2a", "zal6", "zal7", "zal7a"):
            if key in student_forms:
                name = student_forms[key].get("imie_nazwisko", "")
                if name:
                    break
        student_workflow = get_student_workflow()
        workflow = [
            {**step,
             "done": step["key"] in student_forms,
             "status": student_forms.get(step["key"], {}).get('_status', 'draft') if step["key"] in student_forms else ''}
            for step in student_workflow
        ]
        return render_template("index.html",
            role=role, nr_albumu=nr, student_forms=student_forms,
            filled=filled, attachments=attachments,
            workflow=workflow, name=name, editable_forms=editable,
            status_labels=STATUS_LABELS)

    students = []
    for nr in sorted(data.keys()):
        forms = data[nr]
        name = ""
        for key in ("zal3", "zal4", "zal6", "zal1", "zal7", "zal9"):
            if key in forms:
                name = forms[key].get("imie_nazwisko", "")
                if name:
                    break
        filled = [a["key"] for a in attachments if a["key"] in forms]
        students.append({
            "nr_albumu": nr,
            "imie_nazwisko": name,
            "filled": filled,
            "count": len(filled),
        })

    pending_reviews = []
    document_workflow = get_document_workflow()
    if role in ('uopz', 'zopz', 'admin'):
        for nr, forms in data.items():
            student_name = ""
            for key in ("zal3", "zal4", "zal6", "zal1", "zal7", "zal9"):
                if key in forms and isinstance(forms[key], dict):
                    student_name = forms[key].get("imie_nazwisko", "")
                    if student_name:
                        break
            for zal_key, rec in forms.items():
                if not isinstance(rec, dict) or rec.get('_status') != 'pending':
                    continue
                wf = document_workflow.get(zal_key, {})
                rev = wf.get('reviewer')
                if rev and (role == 'admin' or role == rev):
                    att = next((a for a in attachments if a['key'] == zal_key), None)
                    if att:
                        pending_reviews.append({
                            'nr_albumu': nr,
                            'student_name': student_name or nr,
                            'zal_key': zal_key,
                            'att': att,
                            'reviewer_label': wf.get('reviewer_label', ''),
                        })

    return render_template("index.html",
        role=role, students=students, attachments=attachments, editable_forms=editable,
        pending_reviews=pending_reviews)


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
    return render_template("podglad.html",
        nr_albumu=nr_albumu,
        student=student,
        attachments=get_attachments(),
        effect_map=effect_map,
        editable_forms=get_role_form_access().get(current_user.role, set()),
        user_role=current_user.role,
        document_workflow=get_document_workflow(),
        status_labels=STATUS_LABELS,
        form_fields=get_form_fields(),
    )


@app.route("/student/<nr_albumu>/usun", methods=["POST"])
@login_required
def student_delete(nr_albumu):
    if current_user.role not in ('admin', 'dziekanat'):
        flash("Brak uprawnień do usuwania rekordów studenta.", "error")
        return redirect(url_for("index"))
    data = load_data()
    if nr_albumu in data:
        del data[nr_albumu]
        save_data(data)
        flash("Rekord studenta został usunięty.", "success")
    return redirect(url_for("index"))


# ── Workflow: wysyłanie / zatwierdzanie / odrzucanie ─────────────────────────

@app.route("/student/<nr_albumu>/<zal_key>/wyslij", methods=["POST"])
@login_required
def wyslij_do_oceny(nr_albumu, zal_key):
    if current_user.role == 'student' and current_user.album_number != nr_albumu:
        flash("Brak dostępu.", "error")
        return redirect(url_for("index"))
    wf = get_document_workflow().get(zal_key, {})
    if not wf.get('reviewer'):
        flash("Ten formularz nie wymaga zatwierdzenia.", "info")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    data = load_data()
    rec = data.get(nr_albumu, {}).get(zal_key)
    if not rec:
        flash("Formularz nie został jeszcze wypełniony.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    if rec.get('_status') not in ('draft', 'rejected'):
        flash("Dokument jest już w trakcie oceny lub zatwierdzony.", "info")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    rec['_status'] = 'pending'
    rec.pop('_rejection_comment', None)
    rec.pop('_rejection_by', None)
    save_data(data)
    flash(f"Dokument wysłany do zatwierdzenia przez {wf['reviewer_label']}.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


@app.route("/student/<nr_albumu>/<zal_key>/zatwierdz", methods=["POST"])
@login_required
def zatwierdz_dokument(nr_albumu, zal_key):
    wf = get_document_workflow().get(zal_key, {})
    if current_user.role != wf.get('reviewer') and current_user.role != 'admin':
        flash("Nie masz uprawnień do zatwierdzania tego dokumentu.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    data = load_data()
    rec = data.get(nr_albumu, {}).get(zal_key)
    if not rec or rec.get('_status') != 'pending':
        flash("Dokument nie oczekuje na zatwierdzenie.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    rec['_status'] = 'approved'
    rec.pop('_rejection_comment', None)
    rec.pop('_rejection_by', None)
    save_data(data)
    flash("Dokument został zatwierdzony.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


@app.route("/student/<nr_albumu>/<zal_key>/odrzuc", methods=["POST"])
@login_required
def odrzuc_dokument(nr_albumu, zal_key):
    wf = get_document_workflow().get(zal_key, {})
    if current_user.role != wf.get('reviewer') and current_user.role != 'admin':
        flash("Nie masz uprawnień do odrzucania tego dokumentu.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    data = load_data()
    rec = data.get(nr_albumu, {}).get(zal_key)
    if not rec or rec.get('_status') != 'pending':
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
    rec['_status'] = 'rejected'
    rec['_rejection_comment'] = comment
    rec['_rejection_by'] = current_user.full_name
    if field_comments:
        rec['_field_comments'] = field_comments
    else:
        rec.pop('_field_comments', None)
    save_data(data)
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
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko (co najmniej dwa wyrazy).", "error")
        return render_template("zal1.html", data=f, edit_nr=edit_nr, specialties=specialties, nr_locked=nr_locked)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
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
        "podpis_zakladowy": f.get("podpis_zakladowy", "").strip(),
        "podpis_uczelniany": f.get("podpis_uczelniany", "").strip(),
    }
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
    return render_template("zal2.html", data=build_prefill(nr), edit_nr=None)


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
    return render_template("zal2.html", data=existing, edit_nr=nr_albumu)


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
    nr_albumu = f.get("nr_albumu", "").strip()
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal2.html", data=f, edit_nr=edit_nr)
    record = {
        "nr_albumu": nr_albumu,
        "zaklad_pracy": f.get("zaklad_pracy", "").strip(),
        "data_start": f.get("data_start", "").strip(),
        "data_end": f.get("data_end", "").strip(),
        "data_uzgodnienia": f.get("data_uzgodnienia", "").strip(),
        "podpis_zakladowy": f.get("podpis_zakladowy", "").strip(),
        "podpis_uczelniany": f.get("podpis_uczelniany", "").strip(),
    }
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
        "podpis_uczelniany": f.get("podpis_uczelniany", "").strip(),
        "podpis_zakladowy": f.get("podpis_zakladowy", "").strip(),
        "podpis_studenta": f.get("podpis_studenta", "").strip(),
    }
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
        "podpis_zakladowy": f.get("podpis_zakladowy", "").strip(),
        "ocena_uczelniana_param": f.get("ocena_uczelniana_param", "").strip(),
        "ocena_uczelniana_opis": f.get("ocena_uczelniana_opis", "").strip(),
        "podpis_uczelniany": f.get("podpis_uczelniany", "").strip(),
        "ocena_sprawozdania": f.get("ocena_sprawozdania", "").strip(),
        "podpis_sprawozdanie": f.get("podpis_sprawozdanie", "").strip(),
    }
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
        "podpis_uopz": f.get("podpis_uopz", "").strip(),
    }
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
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = student_nr(f.get("nr_albumu", "").strip())
    nr_locked     = (current_user.role == 'student')
    specialties   = get_specialties()
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
        "podpis_studenta": f.get("podpis_studenta", "").strip(),
    }
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
    return render_template("zal6.html", data=existing, edit_nr=nr_albumu,
                           effects=effects, specialties=get_specialties(),
                           nr_locked=(current_user.role == 'student'))


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
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal6.html", data=f, edit_nr=edit_nr, effects=effects,
                               specialties=specialties, nr_locked=nr_locked)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal6.html", data=f, edit_nr=edit_nr, effects=effects,
                               specialties=specialties, nr_locked=nr_locked)
    dni_max = int(f.get("dni_count", "30") or "30")
    dziennik = []
    for i in range(1, dni_max + 1):
        dzien = f.get(f"dzien_{i}", "").strip()
        data_d = f.get(f"data_{i}", "").strip()
        opis = f.get(f"opis_{i}", "").strip()
        efekty = f.get(f"efekty_{i}", "").strip()
        podpis = f.get(f"podpis_{i}", "").strip()
        if dzien or data_d or opis:
            dziennik.append({"dzien": dzien, "data": data_d, "opis": opis, "efekty": efekty, "podpis": podpis})
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
        "podpis_studenta": f.get("podpis_studenta", "").strip(),
        "podpis_przelozonego": f.get("podpis_przelozonego", "").strip(),
    }
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
        "podpis_s": f.get("podpis_s", "").strip(),
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
        "podpis": f.get("podpis", "").strip(),
    }
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
    data = load_data()
    data.setdefault(nr_albumu, {})
    for key, record in test_data.items():
        record.setdefault('_status', 'draft')
        data[nr_albumu][key] = record
    save_data(data)
    flash("Dane testowe wypełnione dla wszystkich formularzy.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true",
    )
