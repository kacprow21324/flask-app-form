"""
Uruchom raz (lub po resecie), żeby wypełnić bazę użytkownikami testowymi i efektami:
  python seed.py

Istniejący użytkownicy mają zaktualizowane imiona i nazwiska.
"""
import json, os
from werkzeug.security import generate_password_hash
from app import app
from models import db, User, LearningEffect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE  = os.path.join(BASE_DIR, "data", "studenci.json")


USERS = [
    {
        "email": "student@student.ans-elblag.pl",
        "password": "Student123!",
        "first_name": "Aleksandra",
        "last_name": "Kowalska",
        "role": "student",
        "album_number": "21001",
        "is_active": 1,
    },
    {
        "email": "opiekun@ans-elblag.pl",
        "password": "Opiekun123!",
        "first_name": "Irena",
        "last_name": "Malinowska",
        "role": "uopz",
        "album_number": None,
        "is_active": 1,
    },
    {
        "email": "zopz@firma.pl",
        "password": "Zopz123!",
        "first_name": "Zbigniew",
        "last_name": "Ostrowski",
        "role": "zopz",
        "album_number": None,
        "is_active": 1,
    },
    {
        "email": "dziekanat@ans-elblag.pl",
        "password": "Dziekanat123!",
        "first_name": "Dorota",
        "last_name": "Kamińska",
        "role": "dziekanat",
        "album_number": None,
        "is_active": 1,
    },
    {
        "email": "admin@ans-elblag.pl",
        "password": "Admin123!",
        "first_name": "Adam",
        "last_name": "Wiśniewski",
        "role": "admin",
        "album_number": None,
        "is_active": 1,
    },
    {
        "email": "student2@student.ans-elblag.pl",
        "password": "Student123!",
        "first_name": "Marek",
        "last_name": "Nowak",
        "role": "student",
        "album_number": "21002",
        "is_active": 1,
    },
    {
        "email": "student3@student.ans-elblag.pl",
        "password": "Student123!",
        "first_name": "Katarzyna",
        "last_name": "Wróbel",
        "role": "student",
        "album_number": "21003",
        "is_active": 1,
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


def seed_users():
    added = updated = 0
    for data in USERS:
        existing = User.query.filter_by(email=data["email"]).first()
        if existing:
            existing.first_name = data["first_name"]
            existing.last_name  = data["last_name"]
            db.session.add(existing)
            updated += 1
            print(f"  zaktualizowano: {data['email']}  ({data['first_name']} {data['last_name']})")
        else:
            user = User(
                email=data["email"],
                password_hash=generate_password_hash(data["password"]),
                first_name=data["first_name"],
                last_name=data["last_name"],
                role=data["role"],
                album_number=data.get("album_number"),
                is_active=data["is_active"],
                email_verified=1,
            )
            db.session.add(user)
            added += 1
            print(f"  dodano: {data['email']}  hasło: {data['password']}")
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


def seed_forms():
    """Wypełnia studenci.json danymi testowymi dla konta studenckiego (album 21001)."""
    from datetime import date as _d
    from models import LearningEffect as LE

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
            "_status": "approved",   # podpisane przed praktyką przez UOPZ
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
            "_status": "approved",   # program uzgodniony przez UOPZ przed praktyką
            "nr_albumu": nr, "zaklad_pracy": company_full,
            "data_start": start, "data_end": end,
            "data_uzgodnienia": f"{year}-03-15",
            "podpis_zakladowy": f"Piotr Zieliński, {year}-03-15",
            "podpis_uczelniany": f"{uopz_name}, {year}-03-15",
        },
        "zal2a": {
            "_status": "approved",   # harmonogram zatwierdzony przez ZOPZ przed praktyką
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
            "_status": "pending",    # karta wypełniona przez ZOPZ, czeka na UOPZ
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
            "ocena_zakladowa_opis": "Studentka wykazała dużą inicjatywę i kompetencje techniczne. Sprawnie realizowała zadania z zakresu administracji sieciowej.",
            "podpis_zakladowy": f"{zopz_name}, {year}-06-01",
            "ocena_uczelniana_param": "5",
            "ocena_uczelniana_opis": "Studentka aktywnie uczestniczyła w praktyce. Dokumentacja kompletna i zgodna z wymaganiami.",
            "podpis_uczelniany": f"{uopz_name}, {year}-06-05",
            "ocena_sprawozdania": "5",
            "podpis_sprawozdanie": f"{uopz_name}, {year}-06-10",
        },
        "zal4": {
            "_status": "approved",   # potwierdzenie efektów przez ZOPZ — zatwierdzone
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "wymiar_godzin": "240",
            "potwierdzenie_opiekuna": zopz_name,
            "opinia_opiekuna": "Studentka wykazała wysokie zaangażowanie i kompetencje. Polecam zaliczenie wszystkich efektów.",
            "efekty": efekty_all,
        },
        "zal4a": {
            "_status": "approved",   # UOPZ ocenił wniosek studenta — zatwierdzone
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "data_zlozenia": f"{year}-03-10",
            "ocena_efektow": ocena_efektow,
            "rekomendacja": "Zaliczam efekty uczenia się wskazane we wniosku studenta.",
            "uwagi": "Studentka przedłożyła kompletną dokumentację potwierdzającą realizację efektów.",
            "data_oceny": f"{year}-03-12",
            "podpis_uopz": uopz_name,
        },
        "zal4b": {
            "_status": "approved",   # wniosek studenta zatwierdzony przez UOPZ
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
            "_status": "draft",      # ankieta — student jeszcze nie wysłał
            "nr_albumu": nr, "rok_akademicki": rok_ak,
            "kierunek": "Informatyka", "forma_studiow": "stacjonarne",
            "semestr": "6", "liczba_godzin": "240",
            "pytania": pytania,
            "uwagi": "Praktyka w pełni odpowiadała moim oczekiwaniom zawodowym.",
        },
        "zal6": {
            "_status": "pending",    # dziennik wysłany do ZOPZ, czeka na zatwierdzenie
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne", "rok_akademicki": rok_ak,
            "miejsce_praktyki": company,
            "data_start": start, "data_end": end,
            "wykaz_zalacznikow": "Zaświadczenie od pracodawcy",
            "dziennik": dziennik,
        },
        "zal7": {
            "_status": "rejected",   # sprawozdanie odrzucone przez UOPZ do poprawy
            "_rejection_comment": "Sprawozdanie wymaga rozbudowania sekcji opisu wykonanych prac. Proszę o uzupełnienie informacji dotyczących stosowanych technologii sieciowych i konkretnych zadań realizowanych w każdym tygodniu praktyki.",
            "_rejection_by": uopz_name,
            "_field_comments": [
                {"field": "Opis wykonanych prac", "note": "Zbyt ogólny – proszę opisać konkretne zadania z każdego tygodnia."},
                {"field": "Charakterystyka zakładu", "note": "Proszę rozbudować o informacje o stosowanych technologiach."},
            ],
            "imie_nazwisko": student_name, "nr_albumu": nr,
            "kierunek": "Informatyka", "specjalnosc": spec,
            "rodzaj_studiow": "stacjonarne", "rok_akademicki": rok_ak,
            "miejsce_praktyki": company,
            "charakterystyka": f"{company} jest firmą informatyczną z Gdańska specjalizującą się w rozwiązaniach sieciowych i systemowych dla sektora MŚP. Zatrudnia 45 pracowników.",
            "opis_prac": "Konfiguracja sieci LAN/WAN, administracja serwerami Linux/Windows Server, tworzenie dokumentacji technicznej, monitoring infrastruktury i helpdesk.",
            "wiedza_umiejetnosci": "Zastosowałam wiedzę z administracji sieciowej i bezpieczeństwa IT. Nauczyłam się konfigurowania sprzętu Cisco i zarządzania serwerami produkcyjnymi.",
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
            "_status": "approved",   # oświadczenie instytucji podpisane przed praktyką
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

    # Load existing JSON and only fill missing keys for this student
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
    from models import LearningEffect as LE

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


with app.app_context():
    db.create_all()
    seed_users()
    seed_effects()
    seed_forms()
    seed_extra_forms()
    print("\nGotowe.")
