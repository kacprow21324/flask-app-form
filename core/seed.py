"""
Uruchom raz (lub po resecie), żeby wypełnić bazę użytkownikami testowymi i efektami:
  python -m core.seed

Istniejący użytkownicy mają zaktualizowane imiona i nazwiska.
"""
import json, os
from werkzeug.security import generate_password_hash
from app import app
from core.models import (
    db, User, LearningEffect,
    Specialty, Attachment, RoleFormAccess, StudentWorkflowStep,
    SurveyQuestion, SurveyOption, FormField, AppConfig,
    DocumentWorkflow, DocumentLog,
)
from core import store

# Katalog główny projektu = poziom wyżej niż pakiet core/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE  = os.path.join(BASE_DIR, "data", "studenci.json")


USERS = [
    {
        "email": "student@student.ans-elblag.pl",
        "first_name": "Aleksandra",
        "last_name": "Kowalska",
        "role": "student",
        "album_number": "21001",
        "gender": "K",
        "is_active": 1,
        "speciality": "Administracja systemów i sieci komputerowych (ASiSK)",
        "study_mode": "stacjonarne",
        "semester": "6",
        "study_year": "3",
    },
    {
        "email": "opiekun@ans-elblag.pl",
        "first_name": "Irena",
        "last_name": "Malinowska",
        "role": "uopz",
        "album_number": None,
        "is_active": 1,
    },
    {
        "email": "zopz@firma.pl",
        "first_name": "Zbigniew",
        "last_name": "Ostrowski",
        "role": "zopz",
        "album_number": None,
        "is_active": 1,
    },
    {
        "email": "dziekanat@ans-elblag.pl",
        "first_name": "Dorota",
        "last_name": "Kamińska",
        "role": "dziekanat",
        "album_number": None,
        "is_active": 1,
    },
    {
        "email": "admin@ans-elblag.pl",
        "first_name": "Adam",
        "last_name": "Wiśniewski",
        "role": "admin",
        "album_number": None,
        "is_active": 1,
    },
    {
        "email": "student2@student.ans-elblag.pl",
        "first_name": "Marek",
        "last_name": "Nowak",
        "role": "student",
        "album_number": "21002",
        "gender": "M",
        "is_active": 1,
        "speciality": "Projektowanie baz danych i oprogramowanie użytkowe (PBDiOU)",
        "study_mode": "niestacjonarne",
        "semester": "6",
        "study_year": "3",
    },
    {
        "email": "student3@student.ans-elblag.pl",
        "first_name": "Katarzyna",
        "last_name": "Wróbel",
        "role": "student",
        "album_number": "21003",
        "gender": "K",
        "is_active": 1,
        "speciality": "Modelowanie 3D w zastosowaniach medycznych, prototypowaniu i mediach interaktywnych (M3D)",
        "study_mode": "stacjonarne",
        "semester": "6",
        "study_year": "3",
    },
    {
        "email": "student4@student.ans-elblag.pl",
        "first_name": "Michał",
        "last_name": "Zając",
        "role": "student",
        "album_number": "21004",
        "gender": "M",
        "is_active": 1,
        "speciality": "Projektowanie baz danych i oprogramowanie użytkowe (PBDiOU)",
        "study_mode": "stacjonarne",
        "semester": "6",
        "study_year": "3",
        "_password_env": "SEED_STUDENT4_PASSWORD",
    },
]

EFFECTS = [
    (1, "Ma wiedzę na temat sposobu realizacji zadań inżynierskich dotyczących informatyki z zachowaniem standardów i norm technicznych"),
    (2, "Zna technologie, narzędzia, metody, techniki oraz sprzęt stosowane w informatyce"),
    (3, "Zna ekonomiczne, prawne skutki własnych działań podejmowanych w ramach praktyki oraz ograniczenia wynikające z prawa autorskiego i kodeksu pracy"),
    (4, "Zna zasady bezpieczeństwa pracy i ergonomii w zawodzie informatyka"),
    (5, "Pozyskuje informacje odnośnie technologii, metod, technik, sprzętu wymaganego do realizacji powierzonego zadania, posługując się rozmaitymi źródłami literaturowymi i zasobami publikowanymi w języku polskim jak i angielskim"),
    (6, "W oparciu o kontakty ze środowiskiem inżynierskim zakładu, potrafi podnieść swoje kompetencje, wiedzę i umiejętności, co najmniej z dwóch zakresów: zadania dotyczące sprzętu i oprogramowania: np.: programowania, administrowanie siecią komputerową, konserwacja sprzętu i oprogramowania, bieżące usuwanie usterek, administrowanie zasobami informatycznymi, zakładu pracy / instytucji, (e)-usługami."),
    (7, "Opracowuje dokumentację dotyczącą realizacji podejmowanych zadań w ramach praktyki, a także referuje ustnie prezentowane w niej zagadnienia"),
    (8, "Potrafi zidentyfikować problem informatyczny występujący w zakładzie pracy / instytucji, opisać go, przedstawić koncepcję rozwiązania i ją zrealizować."),
    (9, "Potrafi rozwiązać rzeczywiste zadanie inżynierskie z zakresu działalności informatycznej zakładu pracy/instytucji stosując normy i standardy stosowane w informatyce oraz biorąc pod uwagę aspekty środowiskowe i etyczne."),
    (10, "Pracuje w zespole zajmującym się zawodowo branżą IT"),
    (11, "Przestrzega zasad etyki zawodowej i zgodnie z tymi zasadami korzysta z wiedzy i pomocy doświadczonych kolegów"),
    (12, "Kontaktując się z osobami spoza branży potrafi zarówno pozyskać od nich niezbędne informacje do realizacji planowanego zadania, jak i przekazać im w sposób zrozumiały informacje i opinie z zakresu informatyki"),
    (13, "Dostrzega w praktyce tempo deaktualizacji wiedzy informatycznej oraz skutki działalności informatyków w szczególności ekonomiczne i społeczne"),
]

SPECIALTIES_DATA = [
    (0, "Administracja systemów i sieci komputerowych (ASiSK)"),
    (1, "Projektowanie baz danych i oprogramowanie użytkowe (PBDiOU)"),
    (2, "Modelowanie 3D w zastosowaniach medycznych, prototypowaniu i mediach interaktywnych (M3D)"),
]

# key, nr, title, reviewer_role, reviewer_label, sort_order
ATTACHMENTS_DATA = [
    ("zal1",  "1",  "Porozumienie z zakładem pracy",                     "uopz",  "Opiekun Uczelniany (UOPZ)", 0),
    ("zal2",  "2",  "Program praktyki zawodowej",                         None,    None,                        1),
    ("zal2a", "2a", "Program i harmonogram praktyki",                     "zopz",  "Opiekun Zakładowy (ZOPZ)", 2),
    ("zal3",  "3",  "Karta praktyki zawodowej",                           "uopz",  "Opiekun Uczelniany (UOPZ)", 3),
    ("zal4",  "4",  "Potwierdzenie efektów uczenia się",                  None,    None,                        4),
    ("zal4a", "4a", "Merytoryczna ocena wniosku studenta",                None,    None,                        5),
    ("zal4b", "4b", "Wniosek o zaliczenie efektów uczenia się",          "uopz",  "Opiekun Uczelniany (UOPZ)", 6),
    ("zal5",  "5",  "Kwestionariusz ankiety",                             None,    None,                        7),
    ("zal6",  "6",  "Dziennik praktyki zawodowej",                        "zopz",  "Opiekun Zakładowy (ZOPZ)", 8),
    ("zal7",  "7",  "Sprawozdanie z praktyki zawodowej",                  None,    None,                        9),
    ("zal7a", "7a", "Sprawozdanie z praktyki (niestacjonarne)",           "zopz",  "Opiekun Zakładowy (ZOPZ)", 10),
    ("zal8",  "8",  "Protokół zaliczenia praktyki",                       None,    None,                        11),
]

# role -> [form_keys]
ROLE_ACCESS_DATA = {
    'student':   ['zal1', 'zal2a', 'zal4b', 'zal5', 'zal6', 'zal7', 'zal7a'],
    # uopz ma dostęp do zal4b żeby wypełnić sekcję E (Opinia Komisji)
    'uopz':      ['zal2', 'zal4a', 'zal4b'],
    'zopz':      ['zal3', 'zal4'],
    'dziekanat': ['zal8'],
    'admin':     ['zal1', 'zal2', 'zal2a', 'zal3', 'zal4', 'zal4a', 'zal4b',
                  'zal5', 'zal6', 'zal7', 'zal7a', 'zal8', 'zal9'],
}

# step, key, nr, title, when_label, hint
# Kolejność uzupełniania przez studenta wg faz praktyki (FAZA 0 → 2).
STUDENT_WORKFLOW_DATA = [
    (1, "zal1",  "1",  "Porozumienie z zakładem pracy",
     "Faza 1 — przed praktyką",
     "Złóż jako pierwsze – uzgodnij warunki z zakładem pracy. Po złożeniu trafi do zatwierdzenia przez Opiekuna Uczelnianego."),
    (2, "zal2a", "2a", "Program i harmonogram praktyki",
     "Faza 1 — przed praktyką",
     "Ustal indywidualny plan zadań i harmonogram. Wymaga zatwierdzenia przez Opiekuna Zakładowego."),
    (3, "zal4b", "4b", "Wniosek o zaliczenie efektów",
     "Faza 1 — opcjonalnie",
     "Tylko jeśli ubiegasz się o zaliczenie efektów na podstawie pracy zawodowej lub stażu. Opiekun Uczelniany odpowie Zał. 4a."),
    (4, "zal6",  "6",  "Dziennik praktyki zawodowej",
     "Faza 2 — w trakcie",
     "Wypełniaj każdego dnia. Po zakończeniu wyślij do zatwierdzenia przez Opiekuna Zakładowego."),
    (5, "zal7",  "7",  "Sprawozdanie z praktyki",
     "Faza 3 — po praktyce",
     "Napisz po zakończeniu – opisz charakter zakładu, wykonane prace i nabyte umiejętności."),
    (6, "zal5",  "5",  "Kwestionariusz ankiety",
     "Faza 3 — na końcu",
     "Anonimowa ankieta oceniająca przebieg praktyki. Wypełnij jako ostatni dokument."),
]

SURVEY_QUESTIONS_DATA = [
    (1,  "Poznałam/poznałem zasady funkcjonowania instytucji, w której odbywałam/odbywałem praktyki zawodowe."),
    (2,  "Poznałam/poznałem strukturę oraz regulamin organizacyjny instytucji, w której odbywałam/odbywałem praktyki zawodowe."),
    (3,  "Praktyki zawodowe umożliwiły mi pełną realizację ramowego programu praktyk zawodowych przewidzianego w ramach mojego kierunku studiów."),
    (4,  "Podczas praktyk zawodowych zwracano uwagę na przestrzeganie zasad etyki i tajemnicy zawodowej."),
    (5,  "Podczas praktyk miałam/miałem możliwość praktycznego zastosowania wiedzy teoretycznej zdobytej na zajęciach."),
    (6,  "Praktyki zawodowe przyczyniły się do pogłębienia mojej wiedzy i umiejętności zdobytych w trakcie studiów."),
    (7,  "Mogłem liczyć na wsparcie merytoryczne Opiekuna zakładowego praktyk."),
    (8,  "Mogłem liczyć na wsparcie merytoryczne Opiekuna uczelnianego praktyk."),
    (9,  "Opiekun zakładowy odpowiedzialny za praktyki zawodowe w miejscu ich odbywania potrafił prawidłowo zorganizować ich przebieg."),
    (10, "Podczas praktyk zawodowych miałam/miałem możliwość pozyskiwania materiałów niezbędnych do przygotowania mojej pracy dyplomowej."),
    (11, "Praktyki zawodowe rozwinęły moje umiejętności skutecznego komunikowania się w sytuacjach zawodowych i pracy w zespole."),
    (12, "Praktyki zawodowe nauczyły mnie samodzielności i odpowiedzialności podczas wykonywania pracy."),
    (13, "Liczba godzin realizowana w ramach praktyk zawodowych jest wystarczająca."),
    (14, "Czy po zakończeniu praktyki zawodowej chciałaby/chciałby Pani/Pan współpracować z instytucją, w której Pani/Pan zrealizowała/zrealizował praktykę?"),
]

SURVEY_OPTIONS_DATA = [
    (0, "zdecydowanie tak"),
    (1, "raczej tak"),
    (2, "trudno powiedzieć"),
    (3, "raczej nie"),
    (4, "zdecydowanie nie"),
]

# form_key -> [field_names]
FORM_FIELDS_DATA = {
    'zal1':  ["Imię i nazwisko", "Nr albumu", "Nr porozumienia", "Miejscowość", "Data",
              "Specjalność", "Rodzaj studiów", "Nazwa zakładu pracy", "Adres zakładu", "NIP zakładu",
              "Reprezentant – nazwisko", "Reprezentant – stanowisko", "E-mail zakładu pracy",
              "Uczelniany opiekun",
              "Data rozpoczęcia", "Data zakończenia", "Liczba godzin",
              "Podpis uczelnianego opiekuna", "Podpis dziekanatu"],
    'zal2':  ["Nr albumu", "Zakład pracy", "Data rozpoczęcia", "Data zakończenia",
              "Data uzgodnienia", "Podpis zakładowy", "Podpis uczelniany"],
    'zal2a': ["Imię i nazwisko", "Nr albumu", "Specjalność", "Miejsce praktyki",
              "Data rozpoczęcia", "Data zakończenia", "Efekty – działy prac",
              "Harmonogram – działy", "Harmonogram – liczba dni", "Data uzgodnienia",
              "Podpis uczelniany", "Podpis zakładowy", "Podpis studenta"],
    'zal3':  ["Imię i nazwisko", "Nr albumu", "Nr porozumienia", "Data porozumienia",
              "Zakład pracy", "Specjalność", "Rodzaj studiów", "Uczelniany opiekun",
              "Data rozpoczęcia", "Data zakończenia", "Opiekun zakładowy – nazwisko",
              "Opiekun zakładowy – funkcja", "Data zgłoszenia", "Data szkolenia BHP",
              "Zaświadczenie – uwagi", "Ocena zakładowa", "Opis oceny zakładowej",
              "Ocena uczelniana", "Opis oceny uczelnianej", "Ocena sprawozdania"],
    'zal4':  ["Imię i nazwisko", "Nr albumu", "Specjalność", "Wymiar godzin",
              "Potwierdzenie opiekuna", "Opinia opiekuna", "Status efektów uczenia się"],
    'zal4a': ["Imię i nazwisko", "Nr albumu", "Data złożenia", "Ocena zasadności efektów",
              "Uzasadnienia efektów", "Rekomendacja", "Uwagi", "Data oceny", "Podpis UOPZ"],
    'zal4b': ["Imię i nazwisko", "Nr albumu", "Specjalność", "Pracodawca", "Adres pracodawcy",
              "Stanowisko", "Okres zatrudnienia – od", "Okres zatrudnienia – do",
              "Uzasadnienia efektów", "Dowody na efekty", "Wykaz dokumentów",
              "Data", "Podpis studenta"],
    'zal5':  ["Nr albumu", "Rok akademicki", "Forma studiów", "Semestr", "Liczba godzin",
              "Odpowiedzi na pytania ankiety", "Uwagi dodatkowe"],
    'zal6':  ["Imię i nazwisko", "Nr albumu", "Specjalność", "Rodzaj studiów",
              "Rok akademicki", "Miejsce praktyki", "Data rozpoczęcia", "Data zakończenia",
              "Wykaz załączników", "Wpisy dziennika – opis", "Wpisy dziennika – efekty",
              "Wpisy dziennika – podpis"],
    'zal7':  ["Imię i nazwisko", "Nr albumu", "Specjalność", "Rodzaj studiów",
              "Rok akademicki", "Miejsce praktyki", "Charakterystyka zakładu",
              "Opis wykonanych prac", "Wiedza i umiejętności", "Data", "Podpis studenta"],
    'zal7a': ["Imię i nazwisko", "Nr albumu", "Specjalność", "Rok akademicki",
              "Miejsce praktyki", "Charakterystyka zakładu", "Opis wykonanych prac",
              "Wiedza i umiejętności", "Data", "Podpis studenta", "Podpis przełożonego"],
    'zal8':  ["Imię i nazwisko", "Nr albumu", "Miejsca praktyki", "Ocena S (sprawozdanie)",
              "Data oceny S", "Podpis S", "Ocena U (uczelniana)", "Ocena Z (zakładowa)",
              "Skład komisji", "Data zaliczenia", "Przewodniczący",
              "Członek komisji 2", "Członek komisji 3",
              "Mini-zadania – treść", "Mini-zadania – ocena",
              "Ocena E (egzamin)", "Ocena K (końcowa)"],
    'zal9':  ["Imię i nazwisko", "Nr albumu", "Miejscowość", "Data", "Nazwa instytucji",
              "Termin – od", "Termin – do", "Opiekun – imię i nazwisko",
              "Opiekun – stanowisko", "Opiekun – telefon", "Opiekun – e-mail",
              "Upoważniony – imię i nazwisko", "Upoważniony – stanowisko", "Podpis"],
}


def seed_app_config():
    defaults = [
        ('semester_summer_start_month', '3',  'Miesiąc początku semestru letniego'),
        ('semester_winter_start_month', '10', 'Miesiąc początku semestru zimowego'),
        ('data_retention_years', '10', 'Okres retencji archiwum studenta w latach'),
    ]
    added = 0
    for key, value, label in defaults:
        if not AppConfig.query.filter_by(key=key).first():
            db.session.add(AppConfig(key=key, value=value, label=label))
            added += 1
    db.session.commit()
    if added:
        print(f"AppConfig: dodano {added} wpisów.")


def seed_users():
    added = updated = 0
    for data in USERS:
        existing = User.query.filter_by(email=data["email"]).first()
        if existing:
            existing.first_name = data["first_name"]
            existing.last_name  = data["last_name"]
            if data.get("speciality"):
                existing.speciality = data["speciality"]
            if data.get("gender"):
                existing.gender = data["gender"]
            if data.get("study_mode"):
                existing.study_mode = data["study_mode"]
            if data.get("semester"):
                existing.semester = data["semester"]
            if data.get("study_year"):
                existing.study_year = data["study_year"]
            db.session.add(existing)
            updated += 1
            print(f"  zaktualizowano: {data['email']}  ({data['first_name']} {data['last_name']})")
        else:
            env_name = data.get("_password_env") or f"SEED_{data['role'].upper()}_PASSWORD"
            password = os.environ.get(env_name, "")
            if len(password) < 12:
                raise RuntimeError(
                    f"Ustaw {env_name} (minimum 12 znaków), aby utworzyć konto "
                    f"{data['email']}."
                )
            user = User(
                email=data["email"],
                password_hash=generate_password_hash(password),
                first_name=data["first_name"],
                last_name=data["last_name"],
                role=data["role"],
                album_number=data.get("album_number"),
                speciality=data.get("speciality"),
                study_mode=data.get("study_mode", "stacjonarne"),
                gender=data.get("gender"),
                semester=data.get("semester"),
                study_year=data.get("study_year"),
                is_active=data["is_active"],
                email_verified=1,
            )
            db.session.add(user)
            added += 1
            print(f"  dodano: {data['email']}")
    db.session.commit()
    print(f"Użytkownicy: dodano {added}, zaktualizowano {updated}.")


def seed_effects():
    added = 0
    for nr, opis in EFFECTS:
        if not LearningEffect.query.filter_by(nr=nr).first():
            db.session.add(LearningEffect(nr=nr, opis=opis))
            added += 1
    db.session.commit()
    if added:
        print(f"Efekty: dodano {added}.")


def seed_specialties():
    added = 0
    for sort_order, name in SPECIALTIES_DATA:
        if not Specialty.query.filter_by(name=name).first():
            db.session.add(Specialty(name=name, sort_order=sort_order))
            added += 1
    db.session.commit()
    if added:
        print(f"Specjalności: dodano {added}.")


def seed_attachments():
    added = 0
    for key, nr, title, reviewer_role, reviewer_label, sort_order in ATTACHMENTS_DATA:
        if not Attachment.query.filter_by(key=key).first():
            db.session.add(Attachment(
                key=key, nr=nr, title=title,
                reviewer_role=reviewer_role,
                reviewer_label=reviewer_label,
                sort_order=sort_order,
            ))
            added += 1
    db.session.commit()
    if added:
        print(f"Załączniki: dodano {added}.")


def seed_role_access():
    added = 0
    for role, keys in ROLE_ACCESS_DATA.items():
        for form_key in keys:
            if not RoleFormAccess.query.filter_by(role=role, form_key=form_key).first():
                db.session.add(RoleFormAccess(role=role, form_key=form_key))
                added += 1
    db.session.commit()
    if added:
        print(f"Dostęp ról: dodano {added} wpisów.")


def migrate_role_access():
    """Aktualizuje role_form_access bez resetowania danych.
    Uruchom: docker compose exec flask python -c
    "from core.seed import migrate_role_access; migrate_role_access()"
    """
    from app import app
    with app.app_context():
        seed_role_access()
        print("Migracja role_form_access zakończona.")


def seed_student_workflow():
    added = updated = 0
    for step, key, nr, title, when_label, hint in STUDENT_WORKFLOW_DATA:
        row = StudentWorkflowStep.query.filter_by(step=step).first()
        if row:
            # aktualizuj etykiety/kolejność przy ponownym seedzie
            row.key, row.nr, row.title = key, nr, title
            row.when_label, row.hint = when_label, hint
            updated += 1
        else:
            db.session.add(StudentWorkflowStep(
                step=step, key=key, nr=nr, title=title,
                when_label=when_label, hint=hint,
            ))
            added += 1
    db.session.commit()
    if updated:
        print(f"Kroki workflow studenta: zaktualizowano {updated}.")
    if added:
        print(f"Kroki workflow studenta: dodano {added}.")


def seed_survey():
    added_q = added_o = 0
    for nr, text in SURVEY_QUESTIONS_DATA:
        if not SurveyQuestion.query.filter_by(nr=nr).first():
            db.session.add(SurveyQuestion(nr=nr, text=text))
            added_q += 1
    for sort_order, label in SURVEY_OPTIONS_DATA:
        if not SurveyOption.query.filter_by(label=label).first():
            db.session.add(SurveyOption(sort_order=sort_order, label=label))
            added_o += 1
    db.session.commit()
    if added_q or added_o:
        print(f"Ankieta: dodano {added_q} pytań, {added_o} opcji.")


def seed_form_fields():
    added = updated = removed = 0
    for form_key, fields in FORM_FIELDS_DATA.items():
        existing_rows = FormField.query.filter_by(form_key=form_key).all()
        existing = {row.field_name: row for row in existing_rows}
        for row in existing_rows:
            if row.field_name not in fields:
                db.session.delete(row)
                removed += 1
        for idx, field_name in enumerate(fields):
            row = existing.get(field_name)
            if row is None:
                db.session.add(FormField(form_key=form_key, sort_order=idx, field_name=field_name))
                added += 1
            elif row.sort_order != idx:
                row.sort_order = idx
                updated += 1
    db.session.commit()
    if added or updated or removed:
        print(
            f"Pola formularzy: dodano {added}, zaktualizowano {updated}, "
            f"usunięto {removed}."
        )


def seed_forms():
    """Wypełnia studenci.json danymi testowymi dla konta studenckiego (album 21001)."""
    from datetime import date as _d
    from core.models import LearningEffect as LE

    effects = LE.query.order_by(LE.nr).all()
    uopz = User.query.filter_by(role='uopz').first()
    zopz = User.query.filter_by(role='zopz').first()
    dziekanat = User.query.filter_by(role='dziekanat').first()
    student = User.query.filter_by(album_number='21001').first()

    if not student:
        print("Brak konta studenckiego – pomijam seed formularzy.")
        return

    today = _d.today()
    year = today.year
    rok_ak = f"{year-1}/{year}" if today.month < 10 else f"{year}/{year+1}"
    nr = "21001"
    student_name = student.full_name
    uopz_name = f"dr {uopz.full_name}" if uopz else "dr Irena Malinowska"
    zopz_name = zopz.full_name if zopz else "Zbigniew Ostrowski"
    dziekanat_name = dziekanat.full_name if dziekanat else "Dorota Kamińska"
    spec = "Administracja systemów i sieci komputerowych (ASiSK)"
    company = "Techno Systems Sp. z o.o."
    company_full = f"{company}, ul. Portowa 12, 80-001 Gdańsk"
    start, end = f"{year}-04-01", f"{year}-05-31"

    efekty_all   = [{"nr": e.nr, "status": "uzyskał/a"} for e in effects]
    efekty_plan  = [{"nr": e.nr, "dzial_prace": "Dział Infrastruktury IT"} for e in effects]
    harmonogram  = [
        {"lp": 1, "dzial": "Infrastruktura IT – konfiguracja sieci LAN/WAN", "dni": "10"},
        {"lp": 2, "dzial": "Administracja serwerami Linux/Windows Server", "dni": "12"},
        {"lp": 3, "dzial": "Helpdesk – wsparcie techniczne użytkowników", "dni": "8"},
        {"lp": 4, "dzial": "Bezpieczeństwo IT – monitoring i audyt", "dni": "10"},
    ]
    ocena_efektow = [
        {"nr": e.nr, "zasadny": "tak",
         "uzasadnienie": f"Efekt nr {e.nr} zrealizowany w pełni w trakcie praktyki."}
        for e in effects
    ]
    efekty_wniosek = [
        {"nr": e.nr,
         "uzasadnienie": "Realizowany w ramach pracy jako asystent administratora sieci.",
         "dowody": "Zaświadczenie od pracodawcy, opis stanowiska"}
        for e in effects
    ]
    _wpisy = [
        ("Zapoznanie z infrastrukturą sieciową firmy. Przegląd dokumentacji topologii LAN/WAN oraz schemat adresacji IP.", "1,2,4"),
        ("Konfiguracja przełączników Cisco Catalyst 2960: tworzenie VLAN-ów dla działów, konfiguracja trunk portów.", "1,2,5"),
        ("Konfiguracja routera brzegowego, ustawienie NAT i ACL. Dokumentacja zmian w rejestrze konfiguracji.", "1,2,7"),
        ("Administracja Active Directory: zakładanie kont użytkowników, przypisywanie do grup, resetowanie haseł.", "2,6,10"),
        ("Wdrożenie polityk GPO: blokada USB, wymuszenie hasła, mapowanie dysków sieciowych dla działów.", "2,3,6"),
        ("Instalacja i konfiguracja serwera WSUS. Zaplanowanie harmonogramu aktualizacji dla stacji roboczych.", "2,5,9"),
        ("Konfiguracja systemu monitoringu Zabbix: dodawanie hostów, ustawienie progów alertów, testy powiadomień.", "2,5,8"),
        ("Helpdesk: diagnoza awarii stacji roboczej (uszkodzony dysk), wymiana, reinstalacja systemu i migracja danych.", "6,8,11"),
        ("Analiza logów systemowych serwera plików. Identyfikacja i usunięcie konta z podejrzaną aktywnością.", "3,7,8"),
        ("Tworzenie dokumentacji technicznej: schematy sieci, procedury odtwarzania backupu, opis konfiguracji VPN.", "5,7,12"),
    ]
    dziennik = [
        {"dzien": str(i+1),
         "data": f"{year}-04-{str(i+1).zfill(2)}",
         "opis": _wpisy[i][0],
         "efekty": _wpisy[i][1],
         "podpis": zopz_name}
        for i in range(10)
    ]
    pytania = [
        {"nr": i+1, "odpowiedz": "zdecydowanie tak" if i < 11 else "raczej tak"}
        for i in range(14)
    ]
    miejsca = [{"nazwa": company_full, "okres": f"{start} – {end}", "dni": "40"}]
    mini_zadania = [
        {"tresc": "Opisz zastosowane technologie sieciowe podczas praktyki.", "ocena": "5"},
        {"tresc": "Omów zarządzanie serwerami Linux i Windows Server.", "ocena": "5"},
        {"tresc": "Przedstaw wyniki monitoringu infrastruktury IT.", "ocena": "5"},
    ]

    forms = {
        "zal1": {
            "_status": "approved",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "nr_porozumienia": f"ZAL-1-{nr}", "miejscowosc": "Elbląg",
            "data": today.isoformat(), "kierunek": "Informatyka",
            "specjalnosc": spec, "rodzaj_studiow": "stacjonarne",
            "nazwa_zakladu": company, "adres_zakladu": "ul. Portowa 12, 80-001 Gdańsk",
            "nip_zakladu": "589-212-34-56",
            "reprezentant_nazwisko": "Piotr Zieliński",
            "reprezentant_stanowisko": "Prezes Zarządu",
            "email_zakladu": "biuro@technosystems.pl",
            "uczelniany_opiekun": uopz_name,
            "data_start": start, "data_end": end, "liczba_godzin": "960",
            "podpis_uczelniany": f"{uopz_name}, {today.strftime('%d.%m.%Y')}",
            "podpis_dziekanatu": f"{dziekanat_name}, {today.strftime('%d.%m.%Y')}",
        },
        "zal2": {
            "_status": "approved",
            "nr_albumu": nr, "zaklad_pracy": company_full,
            "data_start": start, "data_end": end,
            "data_uzgodnienia": f"{year}-03-15",
            "podpis_zakladowy": f"Piotr Zieliński, {year}-03-15",
            "podpis_uczelniany": f"{uopz_name}, {year}-03-15",
        },
        "zal2a": {
            "_status": "approved",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "miejsce_praktyki": company, "data_start": start, "data_end": end,
            "efekty_plan": efekty_plan, "harmonogram": harmonogram,
            "data_uzgodnienia": f"{year}-03-15",
            "podpis_uczelniany": uopz_name,
            "podpis_zakladowy": zopz_name,
            "podpis_studenta": student_name,
        },
        "zal3": {
            "_status": "pending",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "nr_porozumienia": f"ZAL-1-{nr}",
            "data_porozumienia": f"{year}-03-15",
            "zaklad_pracy": company,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne",
            "uczelniany_opiekun": uopz_name,
            "data_start": start, "data_end": end,
            "zakladowy_opiekun_nazwisko": zopz_name,
            "zakladowy_opiekun_funkcja": "Kierownik Działu IT",
            "potwierdzenie_zgloszenia": f"{year}-04-01",
            "potwierdzenie_bhp": f"{year}-04-01",
            "zaswiadczenie_zaklad": company_full,
            "zaswiadczenie_okres_od": start, "zaswiadczenie_okres_do": end,
            "zaswiadczenie_uwagi": "Studentka zrealizowała wszystkie zaplanowane zadania.",
            "zaswiadczenie_podpis": f"{zopz_name}, Gdańsk, {year}-06-01",
            "ocena_zakladowa_param": "5",
            "ocena_zakladowa_opis": "Studentka wykazała dużą inicjatywę i kompetencje techniczne.",
            "podpis_zakladowy": f"{zopz_name}, {year}-06-01",
            "ocena_uczelniana_param": "5",
            "ocena_uczelniana_opis": "Studentka aktywnie uczestniczyła w praktyce.",
            "podpis_uczelniany": f"{uopz_name}, {year}-06-05",
            "ocena_sprawozdania": "5",
            "podpis_sprawozdanie": f"{uopz_name}, {year}-06-10",
        },
        "zal4": {
            "_status": "approved",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "wymiar_godzin": "960",
            "potwierdzenie_opiekuna": zopz_name,
            "opinia_opiekuna": "Studentka wykazała wysokie zaangażowanie i kompetencje.",
            "efekty": efekty_all,
        },
        "zal4a": {
            "_status": "approved",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "data_zlozenia": f"{year}-03-10",
            "ocena_efektow": ocena_efektow,
            "rekomendacja": "Zaliczam efekty uczenia się wskazane we wniosku studenta.",
            "uwagi": "Studentka przedłożyła kompletną dokumentację.",
            "data_oceny": f"{year}-03-12",
            "podpis_uopz": uopz_name,
        },
        "zal4b": {
            "_status": "approved",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "pracodawca": company,
            "adres_pracodawcy": "ul. Portowa 12, 80-001 Gdańsk",
            "stanowisko": "Asystent administratora sieci",
            "okres_od": f"{year-1}-10-01", "okres_do": f"{year}-03-31",
            "efekty_wniosek": efekty_wniosek,
            "wykaz_dokumentow": "Zaświadczenie od pracodawcy, umowa o pracę",
            "data": f"{year}-03-10",
            "podpis_studenta": student_name,
        },
        "zal5": {
            "_status": "draft",
            "nr_albumu": nr, "rok_akademicki": rok_ak,
            "kierunek": "Informatyka", "forma_studiow": "stacjonarne",
            "semestr": "6", "liczba_godzin": "960",
            "pytania": pytania,
            "uwagi": "Praktyka w pełni odpowiadała moim oczekiwaniom zawodowym.",
        },
        "zal6": {
            "_status": "pending",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne", "rok_akademicki": rok_ak,
            "miejsce_praktyki": company,
            "data_start": start, "data_end": end,
            "wykaz_zalacznikow": "Zaświadczenie od pracodawcy",
            "dziennik": dziennik,
        },
        "zal7": {
            "_status": "rejected",
            "_rejection_comment": "Sprawozdanie wymaga rozbudowania sekcji opisu wykonanych prac.",
            "_rejection_by": uopz_name,
            "_field_comments": [
                {"field": "Opis wykonanych prac", "note": "Zbyt ogólny – proszę opisać konkretne zadania z każdego tygodnia."},
                {"field": "Charakterystyka zakładu", "note": "Proszę rozbudować o informacje o stosowanych technologiach."},
            ],
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne", "rok_akademicki": rok_ak,
            "miejsce_praktyki": company,
            "charakterystyka": f"{company} jest firmą informatyczną z Gdańska.",
            "opis_prac": "Konfiguracja sieci LAN/WAN, administracja serwerami.",
            "wiedza_umiejetnosci": "Zastosowałam wiedzę z administracji sieciowej.",
            "data": f"{year}-06-01",
            "podpis_studenta": student_name,
            "podpis_przelozonego": "",
        },
        "zal7a": {
            "_status": "draft",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "niestacjonarne", "rok_akademicki": rok_ak,
            "miejsce_praktyki": company,
            "charakterystyka": f"{company} jest firmą informatyczną z Gdańska.",
            "opis_prac": "Konfiguracja sieci, administracja serwerami, dokumentacja techniczna.",
            "wiedza_umiejetnosci": "Praktyczne zastosowanie wiedzy z administracji sieciowej.",
            "data": f"{year}-06-01",
            "podpis_studenta": student_name,
            "podpis_przelozonego": zopz_name,
        },
        "zal8": {
            "_status": "draft",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "miejsca_praktyki": miejsca,
            "ocena_s": "5", "data_s": f"{year}-06-05", "podpis_s": uopz_name,
            "ocena_u": "5", "ocena_z": "5",
            "sklad_komisji": f"{uopz_name} (przewodnicząca), mgr Tomasz Witek, mgr Anna Kowalczyk",
            "data_zaliczenia": f"{year}-06-10",
            "przewodniczacy": uopz_name,
            "czlonek_2": "mgr Tomasz Witek",
            "czlonek_3": "mgr Anna Kowalczyk",
            "czlonek_4": "",
            "mini_zadania": mini_zadania,
            "ocena_e": "5", "ocena_k": "5",
        },
    }

    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_data = {}

    all_data.setdefault(nr, {})
    all_data[nr].update(forms)

    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print(f"Formularze: zaktualizowano dane testowe studenta nr albumu {nr}.")


def seed_extra_forms():
    """Wypełnia studenci.json danymi testowymi dla studentów 21002 i 21003."""
    from datetime import date as _d
    from core.models import LearningEffect as LE

    effects = LE.query.order_by(LE.nr).all()
    uopz = User.query.filter_by(role='uopz').first()
    zopz = User.query.filter_by(role='zopz').first()
    dziekanat = User.query.filter_by(role='dziekanat').first()

    un = uopz.full_name if uopz else "dr Irena Malinowska"
    zn = zopz.full_name if zopz else "Zbigniew Ostrowski"
    dn = dziekanat.full_name if dziekanat else "Dorota Kamińska"

    today = _d.today()
    year = today.year
    rok_ak = f"{year-1}/{year}" if today.month < 10 else f"{year}/{year+1}"

    students_extra = [
        {
            "nr": "21002",
            "name": "Marek Nowak",
            "spec": "Projektowanie baz danych i oprogramowanie użytkowe (PBDiOU)",
            "company": "DataSoft Sp. z o.o.",
            "company_full": "DataSoft Sp. z o.o., ul. Technologiczna 5, 10-062 Olsztyn",
            "repr": "Anna Kowalczyk",
            "repr_pos": "Dyrektor Techniczny",
            "zopz_phone": "+48 89 456 78 90",
            "zopz_email": "z.ostrowski@datasoft.pl",
            "start": f"{year}-03-01",
            "end": f"{year}-04-30",
            "status_zal1": "approved",
            "status_zal2a": "pending",
            "study_mode": "niestacjonarne",
            "company_email": "kontakt@datasoft.pl",
        },
        {
            "nr": "21003",
            "name": "Katarzyna Wróbel",
            "spec": "Modelowanie 3D w zastosowaniach medycznych, prototypowaniu i mediach interaktywnych (M3D)",
            "company": "MediScan Sp. z o.o.",
            "company_full": "MediScan Sp. z o.o., ul. Medyczna 22, 10-900 Olsztyn",
            "repr": "Tomasz Jabłoński",
            "repr_pos": "Kierownik Projektu",
            "zopz_phone": "+48 89 321 00 11",
            "zopz_email": "z.ostrowski@mediscan.pl",
            "start": f"{year}-05-01",
            "end": f"{year}-06-30",
            "status_zal1": "draft",
            "status_zal2a": "draft",
            "study_mode": "stacjonarne",
            "company_email": "biuro@mediscan.pl",
        },
    ]

    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_data = {}

    total_filled = 0
    for s in students_extra:
        nr = s["nr"]
        all_data.setdefault(nr, {})
        forms = {
            "zal1": {
                "_status": s["status_zal1"],
                "imie_nazwisko": s["name"], "nr_albumu": nr,
                "nr_porozumienia": f"ZAL-1-{nr}", "miejscowosc": "Elbląg",
                "data": today.isoformat(), "kierunek": "Informatyka",
                "specjalnosc": s["spec"], "rodzaj_studiow": s["study_mode"],
                "nazwa_zakladu": s["company"],
                "adres_zakladu": s["company_full"].split(", ", 1)[1] if ", " in s["company_full"] else "",
                "nip_zakladu": "",
                "reprezentant_nazwisko": s["repr"],
                "reprezentant_stanowisko": s["repr_pos"],
                "email_zakladu": s["company_email"],
                "uczelniany_opiekun": un,
                "data_start": s["start"], "data_end": s["end"], "liczba_godzin": "960",
                "podpis_uczelniany": un if s["status_zal1"] == "approved" else "",
                "podpis_dziekanatu": dn if s["status_zal1"] == "approved" else "",
            },
            "zal2a": {
                "_status": s["status_zal2a"],
                "imie_nazwisko": s["name"], "nr_albumu": nr,
                "kierunek": "Informatyka", "specjalnosc": s["spec"],
                "miejsce_praktyki": s["company"],
                "data_start": s["start"], "data_end": s["end"],
                "efekty_plan": [{"nr": e.nr, "dzial_prace": "Dział Rozwoju Oprogramowania"} for e in effects],
                "harmonogram": [
                    {"lp": 1, "dzial": "Zapoznanie z systemem i dokumentacją", "dni": "5"},
                    {"lp": 2, "dzial": "Realizacja zadań programistycznych", "dni": "15"},
                    {"lp": 3, "dzial": "Testowanie i wdrożenie", "dni": "10"},
                ],
                "data_uzgodnienia": f"{year}-02-25",
                "podpis_uczelniany": un,
                "podpis_zakladowy": zn,
                "podpis_studenta": s["name"],
            },
        }
        all_data[nr].update(forms)
        total_filled += len(forms)
        print(f"  Formularze: zaktualizowano dane studenta nr albumu {nr} ({s['name']}).")

    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    if total_filled:
        print(f"Dodatkowi studenci: łącznie wypełniono {total_filled} formularzy.")


def seed_workflow_from_json():
    """Backfill tabel obiegu (document_workflow/document_log) na podstawie studenci.json.

    Wykonuje się tylko gdy tabela obiegu jest pusta – nie nadpisuje historii.
    """
    if DocumentWorkflow.query.first() is not None:
        return
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    reviewers = {a.key: a.reviewer_role for a in Attachment.query.all()}
    count = 0
    for nr, forms in data.items():
        for key, rec in forms.items():
            if not isinstance(rec, dict):
                continue
            status = rec.get('_status', 'draft')
            db.session.add(DocumentWorkflow(
                album_number=nr, form_key=key, status=status,
                reviewer_role=reviewers.get(key),
                rejection_comment=rec.get('_rejection_comment'),
                rejection_by=rec.get('_rejection_by'),
                approved_revision=(
                    store.get_form_revision(nr, key)
                    if status == "approved"
                    else None
                ),
            ))
            db.session.add(DocumentLog(
                album_number=nr, form_key=key, action=status,
                actor_name='import', actor_role='system',
                comment='stan zaimportowany z studenci.json',
            ))
            count += 1
    db.session.commit()
    if count:
        print(f"Obieg dokumentów: zaimportowano {count} stanów z JSON.")


def sync_test_forms_to_store():
    """Nadpisuje formularze kont demonstracyjnych aktualnymi danymi testowymi."""
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    test_albums = {
        item["album_number"]
        for item in USERS
        if item["role"] == "student" and item.get("album_number")
    }
    reviewers = {item.key: item.reviewer_role for item in Attachment.query.all()}
    updated = 0
    for album_number in test_albums:
        for form_key, record in data.get(album_number, {}).items():
            if not isinstance(record, dict):
                continue
            status = record.get("_status", "draft")
            revision = store.save_form(album_number, form_key, record)
            state = DocumentWorkflow.query.filter_by(
                album_number=album_number,
                form_key=form_key,
            ).first()
            if state is None:
                state = DocumentWorkflow(
                    album_number=album_number,
                    form_key=form_key,
                )
                db.session.add(state)
                db.session.add(DocumentLog(
                    album_number=album_number,
                    form_key=form_key,
                    action=status,
                    actor_name="seed",
                    actor_role="system",
                    comment="aktualizacja danych testowych",
                ))
            state.status = status
            state.reviewer_role = reviewers.get(form_key)
            state.approved_revision = revision if status == "approved" else None
            updated += 1
    db.session.commit()
    print(f"MongoDB: zaktualizowano {updated} formularzy kont testowych.")


def seed_student4_forms():
    """Wypełnia wszystkie formularze studenta 4 (album 21004) — 120 dni dziennika, wszystko zatwierdzone."""
    from datetime import date as _d, timedelta
    from core.models import LearningEffect as LE

    effects = LE.query.order_by(LE.nr).all()
    uopz = User.query.filter_by(role='uopz').first()
    zopz = User.query.filter_by(role='zopz').first()
    dziekanat = User.query.filter_by(role='dziekanat').first()
    student = User.query.filter_by(album_number='21004').first()
    if not student:
        print("Brak konta studenta 21004 – pomijam seed_student4_forms.")
        return

    today = _d.today()
    year = today.year
    rok_ak = f"{year-1}/{year}" if today.month < 10 else f"{year}/{year+1}"
    nr = "21004"
    sn = student.full_name
    un = f"dr {uopz.full_name}" if uopz else "dr Irena Malinowska"
    zn = zopz.full_name if zopz else "Zbigniew Ostrowski"
    dn = dziekanat.full_name if dziekanat else "Dorota Kamińska"
    spec = "Projektowanie baz danych i oprogramowanie użytkowe (PBDiOU)"
    company = "NetCode Solutions Sp. z o.o."
    caddr = "ul. Informatyczna 8, 10-062 Olsztyn"
    company_full = f"{company}, {caddr}"

    # 120 dni roboczych (pn–pt) zaczynając od 1 października poprzedniego roku
    base = _d(year - 1 if today.month >= 10 else year - 2, 10, 1)
    diary_dates = []
    cur = base
    while len(diary_dates) < 120:
        if cur.weekday() < 5:
            diary_dates.append(cur)
        cur += timedelta(days=1)
    start = diary_dates[0].isoformat()
    end = diary_dates[-1].isoformat()

    _tasks = [
        ("Analiza wymagań systemu bazodanowego. Spotkanie z klientem, diagram ER i dokumentacja wymagań.", "1,2,5"),
        ("Projektowanie schematu relacyjnej bazy danych MySQL. Normalizacja do 3NF, klucze i relacje.", "1,2,7"),
        ("Implementacja modelu ORM w SQLAlchemy. Tworzenie migracji Alembic i testy spójności danych.", "2,8,9"),
        ("Optymalizacja zapytań SQL — analiza EXPLAIN, dodawanie indeksów pokrywających.", "2,5,8"),
        ("Implementacja REST API w FastAPI. Endpointy CRUD, walidacja Pydantic, dokumentacja Swagger.", "2,6,9"),
        ("Tworzenie procedur składowanych i widoków w MySQL. Testy wydajności i pokrycia.", "2,7,8"),
        ("Konfiguracja środowiska Docker: docker-compose dla bazy i backendu, wolumeny trwałe.", "2,4,9"),
        ("Implementacja autoryzacji JWT i hashowanie haseł bcrypt. Middleware weryfikacji tokenów.", "3,4,8"),
        ("Pisanie testów pytest: jednostkowych i integracyjnych. Pokrycie kodu powyżej 80%.", "7,9,11"),
        ("Helpdesk: diagnoza i naprawa błędów połączeń bazodanowych, wsparcie użytkowników.", "6,8,11"),
        ("Analiza danych sprzedażowych — raport SQL, agregaty, grupowania, wykresy Chart.js.", "1,5,7"),
        ("Dokumentacja techniczna API i modelu danych. Diagramy UML, opisy endpointów.", "5,7,12"),
        ("Implementacja systemu backupu MySQL. Skrypty cron, testy przywracania bazy.", "2,4,9"),
        ("Partycjonowanie tabel i archiwizacja historycznych rekordów sprzedaży.", "2,5,8"),
        ("Code review — uwagi do kodu SQL kolegów: optymalizacje, wzorce, bezpieczeństwo.", "7,10,11"),
        ("Frontend React: panel raportów z filtrami, wykresy interaktywne, eksport CSV.", "2,6,9"),
        ("Integracja z zewnętrznym API płatności Stripe. Obsługa webhooków i idempotentność.", "2,3,8"),
        ("Wdrożenie aplikacji na serwer produkcyjny. Nginx, SSL/TLS, monitoring Prometheus.", "2,4,9"),
        ("Analiza logów produkcyjnych — identyfikacja błędów N+1, bottlenecków zapytań.", "1,5,8"),
        ("Szkolenie nowego stażysty z architektury systemu. Przygotowanie materiałów onboarding.", "7,12,13"),
    ]
    dziennik = [
        {
            "dzien": str(i + 1),
            "data": diary_dates[i].isoformat(),
            "opis": _tasks[i % len(_tasks)][0],
            "efekty": _tasks[i % len(_tasks)][1],
            "godziny": "8",
            "podpis": zn,
        }
        for i in range(120)
    ]

    efekty_all = [{"nr": e.nr, "status": "uzyskał/a"} for e in effects]
    efekty_plan = [{"nr": e.nr, "dzial_prace": "Dział Rozwoju Oprogramowania"} for e in effects]
    harmonogram = [
        {"lp": 1, "dzial": "Analiza i projektowanie bazy danych", "dni": "30"},
        {"lp": 2, "dzial": "Implementacja API i warstwy logiki", "dni": "40"},
        {"lp": 3, "dzial": "Testowanie i optymalizacja", "dni": "30"},
        {"lp": 4, "dzial": "Wdrożenie i dokumentacja", "dni": "20"},
    ]
    ocena_efektow = [
        {"nr": e.nr, "zasadny": "tak", "uzasadnienie": f"Efekt {e.nr} zrealizowany w trakcie praktyki w pełnym zakresie."}
        for e in effects
    ]
    pytania = [{"nr": i + 1, "odpowiedz": "zdecydowanie tak"} for i in range(14)]
    miejsca = [{"nazwa": company_full, "okres": f"{start} – {end}", "dni": "120"}]
    mini_zadania = [
        {"tresc": "Opisz zastosowaną architekturę bazy danych i uzasadnij wybór technologii.", "ocena": "5"},
        {"tresc": "Omów podejście do optymalizacji zapytań i strategię indeksowania.", "ocena": "5"},
        {"tresc": "Przedstaw wdrożone mechanizmy bezpieczeństwa i autoryzacji.", "ocena": "5"},
    ]

    forms = {
        "zal1": {
            "_status": "approved",
            "imie_nazwisko": sn, "nr_albumu": nr,
            "nr_porozumienia": f"ZAL-1-{nr}", "miejscowosc": "Elbląg",
            "data": today.isoformat(), "kierunek": "Informatyka",
            "specjalnosc": spec, "rodzaj_studiow": "stacjonarne",
            "nazwa_zakladu": company, "adres_zakladu": caddr,
            "nip_zakladu": "739-354-12-98",
            "reprezentant_nazwisko": "Karolina Dąbrowska",
            "reprezentant_stanowisko": "Dyrektor Zarządzający",
            "email_zakladu": "biuro@netcode.pl",
            "uczelniany_opiekun": un,
            "data_start": start, "data_end": end, "liczba_godzin": "960",
            "podpis_uczelniany": f"{un}, {today.strftime('%d.%m.%Y')}",
            "podpis_dziekanatu": f"{dn}, {today.strftime('%d.%m.%Y')}",
        },
        "zal2": {
            "_status": "approved",
            "nr_albumu": nr, "zaklad_pracy": company_full,
            "data_start": start, "data_end": end,
            "data_uzgodnienia": diary_dates[0].isoformat(),
            "podpis_zakladowy": f"Karolina Dąbrowska, {diary_dates[0].isoformat()}",
            "podpis_uczelniany": f"{un}, {diary_dates[0].isoformat()}",
        },
        "zal2a": {
            "_status": "approved",
            "imie_nazwisko": sn, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "miejsce_praktyki": company, "data_start": start, "data_end": end,
            "efekty_plan": efekty_plan, "harmonogram": harmonogram,
            "data_uzgodnienia": diary_dates[0].isoformat(),
            "podpis_uczelniany": un, "podpis_zakladowy": zn, "podpis_studenta": sn,
        },
        "zal3": {
            "_status": "approved",
            "imie_nazwisko": sn, "nr_albumu": nr,
            "nr_porozumienia": f"ZAL-1-{nr}",
            "data_porozumienia": diary_dates[0].isoformat(),
            "zaklad_pracy": company,
            "kierunek": "Informatyka", "specjalnosc": spec, "rodzaj_studiow": "stacjonarne",
            "uczelniany_opiekun": un,
            "data_start": start, "data_end": end,
            "zakladowy_opiekun_nazwisko": zn,
            "zakladowy_opiekun_funkcja": "Lider Techniczny",
            "potwierdzenie_zgloszenia": diary_dates[0].isoformat(),
            "potwierdzenie_bhp": diary_dates[0].isoformat(),
            "zaswiadczenie_zaklad": company_full,
            "zaswiadczenie_okres_od": start, "zaswiadczenie_okres_do": end,
            "zaswiadczenie_uwagi": "Student zrealizował wszystkie zaplanowane zadania z pełnym zaangażowaniem.",
            "zaswiadczenie_podpis": f"{zn}, Olsztyn, {diary_dates[-1].isoformat()}",
            "ocena_zakladowa_param": "5",
            "ocena_zakladowa_opis": "Doskonała znajomość SQL i narzędzi deweloperskich.",
            "podpis_zakladowy": f"{zn}, {diary_dates[-1].isoformat()}",
            "ocena_uczelniana_param": "5",
            "ocena_uczelniana_opis": "Student w pełni zrealizował program praktyki.",
            "podpis_uczelniany": f"{un}, {diary_dates[-1].isoformat()}",
            "ocena_sprawozdania": "5",
            "podpis_sprawozdanie": f"{un}, {diary_dates[-1].isoformat()}",
        },
        "zal4": {
            "_status": "approved",
            "imie_nazwisko": sn, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "wymiar_godzin": "960",
            "potwierdzenie_opiekuna": zn,
            "opinia_opiekuna": "Student wykazał doskonałe kompetencje programistyczne i bazodanowe.",
            "efekty": efekty_all,
        },
        "zal5": {
            "_status": "approved",
            "nr_albumu": nr, "rok_akademicki": rok_ak,
            "kierunek": "Informatyka", "forma_studiow": "stacjonarne",
            "semestr": "6", "liczba_godzin": "960",
            "pytania": pytania,
            "uwagi": "Praktyka dostarczyła cennego doświadczenia zawodowego.",
        },
        "zal6": {
            "_status": "approved",
            "imie_nazwisko": sn, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne", "rok_akademicki": rok_ak,
            "miejsce_praktyki": company,
            "data_start": start, "data_end": end,
            "wykaz_zalacznikow": "Zaświadczenie od pracodawcy, dokumentacja projektu",
            "dziennik": dziennik,
        },
        "zal7": {
            "_status": "approved",
            "imie_nazwisko": sn, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne", "rok_akademicki": rok_ak,
            "miejsce_praktyki": company,
            "charakterystyka": (
                f"{company} to dynamiczna firma informatyczna z Olsztyna specjalizująca się "
                "w tworzeniu systemów bazodanowych i aplikacji webowych dla sektora e-commerce. "
                "Zatrudnia ponad 50 specjalistów IT, używa technologii: Python, FastAPI, MySQL, Docker, React."
            ),
            "opis_prac": (
                "W trakcie praktyki realizowałem zadania z zakresu projektowania i optymalizacji baz danych "
                "MySQL, implementacji REST API w FastAPI, konfiguracji środowisk Docker, tworzenia testów "
                "automatycznych i wdrożeń produkcyjnych. Uczestniczyłem w code review i projektowaniu nowych "
                "funkcjonalności systemu e-commerce."
            ),
            "wiedza_umiejetnosci": (
                "Praktyka znacząco rozwinęła moje umiejętności w zakresie inżynierii danych, projektowania "
                "skalowalnych systemów bazodanowych, optymalizacji zapytań SQL i stosowania wzorców REST API. "
                "Poznałem metodykę Agile i narzędzia CI/CD (GitLab, Docker, Nginx)."
            ),
            "data": diary_dates[-1].isoformat(),
            "podpis_studenta": sn,
            "podpis_przelozonego": zn,
        },
        "zal8": {
            "_status": "approved",
            "imie_nazwisko": sn, "nr_albumu": nr,
            "miejsca_praktyki": miejsca,
            "ocena_s": "5", "data_s": diary_dates[-1].isoformat(), "podpis_s": un,
            "ocena_u": "5", "ocena_z": "5",
            "sklad_komisji": f"{un} (przewodnicząca), mgr Tomasz Witek, mgr Anna Kowalczyk",
            "data_zaliczenia": diary_dates[-1].isoformat(),
            "przewodniczacy": un,
            "czlonek_2": "mgr Tomasz Witek",
            "czlonek_3": "mgr Anna Kowalczyk",
            "czlonek_4": "",
            "mini_zadania": mini_zadania,
            "ocena_e": "5", "ocena_k": "5",
        },
    }

    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_data = {}

    all_data.setdefault(nr, {})
    all_data[nr].update(forms)

    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    # Oblicz i zapisz ocenę końcową w tabeli Internship
    from core.internships import get_or_create_internship
    from core.grades import calculate_final_grade, store_final_grade
    internship_obj = get_or_create_internship(student, rok_ak)
    try:
        calc = calculate_final_grade(grade_e="5", grade_s="5", grade_u="5", grade_z="5")
        store_final_grade(internship_obj, calc)
        db.session.commit()
        print(f"  Ocena końcowa studenta 4: {internship_obj.grade_k}")
    except Exception as exc:
        print(f"  Ostrzeżenie: nie udało się ustawić oceny końcowej: {exc}")

    print(f"Student 4 (nr {nr}): zaktualizowano {len(forms)} formularzy, dziennik {len(dziennik)} wpisów.")


with app.app_context():
    seed_users()
    seed_effects()
    seed_app_config()
    seed_specialties()
    seed_attachments()
    seed_role_access()
    seed_student_workflow()
    seed_survey()
    seed_form_fields()
    seed_forms()
    seed_extra_forms()
    seed_student4_forms()
    sync_test_forms_to_store()
    seed_workflow_from_json()
    print("\nGotowe.")
