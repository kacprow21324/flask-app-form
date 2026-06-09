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
    ("zal9",  "9",  "Oświadczenie instytucji",                            None,    None,                        12),
]

# role -> [form_keys]
ROLE_ACCESS_DATA = {
    'student':   ['zal1', 'zal2a', 'zal4b', 'zal5', 'zal6', 'zal7', 'zal7a'],
    # uopz ma dostęp do zal4b żeby wypełnić sekcję E (Opinia Komisji)
    'uopz':      ['zal2', 'zal4a', 'zal4b'],
    'zopz':      ['zal3', 'zal4', 'zal9'],
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
              "Reprezentant – nazwisko", "Reprezentant – stanowisko", "Uczelniany opiekun",
              "Data rozpoczęcia", "Data zakończenia", "Liczba godzin",
              "Podpis zakładowy", "Podpis uczelniany"],
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
            db.session.add(existing)
            updated += 1
            print(f"  zaktualizowano: {data['email']}  ({data['first_name']} {data['last_name']})")
        else:
            env_name = f"SEED_{data['role'].upper()}_PASSWORD"
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
                gender=data.get("gender"),
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
    added = 0
    for form_key, fields in FORM_FIELDS_DATA.items():
        for idx, field_name in enumerate(fields):
            if not FormField.query.filter_by(form_key=form_key, field_name=field_name).first():
                db.session.add(FormField(form_key=form_key, sort_order=idx, field_name=field_name))
                added += 1
    db.session.commit()
    if added:
        print(f"Pola formularzy: dodano {added} wpisów.")


def seed_forms():
    """Wypełnia studenci.json danymi testowymi dla konta studenckiego (album 21001)."""
    from datetime import date as _d
    from core.models import LearningEffect as LE

    effects = LE.query.order_by(LE.nr).all()
    uopz = User.query.filter_by(role='uopz').first()
    zopz = User.query.filter_by(role='zopz').first()
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
            "nr_porozumienia": f"01/INF/{year}", "miejscowosc": "Elbląg",
            "data": f"{year}-03-15", "kierunek": "Informatyka",
            "specjalnosc": spec, "rodzaj_studiow": "stacjonarne",
            "nazwa_zakladu": company, "adres_zakladu": "ul. Portowa 12, 80-001 Gdańsk",
            "nip_zakladu": "589-212-34-56",
            "reprezentant_nazwisko": "Piotr Zieliński",
            "reprezentant_stanowisko": "Prezes Zarządu",
            "uczelniany_opiekun": uopz_name,
            "data_start": start, "data_end": end, "liczba_godzin": "240",
            "podpis_zakladowy": f"Piotr Zieliński, Gdańsk, {year}-03-15",
            "podpis_uczelniany": f"{uopz_name}, Elbląg, {year}-03-15",
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
            "nr_porozumienia": f"01/INF/{year}",
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
            "wymiar_godzin": "240",
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
            "semestr": "6", "liczba_godzin": "240",
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
        "zal9": {
            "_status": "approved",
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "miejscowosc": "Gdańsk", "data": f"{year}-03-15",
            "nazwa_instytucji": company,
            "termin_od": start, "termin_do": end,
            "opiekun_imie_nazwisko": zopz_name,
            "opiekun_stanowisko": "Kierownik Działu IT",
            "opiekun_telefon": "+48 58 123 45 67",
            "opiekun_email": "z.ostrowski@technosystems.pl",
            "upowazniont_imie_nazwisko": "Piotr Zieliński",
            "upowazniont_stanowisko": "Prezes Zarządu",
            "podpis": f"Piotr Zieliński, Gdańsk, {year}-03-15",
        },
    }

    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_data = {}

    all_data.setdefault(nr, {})
    filled = 0
    for key, record in forms.items():
        if key not in all_data[nr]:
            all_data[nr][key] = record
            filled += 1

    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print(f"Formularze: wypełniono {filled} dla studenta nr albumu {nr}.")


def seed_extra_forms():
    """Wypełnia studenci.json danymi testowymi dla studentów 21002 i 21003."""
    from datetime import date as _d
    from core.models import LearningEffect as LE

    effects = LE.query.order_by(LE.nr).all()
    uopz = User.query.filter_by(role='uopz').first()
    zopz = User.query.filter_by(role='zopz').first()

    un = uopz.full_name if uopz else "dr Irena Malinowska"
    zn = zopz.full_name if zopz else "Zbigniew Ostrowski"

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
            "nr_por": f"02/INF/{year}",
            "status_zal1": "approved",
            "status_zal2a": "pending",
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
            "nr_por": f"03/INF/{year}",
            "status_zal1": "draft",
            "status_zal2a": "draft",
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
                "nr_porozumienia": s["nr_por"], "miejscowosc": "Elbląg",
                "data": f"{year}-02-20", "kierunek": "Informatyka",
                "specjalnosc": s["spec"], "rodzaj_studiow": "stacjonarne",
                "nazwa_zakladu": s["company"],
                "adres_zakladu": s["company_full"].split(", ", 1)[1] if ", " in s["company_full"] else "",
                "nip_zakladu": "",
                "reprezentant_nazwisko": s["repr"],
                "reprezentant_stanowisko": s["repr_pos"],
                "uczelniany_opiekun": un,
                "data_start": s["start"], "data_end": s["end"], "liczba_godzin": "240",
                "podpis_zakladowy": s["repr"],
                "podpis_uczelniany": un,
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
            "zal9": {
                "_status": "draft",
                "imie_nazwisko": s["name"], "nr_albumu": nr,
                "miejscowosc": s["company_full"].split(",")[-1].strip().split()[-1] if "," in s["company_full"] else "Olsztyn",
                "data": f"{year}-02-20",
                "nazwa_instytucji": s["company"],
                "termin_od": s["start"], "termin_do": s["end"],
                "opiekun_imie_nazwisko": zn,
                "opiekun_stanowisko": "Kierownik Działu IT",
                "opiekun_telefon": s["zopz_phone"],
                "opiekun_email": s["zopz_email"],
                "upowazniont_imie_nazwisko": s["repr"],
                "upowazniont_stanowisko": s["repr_pos"],
                "podpis": f"{s['repr']}, {year}-02-20",
            },
        }
        filled = 0
        for key, record in forms.items():
            if key not in all_data[nr]:
                all_data[nr][key] = record
                filled += 1
        total_filled += filled
        if filled:
            print(f"  Formularze: wypełniono {filled} dla studenta nr albumu {nr} ({s['name']}).")

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
    imported = store.import_from_json(DB_FILE)
    if imported:
        print(f"MongoDB: zaimportowano {imported} formularzy z studenci.json.")
    seed_workflow_from_json()
    print("\nGotowe.")
