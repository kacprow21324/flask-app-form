# CLAUDE.md – System Rozliczania Praktyk Zawodowych

## Czym jest ten projekt

Aplikacja Flask do cyfrowego zarządzania dokumentacją praktyk zawodowych na Akademii Nauk Stosowanych w Elblągu (ANS). Zastępuje papierowy obieg 9 oficjalnych załączników (Zał. 1–9) formularzami internetowymi z możliwością pobrania PDF.

---

## Uruchomienie od zera (setup)

### Wymagania wstępne
- Python 3.11+ (sprawdź: `python --version`)
- pip (wbudowany w Pythona)
- Opcjonalnie: Docker + Docker Compose

### Uruchomienie lokalne (bez Dockera)

```bash
# 1. Sklonuj repozytorium (lub wejdź do folderu)
cd C:\Repozytoria\flask-app-form

# 2. Utwórz wirtualne środowisko
python -m venv venv

# 3. Aktywuj środowisko
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate

# 4. Zainstaluj zależności
pip install -r requirements.txt

# 5. (Opcjonalnie) Skopiuj plik środowiska
copy .env.example .env

# 6. Wypełnij bazę danych użytkownikami testowymi i efektami uczenia się
python seed.py

# 7. Uruchom aplikację
python app.py
```

Aplikacja będzie dostępna pod: **http://127.0.0.1:5000**

### Uruchomienie przez Docker

```bash
docker compose up --build
```

Aplikacja dostępna pod: **http://localhost:5000**

### Konta testowe (seed.py tworzy je automatycznie)

| E-mail | Hasło | Rola | Nr albumu |
|--------|-------|------|-----------|
| student@student.ans-elblag.pl | Student123! | student | 21001 |
| opiekun@ans-elblag.pl | Opiekun123! | uopz | — |
| zopz@firma.pl | Zopz123! | zopz | — |
| dziekanat@ans-elblag.pl | Dziekanat123! | dziekanat | — |
| admin@ans-elblag.pl | Admin123! | admin | — |

Na stronie logowania dostępne są przyciski „Zaloguj jako..." do szybkiego logowania bez wpisywania danych.

---

## Konfiguracja DBeaver (przeglądanie bazy danych)

DBeaver to darmowe narzędzie do przeglądania i edytowania baz danych z interfejsem graficznym.

### Instalacja DBeaver

1. Pobierz **DBeaver Community** (bezpłatna wersja) ze strony: https://dbeaver.io/download/
2. Zainstaluj jak standardowy program.

### Podłączenie bazy SQLite projektu

Baza danych tworzy się automatycznie przy pierwszym uruchomieniu aplikacji jako plik:
```
C:\Repozytoria\flask-app-form\instance\ems.db
```

Kroki konfiguracji w DBeaver:

1. **Otwórz DBeaver** → kliknij ikonę wtyczki/nowego połączenia (lewy górny róg) lub `Database → New Database Connection`
2. W oknie wyboru bazy danych wyszukaj **SQLite** i kliknij `Next`
3. W polu **Path** wpisz ścieżkę do pliku bazy:
   ```
   C:\Repozytoria\flask-app-form\instance\ems.db
   ```
   lub kliknij `Open` i nawiguj do tego pliku ręcznie
4. Kliknij **Test Connection** — przy pierwszym uruchomieniu DBeaver może zapytać o pobranie sterownika SQLite, zaakceptuj (`Download`)
5. Kliknij `Finish`

### Przeglądanie tabel

Po podłączeniu w panelu po lewej stronie:
```
flask-app-form\instance\ems.db
  └── main
       ├── Tables
       │    ├── users          ← konta użytkowników
       │    └── learning_effects  ← 13 efektów uczenia się
```

Kliknij dwukrotnie tabelę → zakładka `Data` pokazuje rekordy.

### Przydatne zapytania SQL w DBeaver

Otwórz SQL Editor (`SQL Editor → Open SQL Script` lub `F3`):

```sql
-- Wszyscy użytkownicy
SELECT id, email, first_name, last_name, role, is_active FROM users;

-- Tylko aktywne konta
SELECT email, role FROM users WHERE is_active = 1;

-- Efekty uczenia się
SELECT nr, substr(opis, 1, 80) || '...' AS skrot FROM learning_effects ORDER BY nr;

-- Zmiana roli użytkownika (przykład)
UPDATE users SET role = 'admin' WHERE email = 'student@student.ans-elblag.pl';
```

> **Uwaga**: Dane formularzy (Zał. 1–9) są przechowywane w pliku JSON, nie w bazie:
> `C:\Repozytoria\flask-app-form\data\studenci.json`
> Możesz go otworzyć w VS Code lub dowolnym edytorze tekstu.

---

## Architektura projektu

```
flask-app-form/
├── app.py                  # Główna aplikacja – 50+ tras, logika formularzy i workflow
├── auth.py                 # Logowanie/wylogowanie, Flask-Login setup
├── models.py               # Modele SQLAlchemy (User, LearningEffect)
├── config.py               # Konfiguracja z .env
├── seed.py                 # Skrypt seedujący: użytkownicy (realne dane PL), efekty, formularze testowe
├── generate_pdf.py         # Generowanie PDF przez WeasyPrint (aktywne)
├── generate_pdf_latex.py   # Generowanie PDF przez xelatex/MiKTeX (gotowe, wymaga instalacji MiKTeX)
├── generate_docx.py        # Generowanie DOCX (legacy, nieużywane w interfejsie)
│
├── templates/
│   ├── base.html           # Główny layout: awatar z inicjałami, karta użytkownika w sidebarze
│   ├── login.html          # Strona logowania (5 szybkich przycisków)
│   ├── index.html          # Dashboard – lista studentów / panel studenta
│   ├── podglad.html        # Widok studenta: workflow, statusy, przyciski admin
│   ├── regulamin.html      # Regulamin praktyk
│   ├── zal1.html–zal9.html # Formularze wejściowe (edytowalne)
│   ├── print/              # Szablony druku HTML (WeasyPrint)
│   └── latex/              # Szablony LaTeX (.tex.j2) – wszystkie 13 formularzy + base.tex
│
├── static/
│   └── css/base.css        # Cały arkusz stylów (~1300 linii)
│
├── data/
│   └── studenci.json       # Magazyn danych formularzy (JSON)
│
├── instance/
│   └── ems.db              # Baza SQLite (tworzona automatycznie)
│
└── documentation/          # Dokumentacja PDF i diagramy
```

### Przepływ danych

```
Formularz HTML → app.py route → walidacja → studenci.json
                                           ↓
                            Podgląd studenta ← load_data()
                                           ↓
                            Pobierz PDF ← generate_pdf.py (WeasyPrint)
                                       ← generate_pdf_latex.py (xelatex) [po instalacji MiKTeX]
```

### Status dokumentu (_status w JSON)

Każdy rekord w studenci.json ma pole `_status`:
```
draft     → Szkic (domyślny, można edytować)
pending   → Oczekuje (wysłany do zatwierdzenia, zablokowany do edycji)
approved  → Zatwierdzone (zaakceptowany przez recenzenta)
rejected  → Odrzucono (recenzent odrzucił z komentarzem, można poprawić i wysłać ponownie)
```

Pola meta: `_rejection_comment`, `_rejection_by` – ustawiane przy odrzuceniu.

### Dwa magazyny danych

| Co | Gdzie | Format |
|----|-------|--------|
| Konta użytkowników | `instance/ems.db` | SQLite (SQLAlchemy) |
| Dane formularzy Zał. 1–9 | `data/studenci.json` | JSON, klucz = nr albumu |

---

## Trasy (routes)

| Ścieżka | Metoda | Funkcja | Opis |
|---------|--------|---------|------|
| `/login` | GET/POST | `login_page` | Logowanie |
| `/auth/logout` | GET | `logout` | Wylogowanie |
| `/` | GET | `index` | Dashboard |
| `/regulamin` | GET | `regulamin` | Regulamin |
| `/student/<nr>` | GET | `student_detail` | Profil studenta |
| `/student/<nr>/usun` | POST | `student_delete` | Usuń studenta |
| `/admin/wypelnij/<nr>` | POST | `admin_fill_test_data` | Wypełnij testowymi danymi (tylko admin) |
| `/student/<nr>/<zal>/pobierz` | GET | `pobierz_pdf` | Pobierz PDF (WeasyPrint) |
| `/student/<nr>/<zal>/drukuj` | GET | `drukuj` | Widok do druku (HTML) |
| `/student/<nr>/<zal>/wyslij` | POST | `wyslij_do_oceny` | Wyślij dokument do zatwierdzenia |
| `/student/<nr>/<zal>/zatwierdz` | POST | `zatwierdz_dokument` | Zatwierdź dokument |
| `/student/<nr>/<zal>/odrzuc` | POST | `odrzuc_dokument` | Odrzuć dokument z komentarzem |
| `/zal[1-9]` | GET/POST | `zal[1-9]` | Utwórz formularz |
| `/zal[1-9]/<nr>/edytuj` | GET/POST | `zal[1-9]_edit` | Edytuj formularz |
| `/zal[1-9]/<nr>/usun` | POST | `zal[1-9]_delete` | Usuń formularz |

---

## Stałe i helpery w app.py

- **`SPECIALTIES`** – 3 specjalności: ASiSK, PBDiOU, M3D
- **`ATTACHMENTS`** – metadane 13 załączników (klucz, numer, tytuł)
- **`SURVEY_QUESTIONS`** – 14 pytań ankietowych (Zał. 5)
- **`SURVEY_OPTIONS`** – 5 opcji Likerta (zdecydowanie tak … zdecydowanie nie)
- **`ROLE_FORM_ACCESS`** – dict: rola → set kluczy formularzy
- **`DOCUMENT_WORKFLOW`** – dict: klucz → {reviewer, reviewer_label}
- **`STATUS_LABELS`** – dict: status → (etykieta, css_class)

### Helpery

```python
build_prefill(nr='')     # zwraca dict pre-fill na podstawie roli użytkownika:
                         #   student → imie_nazwisko + nr_albumu z profilu
                         #   uopz → uczelniany_opiekun / podpis_uczelniany / podpis_uopz
                         #   zopz → zakladowy_opiekun_nazwisko / opiekun_imie_nazwisko
                         #   inne → {"nr_albumu": nr} lub None

_build_test_data(nr_albumu, effects)  # zwraca dict z pełnymi danymi testowymi dla 13 formularzy
                                      # (Techno Systems Gdańsk, kwiecień–maj bieżącego roku)
```

Wszystkie trasy GET tworzące formularz używają `data=build_prefill(nr)` zamiast `{"nr_albumu": nr} if nr else None`.

---

## Model bazy danych

### `users`
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | Integer PK | |
| email | Text UNIQUE | Login |
| password_hash | Text | Bcrypt hash |
| first_name, last_name | Text | Imię i nazwisko |
| role | Text | `student` / `uopz` / `zopz` / `dziekanat` / `admin` |
| album_number | Text | Numer albumu (studenci) |
| is_active | Integer | 1 = aktywny, 0 = zablokowany |
| email_verified | Integer | 0/1 |
| last_login_at | DateTime | Ostatnie logowanie |
| failed_login_attempts | Integer | Licznik błędów (przygotowane) |
| locked_until | DateTime | Blokada konta (przygotowane) |
| avatar_url | Text | URL awataru (przygotowane) |

### `learning_effects`
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | Integer PK | |
| nr | Integer UNIQUE | Numer efektu (1–13) |
| opis | Text | Pełny opis efektu uczenia się |

---

## System ról (RBAC)

### 5 ról i ich uprawnienia

| Rola | Kod | Tworzy/edytuje formularze | Widzi |
|------|-----|--------------------------|-------|
| **Student** | `student` | Zał. 1, 2a, 4b, 5, 6, 7, 7a | Tylko swoje dokumenty (filtr po nr albumu) |
| **Opiekun Uczelniany** | `uopz` | Zał. 2, 4a | Wszystkich studentów |
| **Opiekun Zakładowy** | `zopz` | Zał. 3, 4, 9 | Wszystkich studentów |
| **Dziekanat** | `dziekanat` | Zał. 8 | Wszystkich studentów + może usuwać rekordy |
| **Administrator** | `admin` | Wszystkie formularze | Wszystko |

### Szczegółowy zakres ról

**Student:**
- Widzi wyłącznie swój profil (filtrowany po `current_user.album_number`)
- Dashboard zawiera panel przewodnika krok-po-kroku (STUDENT_WORKFLOW)
- Numer albumu jest blokowany w formularzach — zawsze pobierany z profilu
- Nie może usuwać rekordów studenta

**UOPZ (Opiekun Uczelniany):**
- Zał. 2 — Program praktyki zawodowej (uzgodniony z zakładem)
- Zał. 4a — Merytoryczna ocena wniosku studenta (dotyczy Zał. 4b)
- Widzi pełną listę studentów (read-only dla pozostałych formularzy)

**ZOPZ (Opiekun Zakładowy):**
- Zał. 3 — Karta praktyki zawodowej (ocena zakładu)
- Zał. 4 — Potwierdzenie efektów uczenia się (13 efektów, ocena zakładu)
- Zał. 9 — Oświadczenie instytucji
- Widzi pełną listę studentów (read-only dla pozostałych formularzy)

**Dziekanat:**
- Zał. 8 — Protokół zaliczenia praktyki (komisja, ocena końcowa)
- Może usuwać rekordy studentów
- Widzi pełną listę wszystkich studentów

**Admin:**
- Dostęp do wszystkich formularzy wszystkich studentów
- Może usuwać rekordy

### Kolejność wypełniania dokumentów (student)

```
Krok 1 [przed praktyką]  → Zał. 1  — Porozumienie z zakładem pracy
Krok 2 [przed praktyką]  → Zał. 2a — Program i harmonogram praktyki
Krok 3 [opcjonalnie]     → Zał. 4b — Wniosek o zaliczenie efektów
Krok 4 [w trakcie]       → Zał. 6  — Dziennik praktyki (codziennie)
Krok 5 [po praktyce]     → Zał. 7  — Sprawozdanie z praktyki
Krok 6 [po praktyce]     → Zał. 5  — Kwestionariusz ankiety
```

Równolegle (opiekunowie):
```
ZOPZ:      Zał. 3, 4, 9
UOPZ:      Zał. 2, 4a
Dziekanat: Zał. 8 (na końcu)
```

### Kluczowe helpery w app.py

```python
ROLE_FORM_ACCESS      # dict: rola → set kluczy formularzy
DOCUMENT_WORKFLOW     # dict: klucz → {reviewer, reviewer_label}
STATUS_LABELS         # dict: status → (etykieta, css_class)
can_edit_form(key)    # bool: czy current_user może edytować ten formularz
guard_form(key)       # redirect lub None: blokada dla nieuprawnionych
student_nr(value)     # dla studenta zawsze zwraca własny nr albumu
get_doc_status(nr, k) # zwraca status dokumentu z JSON
can_edit_now(nr, k)   # bool: czy dokument jest teraz edytowalny (nie pending/approved)
```

### Kto zatwierdza każdy dokument (DOCUMENT_WORKFLOW)

| Dokument | Recenzent |
|----------|-----------|
| Zał. 1 | UOPZ |
| Zał. 2a | ZOPZ |
| Zał. 3 | UOPZ |
| Zał. 4b | UOPZ |
| Zał. 6 | ZOPZ |
| Zał. 7a | ZOPZ |
| Zał. 2, 4, 4a, 5, 7, 8, 9 | — (bez recenzenta) |

---

## Co jest zaimplementowane vs. zaplanowane

### Zaimplementowane
- Logowanie email/hasło przez Flask-Login (5 szybkich przycisków na stronie logowania)
- CRUD dla wszystkich 9 załączników (+ warianty 2a, 4a, 4b, 7a)
- RBAC – 5 ról z pełną kontrolą dostępu (guard_form, student_nr, ROLE_FORM_ACCESS)
- Dashboard studenta z przewodnikiem krok-po-kroku i statusem każdego kroku
- Dashboard pracowniczy z listą studentów i sekcją oczekujących dokumentów
- Workflow zatwierdzania: draft → pending → approved / rejected (→ draft)
- Generowanie PDF przez WeasyPrint (generate_pdf.py)
- Widoki do druku HTML (templates/print/)
- Regulamin
- **Awatar z inicjałami** (AK, IM, ZO…) w nagłówku strony i dolnej karcie sidebaru; kolor koła zależy od roli
- **Etykieta roli** wyświetlana pod imieniem i nazwiskiem (Opiekun Uczelniany, Dziekanat, itp.)
- **Auto-wypełnianie formularzy** – `build_prefill()` wstawia imię/nazwisko studenta i dane opiekuna z profilu użytkownika
- **Dane testowe via seed.py** – 5 kont z realnymi polskimi danymi; `seed_forms()` tworzy kompletną dokumentację studenta 21001 (Techno Systems Gdańsk)
- **Przycisk "Wypełnij danymi testowymi"** w podglad.html dla admina – wypełnia wszystkie 13 formularzy jednym kliknięciem (`/admin/wypelnij/<nr>`)
- **Szablony LaTeX** dla wszystkich 13 formularzy (`templates/latex/*.tex.j2` + `base.tex`) oraz `generate_pdf_latex.py` z xelatex – gotowe, wymagają instalacji MiKTeX

### Zaplanowane / częściowo gotowe
- Logowanie OAuth przez Microsoft (pola w modelu, .env, brak tras)
- Blokowanie konta po błędach logowania (pola w modelu, brak logiki)
- Weryfikacja e-mail (pole w modelu, brak mechanizmu)
- Panel administracyjny użytkowników
- Przełączenie generowania PDF z WeasyPrint na LaTeX (po zainstalowaniu MiKTeX: podmień `generate_pdf` na `generate_pdf_latex` w trasie `pobierz_pdf`)

---

## Generowanie PDF – LaTeX (xelatex)

Szablony LaTeX w `templates/latex/` są gotowe. Do uruchomienia potrzebny jest MiKTeX.

### Instalacja MiKTeX (Windows)

```bash
winget install MiKTeX.MiKTeX
```

Lub pobierz z: https://miktex.org/download

Po zainstalowaniu MiKTeX automatycznie pobiera brakujące pakiety przy pierwszym uruchomieniu.

### Przełączenie generowania PDF z WeasyPrint na LaTeX

W `app.py`, trasa `pobierz_pdf`, zamień:
```python
from generate_pdf import generate_pdf
# ...
buf = generate_pdf(app, zal_key, ctx)
```
na:
```python
from generate_pdf_latex import generate_pdf_latex
# ...
buf = generate_pdf_latex(zal_key, ctx)
```

### Architektura LaTeX

- `templates/latex/base.tex` – wspólna preambuła (importowana przez `\input{base}` w każdym szablonie)
  - Czcionka Calibri (Windows) z fallback na TeX Gyre Termes
  - Format A4, marginesy 2cm / 2.5cm
  - Pomocniki: `\letterhead{nr}`, `\pfield{label}{value}`, `\psig{label}{value}`, `\doctitle`, itp.
- `templates/latex/zal*.tex.j2` – szablony Jinja2 dla każdego formularza
- Delimitery Jinja2 w szablonach `.tex.j2` (bezpieczne dla LaTeXa):
  - `(( zmienna ))` zamiast `{{ }}`
  - `((*  *))` zamiast `{% %}`
  - `((# #))` zamiast `{# #}`
- `generate_pdf_latex.py` – uruchamia xelatex dwukrotnie, zwraca `BytesIO`

---

## Zmienne środowiskowe (.env)

```env
SECRET_KEY=twoj-sekretny-klucz-min-32-znaki
DATABASE_URL=sqlite:///ems.db
```

Zmienne OAuth (opcjonalne, nieużywane):
```env
MS_CLIENT_ID=
MS_CLIENT_SECRET=
MS_TENANT_ID=
MS_REDIRECT_URI=
```

---

## Uruchamianie w środowisku deweloperskim

Flask uruchamia się w trybie debug automatycznie (`FLASK_DEBUG=true` domyślnie). Zmiany w plikach `.py` powodują automatyczny restart. Zmiany w szablonach HTML działają od razu.

```bash
# Pełna sekwencja od zera (Windows PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed.py
python app.py
```

### Resetowanie danych formularzy

Usuń plik JSON żeby wyczyścić wszystkie dane studentów:
```bash
del data\studenci.json
```

### Resetowanie bazy danych

```bash
del instance\ems.db
python seed.py   # odtworzy tabelę i użytkowników
```

---

## Najczęstsze problemy

| Problem | Rozwiązanie |
|---------|-------------|
| `ModuleNotFoundError` | Aktywuj venv: `.\venv\Scripts\Activate.ps1` |
| „Brak danych dla tego numeru albumu" | Numer albumu nie istnieje w studenci.json |
| Puste formularze po logowaniu | Uruchom `python seed.py` aby załadować efekty uczenia |
| Port 5000 zajęty | Zmień w .env: `FLASK_PORT=5001` |
| Baza nie istnieje | Uruchom `python seed.py` — tworzy ems.db |
