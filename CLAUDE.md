# CLAUDE.md – System Rozliczania Praktyk Zawodowych

## Czym jest ten projekt

Aplikacja Flask do cyfrowego zarządzania dokumentacją praktyk zawodowych na Akademii Nauk Stosowanych w Elblągu (ANS). Zastępuje papierowy obieg 9 oficjalnych załączników (Zał. 1–9) formularzami internetowymi z możliwością pobrania PDF.

---

## Uruchomienie od zera (setup)

### Wymagania wstępne
- **Docker Desktop** (zalecane) — baza MariaDB + Flask w kontenerach
- Python 3.11+ tylko przy uruchamianiu lokalnym bez Dockera

### Uruchomienie przez Docker (zalecane)

```bash
# 1. Skopiuj i uzupełnij .env (3 wymagane hasła: SECRET_KEY, MYSQL_ROOT_PASSWORD, MYSQL_PASSWORD)
copy .env.example .env

# 2. Zbuduj i uruchom
docker compose up --build -d

# 3. Poczekaj ~30 sek. na healthcheck MariaDB+MongoDB, następnie zaseeduj
docker compose exec flask python -m core.seed
```

Aplikacja dostępna pod: **http://localhost:5000**

### Uruchomienie lokalne (bez Dockera)

```bash
# 1. Uruchom MariaDB i MongoDB w Dockerze (Flask lokalnie)
docker compose up db mongo -d

# 2. Ustaw w .env:
# DATABASE_URL=mysql+pymysql://ems_user:TWOJE_HASLO@localhost:3306/ems?charset=utf8mb4
# MONGO_URL=mongodb://localhost:27017/ems

# 3. Wirtualne środowisko i zależności
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. Zaseeduj bazę (uruchamiaj jako moduł z katalogu głównego)
venv\Scripts\python -m core.seed

# 5. Uruchom aplikację
venv\Scripts\python app.py
```

### Reset danych

```bash
# Pełny reset (MariaDB + MongoDB + formularze) – usuwa wolumeny
docker compose down -v
docker compose up -d
docker compose exec flask python -m core.seed
```

> Treść formularzy żyje w MongoDB (kolekcja `practice_forms`). `data/studenci.json` jest już tylko źródłem jednorazowego importu (`core/store.import_from_json`) – nie jest zapisywany w czasie działania aplikacji.

---

### Konta testowe

| E-mail | Hasło | Rola | Nr albumu |
|--------|-------|------|-----------|
| student@student.ans-elblag.pl | Student123! | student | 21001 (Aleksandra Kowalska – ASiSK) |
| student2@student.ans-elblag.pl | Student123! | student | 21002 (Marek Nowak – PBDiOU) |
| student3@student.ans-elblag.pl | Student123! | student | 21003 (Katarzyna Wróbel – M3D) |
| opiekun@ans-elblag.pl | Opiekun123! | uopz | — (dr Irena Malinowska) |
| zopz@firma.pl | Zopz123! | zopz | — (Zbigniew Ostrowski) |
| dziekanat@ans-elblag.pl | Dziekanat123! | dziekanat | — (Dorota Kamińska) |
| admin@ans-elblag.pl | Admin123! | admin | — (Adam Wiśniewski) |

---

## Architektura projektu

```
flask-app-form/
├── app.py                  # Główna aplikacja (jedyny moduł w korzeniu) – trasy, logika, workflow
├── core/                   # Pakiet z modułami pomocniczymi
│   ├── __init__.py
│   ├── models.py           # Modele SQLAlchemy (17 tabel MariaDB)
│   ├── store.py            # Magazyn treści formularzy w MongoDB (load_data/save_data)
│   ├── auth.py             # Logowanie/wylogowanie, Flask-Login
│   ├── workflow.py         # Obieg dokumentów: status + dziennik zdarzeń w MariaDB
│   ├── config.py           # Konfiguracja z .env (wymaga DATABASE_URL)
│   ├── seed.py             # Seeduje MariaDB + import formularzy do MongoDB (python -m core.seed)
│   ├── generate_pdf.py     # Generowanie PDF przez WeasyPrint
│   └── generate_pdf_latex.py  # Generowanie PDF przez xelatex (wymaga MiKTeX)
│
├── templates/
│   ├── base.html           # Layout: header, sidebar, powiadomienia, tryb recenzji
│   ├── login.html          # Logowanie z szybkimi przyciskami
│   ├── index.html          # Dashboard
│   ├── podglad.html        # Profil studenta: karty załączników, recenzja, odrzucenia
│   ├── powiadomienia.html  # Strona listy powiadomień
│   ├── profil.html         # Profil studenta (specjalność, tryb studiów)
│   ├── konfiguracja.html   # Konfiguracja semestru (dziekanat/admin)
│   ├── zal1.html–zal9.html # Formularze wejściowe
│   ├── print/              # Szablony druku HTML (WeasyPrint)
│   └── latex/              # Szablony LaTeX (.tex.j2)
│
├── static/css/base.css     # Arkusz stylów (~1650 linii)
│
├── data/
│   ├── studenci.json       # Źródło jednorazowego importu do MongoDB (nie zapisywane w runtime)
│   └── uploads/            # Pliki załączone przez studentów (per nr albumu)
│
├── instance/               # (legacy, nie używane przy MariaDB)
│
├── Dockerfile              # Obraz Flask z zależnościami WeasyPrint
├── docker-compose.yml      # Serwisy: mariadb:11 + mongo:7 + flask
└── .env.example            # Szablon zmiennych środowiskowych
```

### Przepływ danych

```
Formularz HTML → app.py route → walidacja → MongoDB (core.store, kolekcja practice_forms)
Pliki PDF/kody → uploads/{nr_albumu}/   (bajty na dysku; metadane w treści formularza w Mongo)
Baza MariaDB   → użytkownicy, efekty, specjalności, załączniki(metadane), konfiguracja, obieg+log
MongoDB        → treść formularzy Zał. 1–9 (jeden dokument na nr_albumu+zal_key)
```

### Status dokumentu (_status w treści formularza)

```
draft    → Szkic (domyślny, edytowalny)
pending  → Oczekuje na zatwierdzenie (zablokowany do edycji)
approved → Zatwierdzone
rejected → Odrzucono (edytowalny; po zapisie auto-wraca do pending)
```

**Ważne:** Po poprawieniu odrzuconego dokumentu `_persist()` automatycznie zmienia status z `rejected` → `pending`, bez potrzeby ręcznego klikania "Wyślij do zatwierdzenia".

---

## Konfiguracja .env

```env
# Wymagane
SECRET_KEY=min-32-losowe-znaki
MYSQL_ROOT_PASSWORD=
MYSQL_PASSWORD=

# Baza relacyjna (MariaDB)
MYSQL_DATABASE=ems
MYSQL_USER=ems_user
DATABASE_URL=mysql+pymysql://ems_user:HASLO@db:3306/ems?charset=utf8mb4

# Baza dokumentowa (MongoDB – treść formularzy); nazwa bazy na końcu URL
MONGO_URL=mongodb://mongo:27017/ems

# Serwer
FLASK_HOST=127.0.0.1    # 0.0.0.0 w docker-compose (hardkodowane)
FLASK_PORT=5000
FLASK_DEBUG=false
DB_PORT=3306
MONGO_PORT=27017
```

---

## Trasy (routes)

| Ścieżka | Rola | Opis |
|---------|------|------|
| `/login` | wszyscy | Logowanie |
| `/auth/logout` | wszyscy | Wylogowanie |
| `/` | wszyscy | Dashboard |
| `/regulamin` | wszyscy | Regulamin |
| `/powiadomienia` | wszyscy | Lista powiadomień wymagających działania |
| `/profil` | student | Edycja specjalności i trybu studiów |
| `/konfiguracja` | dziekanat, admin | Konfiguracja dat semestru |
| `/student/<nr>` | wszyscy | Profil studenta (ZOPZ widzi tylko swoje formularze) |
| `/student/<nr>/usun` | admin, dziekanat | Usuń studenta |
| `/student/<nr>/<zal>/pobierz` | wszyscy | Pobierz PDF (WeasyPrint) |
| `/student/<nr>/<zal>/drukuj` | wszyscy | Widok do druku |
| `/student/<nr>/<zal>/formularz` | wszyscy | Podgląd readonly |
| `/student/<nr>/<zal>/recenzuj` | uopz, zopz, admin | **Tryb recenzji** – formularz z checkboxami |
| `/student/<nr>/<zal>/wyslij` | twórca | Wyślij do zatwierdzenia |
| `/student/<nr>/<zal>/zatwierdz` | recenzent | Zatwierdź |
| `/student/<nr>/<zal>/odrzuc` | recenzent | Odrzuć z komentarzem |
| `/student/<nr>/zal6/plik/<id>` | wszyscy | Pobierz plik załącznika z dziennika |
| `/admin/wypelnij/<nr>` | admin | Wypełnij danymi testowymi |
| `/zal[1-9]` | rola-zależne | Nowy formularz |
| `/zal[1-9]/<nr>/edytuj` | rola-zależne | Edytuj formularz |
| `/zal[1-9]/<nr>/usun` | rola-zależne | Usuń formularz |

---

## Model bazy danych (MariaDB)

### Tabele słownikowe (dane statyczne, seedowane)

| Tabela | Opis |
|--------|------|
| `specialties` | 3 specjalności (ASiSK, PBDiOU, M3D) |
| `attachments` | 13 załączników z metadanymi i recenzentem |
| `role_form_access` | Które role mogą edytować które formularze |
| `student_workflow_steps` | Kroki przewodnika studenta |
| `survey_questions` | 14 pytań ankietowych (Zał. 5) |
| `survey_options` | 5 opcji Likerta |
| `form_fields` | Nazwy pól formularzy (do dropdown recenzji) |
| `learning_effects` | 13 efektów uczenia się |
| `app_config` | Konfiguracja: miesiące startu semestrów |

### Tabele użytkowników

**`document_workflow`** – autorytatywny stan obiegu każdego dokumentu (album + formularz): `status`, `reviewer_role`, `rejection_comment`, `rejection_by`, `updated_at`. Treść formularza pozostaje w MongoDB; tu trzymany jest status i decyzja.

**`document_log`** – dziennik zdarzeń (append-only): `action` (created/updated/submitted/approved/rejected/deleted), `actor_id/name/role`, `comment`, `created_at`. Każda zmiana statusu zapisuje wpis przez `workflow.py`.

**`users`** – konta użytkowników:
- `email`, `password_hash`, `first_name`, `last_name`, `role`
- `album_number` – numer albumu (studenci)
- `speciality` – specjalność (student uzupełnia w /profil)
- `study_mode` – stacjonarne/niestacjonarne
- `is_active`, `email_verified`, `last_login_at`
- `failed_login_attempts`, `locked_until` (przygotowane, bez logiki)

---

## System ról (RBAC)

| Rola | Tworzy/edytuje | Widzi |
|------|----------------|-------|
| **student** | Zał. 1, 2a, 4b, 5, 6, 7, 7a | Tylko swoje dokumenty |
| **uopz** | Zał. 2, 4a | Wszyscy studenci + pełny widok |
| **zopz** | Zał. 3, 4, 9 | Wszyscy studenci + **tylko formularze: 2a, 3, 4, 6, 7a, 9** |
| **dziekanat** | Zał. 8 | Wszyscy + może usuwać + konfiguracja semestru |
| **admin** | Wszystkie | Wszystko |

---

## Helpery i gettery danych z bazy

```python
get_specialties()       → [str]  # lista specjalności
get_attachments()       → [dict] # metadane załączników
get_document_workflow() → dict   # kto zatwierdza każdy formularz
get_role_form_access()  → dict   # rola → set kluczy formularzy
get_student_workflow()  → [dict] # kroki przewodnika studenta
get_survey_questions()  → [str]  # pytania ankietowe
get_survey_options()    → [str]  # opcje Likerta
get_form_fields()       → dict   # formularz → lista pól
get_current_semester()  → str    # np. "2025/2026 letni"
get_config_value(key)   → str    # wartość z app_config
```

Wszystkie gettery pobierają dane z MariaDB przy każdym żądaniu (bez cache — tabele są małe).

---

## Workflow odrzucania dokumentów

### Stary flow (zastąpiony)
Modal inline w podglad.html z textarea i dropdown pól.

### Nowy flow – Tryb recenzji (`/recenzuj`)
1. Recenzent klika **"Przejrzyj i odrzuć…"** w karcie dokumentu
2. Otwiera się formularz studenta w trybie tylko do odczytu
3. JavaScript injektuje checkbox przy każdym polu formularza
4. Dla dziennika (Zał. 6): checkboxy w kolumnach Data, Opis, Nr efektów każdego wiersza
5. Sticky panel na dole: komentarz ogólny + lista zaznaczonych pól + przycisk "Odrzuć dokument"
6. Submission → `odrzuc_dokument` → status `pending` → `rejected`
7. Student edytuje → `_persist()` auto-zmienia status `rejected` → `pending`
8. ZOPZ/UOPZ widzi dokument ponownie w kolejce

---

## Powiadomienia

Generowane dynamicznie przy każdym żądaniu przez `_build_notifications()`:

| Rola | Kiedy dostaje powiadomienie |
|------|------------------------------|
| student | Dokument odrzucony (wymaga poprawy) |
| uopz | Dokument oczekuje na ich zatwierdzenie |
| zopz | Dokument oczekuje na ich zatwierdzenie |
| admin | Wszystkie oczekujące dokumenty |

Bell w headerze → dropdown + strona `/powiadomienia`. Kliknięcie → profil studenta z auto-scrollem do karty dokumentu (`#doc-zal6` itp.).

---

## Automatyczny rok akademicki

`get_current_semester()` wylicza na podstawie miesiąca:
- **Marzec–Wrzesień** → `{rok-1}/{rok} letni`
- **Październik–Luty** → `{rok}/{rok+1} zimowy`

Granice miesięcy konfigurowalne w `/konfiguracja` (dziekanat/admin) → zapisane w tabeli `app_config`.

Rok akademicki jest automatycznie wstawiany w nowe formularze studenta przez `build_prefill()`.

---

## Załączniki plików (Zał. 6)

Studenci mogą dołączać pliki do Dziennika praktyki:
- Typy: PDF, DOCX, PY, JS, TS, SQL, TXT, CSV, JSON, XML, ZIP, PNG, JPG, XLSX
- Limit: 10 MB na plik
- Storage: `data/uploads/{nr_albumu}/{uuid}.{ext}`
- Metadane w treści formularza (MongoDB): `zal6["pliki"]`
- Pobieranie: `/student/<nr>/zal6/plik/<id>`

---

## Co jest zaimplementowane

- **Logowanie** email/hasło przez Flask-Login; szybkie przyciski na stronie logowania
- **Baza MariaDB** przez Docker Compose z healthcheckiem (użytkownicy, słowniki, konfiguracja, obieg+log)
- **MongoDB** (Docker, kolekcja `practice_forms`) – treść formularzy Zał. 1–9; dostęp przez `core/store.py` (`load_data`/`save_data`); jednorazowy import z `studenci.json`
- **Wszystkie dane konfiguracyjne w DB** (specjalności, załączniki, dostępy ról, workflow, ankieta, pola formularzy)
- **CRUD** dla wszystkich 13 formularzy (Zał. 1–9 + warianty 2a, 4a, 4b, 7a)
- **RBAC** z filtrowaniem widoku (ZOPZ widzi tylko swoje formularze)
- **Workflow zatwierdzania** draft → pending → approved / rejected → pending (auto po poprawce)
- **Tryb recenzji** z JS checkboxami na każdym polu formularza + sticky panel
- **Komentarze do wpisów dziennika** per kolumna (Data, Opis, Efekty)
- **Powiadomienia** (bell + dropdown + strona `/powiadomienia`) z nawigacją do dokumentu
- **Profil studenta** `/profil` – specjalność, tryb studiów, rok studiów i semestr (`users.semester`, `users.study_year`; semestr auto do Zał. 5)
- **Auto-wypełnianie formularzy** – dane studenta z profilu: imię, nazwisko, nr albumu, specjalność, tryb studiów, rok akademicki
- **Automatyczny rok akademicki** z konfigurowalną datą startu semestru (/konfiguracja)
- **Upload plików** w Zał. 6 (kody, skrypty, PDF) – widoczne na karcie, w formularzu, w trybie recenzji oraz w widoku druku/PDF
- **Dziennik zdarzeń obiegu w bazie** (`document_workflow` + `document_log` via `workflow.py`) – każde utworzenie/wysłanie/zatwierdzenie/odrzucenie/usunięcie zapisuje kto/kiedy/co; historia widoczna na profilu studenta
- **Walidacja serwerowa** (`core/validators.py`) – imię i nazwisko (litery/spacje, ≥2 wyrazy), nr albumu (4–6 cyfr), NIP (10 cyfr + suma kontrolna), daty (format + zakres), opis dziennika (min. 100 znaków). Podgląd „na bieżąco" (`static/js/form-validate.js`) – pokazuje TYLKO błędy (czerwone), bez potwierdzania poprawnych pól; blokuje wysyłkę przy błędach
- **Auto-pieczątka zatwierdzenia** – po akceptacji (`zatwierdz_dokument`) na dokumencie zapisuje się `_approved_by/_approved_role/_approved_at`; karta w `podglad.html` pokazuje pieczątkę „ZATWIERDZONO — kto · data"
- **Generowanie PDF** przez WeasyPrint
- **Szablony LaTeX** (gotowe, wymagają MiKTeX)
- **Dashboard** studenta z przewodnikiem kroków
- **Dashboard pracowniczy** z listą studentów i dokumentami oczekującymi

---

## Co wymaga dokończenia / poprawy

- **Panel admina użytkowników** – brak strony zarządzania kontami (zmiana roli, reset hasła, blokada)
- **Blokowanie konta po błędach logowania** – pola `failed_login_attempts` i `locked_until` w modelu, brak logiki w auth.py
- **Weryfikacja e-mail** – pole `email_verified` w modelu, brak mechanizmu wysyłania maili
- **Logowanie OAuth przez Microsoft** – pola w .env, brak tras (msal/authlib)
- **Przełączenie PDF na LaTeX** – po zainstalowaniu MiKTeX podmień w trasie `pobierz_pdf`: `generate_pdf` → `generate_pdf_latex`
- **Powiadomienia e-mail** – brak wysyłki e-mail przy zmianie statusu dokumentu
- **Eksport CSV/Excel** – lista studentów z ocenami dla dziekanatu
- **Kolejki recenzenta z DB** – statusy są już zapisywane i logowane w bazie (`document_workflow`/`document_log`), ale kolejki/powiadomienia nadal czytają `_status` z treści formularza (Mongo); do rozważenia oparcie kolejek bezpośrednio o tabelę `document_workflow`
- **Wizualny podgląd obiegu dokumentów (diagram workflow)** – dodać widok pokazujący stan każdego załącznika (Zał. 1–9) jako diagram fazowy (Faza 0–4), z kolorystycznym statusem (szkic / oczekuje / zatwierdzone / odrzucone) oraz ścieżką sekwencyjną i równoległą:
  - **Dla studenta** – własny obieg: które dokumenty zrobione, które czekają, gdzie utknął (z linkami do edycji/poprawy)
  - **Dla UOPZ / ZOPZ** – widok zbiorczy „moich studentów" z diagramem na każdego (szybkie wyłapanie, kto blokuje proces, co czeka na moją akceptację)
  - **Dla dziekanatu** – widok kilkunastu studentów naraz (tabela/grid z mini-diagramami statusów albo widok agregowany: ile osób w której fazie, ile dokumentów odrzuconych, ile gotowych do Zał. 8)
  - Bazą danych są tabele `document_workflow` + `document_log` (już istnieją) – diagram tylko je renderuje, np. SVG/CSS grid lub biblioteką typu Mermaid renderowaną client-side

---

## Najczęstsze problemy

| Problem | Rozwiązanie |
|---------|-------------|
| Port 5000 zajęty | Zmień w .env: `FLASK_PORT=5001` |
| MariaDB nie startuje | Sprawdź logi: `docker compose logs db` |
| Flask startuje na 127.0.0.1 (niedostępny z zewnątrz) | docker-compose.yml hardkoduje `FLASK_HOST=0.0.0.0` — upewnij się że używasz `docker compose up` |
| Puste formularze / brak efektów | Uruchom seed: `docker compose exec flask python -m core.seed` |
| `libgdk-pixbuf2.0-0` błąd w Docker | Nazwa pakietu zmieniła się na `libgdk-pixbuf-xlib-2.0-0` w Debianie Trixie — Dockerfile jest już poprawiony |
| Komentarz recenzenta nie wyświetla się | Bug Jinja2 z `r._xxx` – naprawione na `r.get('_xxx', '')` w podglad.html |
| Po poprawieniu dokument nie wraca do recenzenta | Naprawione – `_persist()` auto-zmienia `rejected` → `pending` |
