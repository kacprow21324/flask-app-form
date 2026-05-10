from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, login_user, current_user
import json
import os
from generate_docx import generate as docx_generate

from config import Config
from models import db, User, LearningEffect
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

SPECIALTIES = [
    "Administracja systemów i sieci komputerowych (ASiSK)",
    "Projektowanie baz danych i oprogramowanie użytkowe (PBDiOU)",
    "Modelowanie 3D w zastosowaniach medycznych, prototypowaniu i mediach interaktywnych (M3D)",
]

ATTACHMENTS = [
    {"key": "zal1",  "nr": "1",  "title": "Porozumienie z zakładem pracy"},
    {"key": "zal2",  "nr": "2",  "title": "Program praktyki zawodowej"},
    {"key": "zal2a", "nr": "2a", "title": "Program i harmonogram praktyki"},
    {"key": "zal3",  "nr": "3",  "title": "Karta praktyki zawodowej"},
    {"key": "zal4",  "nr": "4",  "title": "Potwierdzenie efektów uczenia się"},
    {"key": "zal4a", "nr": "4a", "title": "Merytoryczna ocena wniosku studenta"},
    {"key": "zal4b", "nr": "4b", "title": "Wniosek o zaliczenie efektów uczenia się"},
    {"key": "zal5",  "nr": "5",  "title": "Kwestionariusz ankiety"},
    {"key": "zal6",  "nr": "6",  "title": "Dziennik praktyki zawodowej"},
    {"key": "zal7",  "nr": "7",  "title": "Sprawozdanie z praktyki zawodowej"},
    {"key": "zal7a", "nr": "7a", "title": "Sprawozdanie z praktyki (niestacjonarne)"},
    {"key": "zal8",  "nr": "8",  "title": "Protokół zaliczenia praktyki"},
    {"key": "zal9",  "nr": "9",  "title": "Oświadczenie instytucji"},
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    for enc in ('utf-8', 'utf-8-sig', 'cp1250', 'latin-1'):
        try:
            with open(DB_FILE, 'r', encoding=enc) as f:
                data = json.load(f)
            if enc != 'utf-8':
                save_data(data)  # re-save as UTF-8
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


def _persist(nr_albumu, key, record, label):
    data = load_data()
    data.setdefault(nr_albumu, {})
    data[nr_albumu][key] = record
    save_data(data)
    flash(f"{label} został/a zapisany/a.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu))


# ── Logowanie ─────────────────────────────────────────────────────────────────

@app.route("/regulamin")
@login_required
def regulamin():
    return render_template("regulamin.html")


@app.route("/student/<nr_albumu>/<zal_key>/pobierz")
@login_required
def pobierz_docx(nr_albumu, zal_key):
    valid_keys = {a["key"] for a in ATTACHMENTS}
    if zal_key not in valid_keys:
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    store = load_data()
    record = store.get(nr_albumu, {}).get(zal_key)
    if not record:
        flash("Brak danych do pobrania.", "error")
        return redirect(url_for("student_detail", nr_albumu=nr_albumu))
    effects = get_effects()
    buf = docx_generate(zal_key, record, effects)
    att = next((a for a in ATTACHMENTS if a["key"] == zal_key), None)
    filename = f"Zal_{att['nr']}_{nr_albumu}.docx" if att else f"{zal_key}_{nr_albumu}.docx"
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.route("/student/<nr_albumu>/<zal_key>/drukuj")
@login_required
def drukuj(nr_albumu, zal_key):
    valid_keys = {a["key"] for a in ATTACHMENTS}
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
    att = next((a for a in ATTACHMENTS if a["key"] == zal_key), None)
    sn = (zal_key == "zal7a")
    return render_template(f"print/{zal_key}.html",
        data=record, nr_albumu=nr_albumu, att=att,
        effects=effects, effect_map=effect_map,
        questions=SURVEY_QUESTIONS, options=SURVEY_OPTIONS,
        specialties=SPECIALTIES, sn=sn)


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
    students = []
    for nr in sorted(data.keys()):
        forms = data[nr]
        name = ""
        for key in ("zal3", "zal4", "zal6", "zal1", "zal7", "zal9"):
            if key in forms:
                name = forms[key].get("imie_nazwisko", "")
                if name:
                    break
        filled = [a["key"] for a in ATTACHMENTS if a["key"] in forms]
        students.append({
            "nr_albumu": nr,
            "imie_nazwisko": name,
            "filled": filled,
            "count": len(filled),
        })
    return render_template("index.html", students=students, attachments=ATTACHMENTS)


# ── Szczegóły studenta ────────────────────────────────────────────────────────

@app.route("/student/<nr_albumu>")
@login_required
def student_detail(nr_albumu):
    data = load_data()
    student = data.get(nr_albumu)
    if not student:
        flash("Brak danych dla tego numeru albumu.", "error")
        return redirect(url_for("index"))
    effect_map = {e.nr: e.opis for e in get_effects()}
    return render_template("podglad.html",
        nr_albumu=nr_albumu,
        student=student,
        attachments=ATTACHMENTS,
        effect_map=effect_map,
    )


@app.route("/student/<nr_albumu>/usun", methods=["POST"])
@login_required
def student_delete(nr_albumu):
    data = load_data()
    if nr_albumu in data:
        del data[nr_albumu]
        save_data(data)
        flash("Rekord studenta został usunięty.", "success")
    return redirect(url_for("index"))


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 1 – Porozumienie z zakładem pracy
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal1", methods=["GET", "POST"])
@login_required
def zal1():
    if request.method == "POST":
        return _save_zal1(None)
    nr = request.args.get("nr", "")
    return render_template("zal1.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, specialties=SPECIALTIES)


@app.route("/zal1/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal1_edit(nr_albumu):
    if request.method == "POST":
        return _save_zal1(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal1")
    return render_template("zal1.html", data=existing, edit_nr=nr_albumu, specialties=SPECIALTIES)


@app.route("/zal1/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal1_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal1")
    flash("Załącznik 1 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal1(edit_nr):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko (co najmniej dwa wyrazy).", "error")
        return render_template("zal1.html", data=f, edit_nr=edit_nr, specialties=SPECIALTIES)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal1.html", data=f, edit_nr=edit_nr, specialties=SPECIALTIES)
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
# ZAŁ. 2 – Program praktyki zawodowej
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal2", methods=["GET", "POST"])
@login_required
def zal2():
    if request.method == "POST":
        return _save_zal2(None)
    nr = request.args.get("nr", "")
    return render_template("zal2.html", data={"nr_albumu": nr} if nr else None, edit_nr=None)


@app.route("/zal2/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal2_edit(nr_albumu):
    if request.method == "POST":
        return _save_zal2(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal2")
    return render_template("zal2.html", data=existing, edit_nr=nr_albumu)


@app.route("/zal2/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal2_delete(nr_albumu):
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
# ZAŁ. 2a – Program i harmonogram
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal2a", methods=["GET", "POST"])
@login_required
def zal2a():
    effects = get_effects()
    if request.method == "POST":
        return _save_zal2a(None, effects)
    nr = request.args.get("nr", "")
    return render_template("zal2a.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, effects=effects, specialties=SPECIALTIES)


@app.route("/zal2a/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal2a_edit(nr_albumu):
    effects = get_effects()
    if request.method == "POST":
        return _save_zal2a(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal2a")
    return render_template("zal2a.html", data=existing, edit_nr=nr_albumu,
                           effects=effects, specialties=SPECIALTIES)


@app.route("/zal2a/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal2a_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal2a")
    flash("Załącznik 2a został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal2a(edit_nr, effects):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal2a.html", data=f, edit_nr=edit_nr, effects=effects, specialties=SPECIALTIES)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal2a.html", data=f, edit_nr=edit_nr, effects=effects, specialties=SPECIALTIES)
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
# ZAŁ. 3 – Karta praktyki zawodowej
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal3", methods=["GET", "POST"])
@login_required
def zal3():
    if request.method == "POST":
        return _save_zal3(None)
    nr = request.args.get("nr", "")
    return render_template("zal3.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, specialties=SPECIALTIES)


@app.route("/zal3/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal3_edit(nr_albumu):
    if request.method == "POST":
        return _save_zal3(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal3")
    return render_template("zal3.html", data=existing, edit_nr=nr_albumu, specialties=SPECIALTIES)


@app.route("/zal3/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal3_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal3")
    flash("Załącznik 3 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal3(edit_nr):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal3.html", data=f, edit_nr=edit_nr, specialties=SPECIALTIES)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal3.html", data=f, edit_nr=edit_nr, specialties=SPECIALTIES)
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
# ZAŁ. 4 – Potwierdzenie efektów uczenia się
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal4", methods=["GET", "POST"])
@login_required
def zal4():
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4(None, effects)
    nr = request.args.get("nr", "")
    return render_template("zal4.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, effects=effects, specialties=SPECIALTIES)


@app.route("/zal4/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal4_edit(nr_albumu):
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal4")
    return render_template("zal4.html", data=existing, edit_nr=nr_albumu,
                           effects=effects, specialties=SPECIALTIES)


@app.route("/zal4/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal4_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal4")
    flash("Załącznik 4 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal4(edit_nr, effects):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal4.html", data=f, edit_nr=edit_nr, effects=effects, specialties=SPECIALTIES)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal4.html", data=f, edit_nr=edit_nr, effects=effects, specialties=SPECIALTIES)
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "kierunek": "Informatyka",
        "specjalnosc": f.get("specjalnosc", "").strip(),
        "wymiar_godzin": f.get("wymiar_godzin", "960").strip(),
        "potwierdzenie_opiekuna": f.get("potwierdzenie_opiekuna", "").strip(),
        "opinia_opiekuna": f.get("opinia_opiekuna", "").strip(),
        "efekty": [{"nr": e.nr, "status": f.get(f"efekt_{e.nr}", "")} for e in effects],
    }
    return _persist(nr_albumu, "zal4", record, "Załącznik 4")


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 4a – Merytoryczna ocena wniosku studenta
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal4a", methods=["GET", "POST"])
@login_required
def zal4a():
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4a(None, effects)
    nr = request.args.get("nr", "")
    return render_template("zal4a.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, effects=effects)


@app.route("/zal4a/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal4a_edit(nr_albumu):
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4a(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal4a")
    return render_template("zal4a.html", data=existing, edit_nr=nr_albumu, effects=effects)


@app.route("/zal4a/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal4a_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal4a")
    flash("Załącznik 4a został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal4a(edit_nr, effects):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal4a.html", data=f, edit_nr=edit_nr, effects=effects)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal4a.html", data=f, edit_nr=edit_nr, effects=effects)
    ocena_efektow = [
        {"nr": e.nr, "zasadny": f.get(f"zasadny_{e.nr}", ""), "uzasadnienie": f.get(f"uzasadnienie_{e.nr}", "").strip()}
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
# ZAŁ. 4b – Wniosek o zaliczenie efektów uczenia się
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal4b", methods=["GET", "POST"])
@login_required
def zal4b():
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4b(None, effects)
    nr = request.args.get("nr", "")
    return render_template("zal4b.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, effects=effects, specialties=SPECIALTIES)


@app.route("/zal4b/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal4b_edit(nr_albumu):
    effects = get_effects()
    if request.method == "POST":
        return _save_zal4b(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal4b")
    return render_template("zal4b.html", data=existing, edit_nr=nr_albumu,
                           effects=effects, specialties=SPECIALTIES)


@app.route("/zal4b/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal4b_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal4b")
    flash("Załącznik 4b został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal4b(edit_nr, effects):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal4b.html", data=f, edit_nr=edit_nr, effects=effects, specialties=SPECIALTIES)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal4b.html", data=f, edit_nr=edit_nr, effects=effects, specialties=SPECIALTIES)
    efekty_wniosek = [
        {"nr": e.nr, "uzasadnienie": f.get(f"uzasadnienie_{e.nr}", "").strip(),
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
# ZAŁ. 5 – Kwestionariusz ankiety
# ═══════════════════════════════════════════════════════════════════════════════

SURVEY_QUESTIONS = [
    "Poznałam/poznałem zasady funkcjonowania instytucji, w której odbywałam/odbywałem praktyki zawodowe.",
    "Poznałam/poznałem strukturę oraz regulamin organizacyjny instytucji, w której odbywałam/odbywałem praktyki zawodowe.",
    "Praktyki zawodowe umożliwiły mi pełną realizację ramowego programu praktyk zawodowych przewidzianego w ramach mojego kierunku studiów.",
    "Podczas praktyk zawodowych zwracano uwagę na przestrzeganie zasad etyki i tajemnicy zawodowej.",
    "Podczas praktyk miałam/miałem możliwość praktycznego zastosowania wiedzy teoretycznej zdobytej na zajęciach.",
    "Praktyki zawodowe przyczyniły się do pogłębienia mojej wiedzy i umiejętności zdobytych w trakcie studiów.",
    "Mogłem liczyć na wsparcie merytoryczne Opiekuna zakładowego praktyk.",
    "Mogłem liczyć na wsparcie merytoryczne Opiekuna uczelnianego praktyk.",
    "Opiekun zakładowy odpowiedzialny za praktyki zawodowe w miejscu ich odbywania potrafił prawidłowo zorganizować ich przebieg.",
    "Podczas praktyk zawodowych miałam/miałem możliwość pozyskiwania materiałów niezbędnych do przygotowania mojej pracy dyplomowej.",
    "Praktyki zawodowe rozwinęły moje umiejętności skutecznego komunikowania się w sytuacjach zawodowych i pracy w zespole.",
    "Praktyki zawodowe nauczyły mnie samodzielności i odpowiedzialności podczas wykonywania pracy.",
    "Liczba godzin realizowana w ramach praktyk zawodowych jest wystarczająca.",
    "Czy po zakończeniu praktyki zawodowej chciałaby/chciałby Pani/Pan współpracować z instytucją, w której Pani/Pan zrealizowała/zrealizował praktykę?",
]

SURVEY_OPTIONS = ["zdecydowanie tak", "raczej tak", "trudno powiedzieć", "raczej nie", "zdecydowanie nie"]


@app.route("/zal5", methods=["GET", "POST"])
@login_required
def zal5():
    if request.method == "POST":
        return _save_zal5(None)
    nr = request.args.get("nr", "")
    return render_template("zal5.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, questions=SURVEY_QUESTIONS, options=SURVEY_OPTIONS)


@app.route("/zal5/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal5_edit(nr_albumu):
    if request.method == "POST":
        return _save_zal5(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal5")
    return render_template("zal5.html", data=existing, edit_nr=nr_albumu,
                           questions=SURVEY_QUESTIONS, options=SURVEY_OPTIONS)


@app.route("/zal5/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal5_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal5")
    flash("Załącznik 5 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal5(edit_nr):
    f = request.form
    nr_albumu = f.get("nr_albumu", "").strip()
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal5.html", data=f, edit_nr=edit_nr,
                               questions=SURVEY_QUESTIONS, options=SURVEY_OPTIONS)
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
# ZAŁ. 6 – Dziennik praktyki zawodowej
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal6", methods=["GET", "POST"])
@login_required
def zal6():
    effects = get_effects()
    if request.method == "POST":
        return _save_zal6(None, effects)
    nr = request.args.get("nr", "")
    return render_template("zal6.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, effects=effects, specialties=SPECIALTIES)


@app.route("/zal6/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal6_edit(nr_albumu):
    effects = get_effects()
    if request.method == "POST":
        return _save_zal6(nr_albumu, effects)
    existing = load_data().get(nr_albumu, {}).get("zal6")
    return render_template("zal6.html", data=existing, edit_nr=nr_albumu,
                           effects=effects, specialties=SPECIALTIES)


@app.route("/zal6/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal6_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal6")
    flash("Załącznik 6 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal6(edit_nr, effects):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template("zal6.html", data=f, edit_nr=edit_nr, effects=effects, specialties=SPECIALTIES)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template("zal6.html", data=f, edit_nr=edit_nr, effects=effects, specialties=SPECIALTIES)
    dni         = f.getlist("dzien[]")
    daty        = f.getlist("data[]")
    opisy       = f.getlist("opis[]")
    efekty_list = f.getlist("efekty[]")
    podpisy     = f.getlist("podpis[]")
    dziennik = [
        {"dzien": d, "data": dt, "opis": op, "efekty": ef, "podpis": p}
        for d, dt, op, ef, p in zip(dni, daty, opisy, efekty_list, podpisy)
    ]
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
# ZAŁ. 7 – Sprawozdanie z praktyki zawodowej
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal7", methods=["GET", "POST"])
@login_required
def zal7():
    if request.method == "POST":
        return _save_zal7(None)
    nr = request.args.get("nr", "")
    return render_template("zal7.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, specialties=SPECIALTIES, sn=False)


@app.route("/zal7/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal7_edit(nr_albumu):
    if request.method == "POST":
        return _save_zal7(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal7")
    return render_template("zal7.html", data=existing, edit_nr=nr_albumu, specialties=SPECIALTIES, sn=False)


@app.route("/zal7/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal7_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal7")
    flash("Załącznik 7 został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


def _save_zal7(edit_nr, sn=False):
    f = request.form
    imie_nazwisko = f.get("imie_nazwisko", "").strip()
    nr_albumu     = f.get("nr_albumu", "").strip()
    key = "zal7a" if sn else "zal7"
    tpl = "zal7.html"
    if not is_valid_full_name(imie_nazwisko):
        flash("Podaj imię i nazwisko.", "error")
        return render_template(tpl, data=f, edit_nr=edit_nr, specialties=SPECIALTIES, sn=sn)
    if not nr_albumu or not is_digits_only(nr_albumu):
        flash("Numer albumu może zawierać tylko cyfry.", "error")
        return render_template(tpl, data=f, edit_nr=edit_nr, specialties=SPECIALTIES, sn=sn)
    record = {
        "imie_nazwisko": imie_nazwisko,
        "nr_albumu": nr_albumu,
        "kierunek": "Informatyka",
        "specjalnosc": f.get("specjalnosc", "").strip(),
        "rodzaj_studiow": "niestacjonarne" if sn else f.get("rodzaj_studiow", "stacjonarne"),
        "rok_akademicki": f.get("rok_akademicki", "").strip(),
        "miejsce_praktyki": f.get("miejsce_praktyki", "").strip(),
        "charakterystyka": f.get("charakterystyka", "").strip(),
        "opis_prac": f.get("opis_prac", "").strip(),
        "wiedza_umiejetnosci": f.get("wiedza_umiejetnosci", "").strip(),
        "data": f.get("data", "").strip(),
        "podpis_studenta": f.get("podpis_studenta", "").strip(),
        "podpis_przelozonego": f.get("podpis_przelozonego", "").strip() if sn else "",
    }
    return _persist(nr_albumu, key, record, f"Załącznik {'7a' if sn else '7'}")


# ── Zał. 7a (SN – niestacjonarne) ─────────────────────────────────────────────

@app.route("/zal7a", methods=["GET", "POST"])
@login_required
def zal7a():
    if request.method == "POST":
        return _save_zal7(None, sn=True)
    nr = request.args.get("nr", "")
    return render_template("zal7.html", data={"nr_albumu": nr} if nr else None,
                           edit_nr=None, specialties=SPECIALTIES, sn=True)


@app.route("/zal7a/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal7a_edit(nr_albumu):
    if request.method == "POST":
        return _save_zal7(nr_albumu, sn=True)
    existing = load_data().get(nr_albumu, {}).get("zal7a")
    return render_template("zal7.html", data=existing, edit_nr=nr_albumu, specialties=SPECIALTIES, sn=True)


@app.route("/zal7a/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal7a_delete(nr_albumu):
    has_other = _delete_attachment(nr_albumu, "zal7a")
    flash("Załącznik 7a został usunięty.", "success")
    return redirect(url_for("student_detail", nr_albumu=nr_albumu) if has_other else url_for("index"))


# ═══════════════════════════════════════════════════════════════════════════════
# ZAŁ. 8 – Protokół zaliczenia praktyki zawodowej
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal8", methods=["GET", "POST"])
@login_required
def zal8():
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
# ZAŁ. 9 – Oświadczenie instytucji
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/zal9", methods=["GET", "POST"])
@login_required
def zal9():
    if request.method == "POST":
        return _save_zal9(None)
    nr = request.args.get("nr", "")
    return render_template("zal9.html", data={"nr_albumu": nr} if nr else None, edit_nr=None)


@app.route("/zal9/<nr_albumu>/edytuj", methods=["GET", "POST"])
@login_required
def zal9_edit(nr_albumu):
    if request.method == "POST":
        return _save_zal9(nr_albumu)
    existing = load_data().get(nr_albumu, {}).get("zal9")
    return render_template("zal9.html", data=existing, edit_nr=nr_albumu)


@app.route("/zal9/<nr_albumu>/usun", methods=["POST"])
@login_required
def zal9_delete(nr_albumu):
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


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true",
    )
