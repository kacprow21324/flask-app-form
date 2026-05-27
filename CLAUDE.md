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
# 1. Wejdź do folderu projektu
cd C:\Users\Kacper\Desktop\flask-app-form

# 2. Utwórz wirtualne środowisko
python -m venv venv

# 3. Aktywuj środowisko
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat

# 4. Zainstaluj zależności
pip install -r requirements.txt

# 5. (Opcjonalnie) Skopiuj plik środowiska
copy .env.example .env

# 6. Wypełnij bazę danych
venv\Scripts\python seed.py

# 7. Uruchom aplikację
venv\Scripts\python app.py
```

> **Ważne:** Zawsze uruchamiaj `seed.py` i `app.py` przez `venv\Scripts\python`, nie przez systemowego Pythona — inaczej braknie modułów (flask_login, itp.).

Aplikacja będzie dostępna pod: **http://127.0.0.1:5000**

### Uruchomienie przez Docker

```bash
docker compose up --build
```

Aplikacja dostępna pod: **http://localhost:5000**

### Konta testowe (seed.py tworzy je automatycznie)

| E-mail | Hasło | Rola | Nr albumu |
|--------|-------|------|-----------|
| student@student.ans-elblag.pl | Student123! | student | 21001 (Aleksandra Kowalska – ASiSK, Techno Systems Gdańsk) |
| student2@student.ans-elblag.pl | Student123! | student | 21002 (Marek Nowak – PBDiOU, DataSoft Olsztyn) |
| student3@student.ans-elblag.pl | Student123! | student | 21003 (Katarzyna Wróbel – M3D, MediScan Olsztyn) |
| opiekun@ans-elblag.pl | Opiekun123! | uopz | — (dr Irena Malinowska) |
| zopz@firma.pl | Zopz123! | zopz | — (Zbigniew Ostrowski) |
| dziekanat@ans-elblag.pl | Dziekanat123! | dziekanat | — (Dorota Kamińska) |
| admin@ans-elblag.pl | Admin123! | admin | — (Adam Wiśniewski) |

Na stronie logowania dostępne są przyciski „Zaloguj jako..." do szybkiego logowania bez wpisywania danych.

### Stan danych testowych (21001 – Aleksandra Kowalska)

Dane odzwierciedlają realistyczny stan praktyki w trakcie realizacji:

| Załącznik | Status | Opis |
|-----------|--------|------|
| Zał. 1 | ✅ Zatwierdzone | Porozumienie podpisane przed praktyką |
| Zał. 2 | ✅ Zatwierdzone | Program praktyki uzgodniony przez UOPZ |
| Zał. 2a | ✅ Zatwierdzone | Harmonogram zatwierdzony przez ZOPZ |
| Zał. 3 | ⏳ Oczekuje | Karta wypełniona przez ZOPZ, czeka na UOPZ |
| Zał. 4 | ✅ Zatwierdzone | Efekty potwierdzone przez ZOPZ |
| Zał. 4a | ✅ Zatwierdzone | Ocena wniosku studenta przez UOPZ |
| Zał. 4b | ✅ Zatwierdzone | Wniosek studenta zatwierdzony |
| Zał. 5 | 📝 Szkic | Ankieta jeszcze nie wysłana |
| Zał. 6 | ⏳ Oczekuje | Dziennik wysłany do ZOPZ |
| Zał. 7 | ❌ Odrzucono | Sprawozdanie odrzucone przez UOPZ z komentarzami do pól |
| Zał. 7a | 📝 Szkic | Wariant niestacjonarny – nie dotyczy |
| Zał. 8 | 📝 Szkic | Protokół dziekanatu – na końcu procesu |
| Zał. 9 | ✅ Zatwierdzone | Oświadczenie instytucji podpisane przed praktyką |

---

## Resetowanie danych testowych

```bash
# Tylko dane formularzy (szybsze, DB pozostaje):
rm -f data/studenci.json
venv\Scripts\python seed.py

# Pełny reset (DB + formularze) – wymaga zatrzymania serwera:
del instance\ems.db
del data\studenci.json
venv\Scripts\python seed.py
```

---

## Konfiguracja DBeaver (przeglądanie bazy danych)

DBeaver to darmowe narzędzie do przeglądania i edytowania baz danych z interfejsem graficznym.

### Instalacja DBeaver

1. Pobierz **DBeaver Community** (bezpłatna wersja) ze strony: https://dbeaver.io/download/
2. Zainstaluj jak standardowy program.

### Podłączenie bazy SQLite projektu

Baza danych tworzy się automatycznie przy pierwszym uruchomieniu:
```
C:\Users\Kacper\Desktop\flask-app-form\instance\ems.db
```

Kroki konfiguracji w DBeaver:

1. **Otwórz DBeaver** → `Database → New Database Connection`
2. Wyszukaj **SQLite** → `Next`
3. W polu **Path** podaj ścieżkę do pliku lub kliknij `Open` i nawiguj
4. **Test Connection** → zaakceptuj pobranie sterownika (`Download`) → `Finish`

### Przydatne zapytania SQL

```sql
-- Wszyscy użytkownicy
SELECT id, email, first_name, last_name, role, is_active FROM users;

-- Zmiana roli użytkownika
UPDATE users SET role = 'admin' WHERE email = 'student@student.ans-elblag.pl';

-- Efekty uczenia się
SELECT nr, substr(opis, 1, 80) || '...' AS skrot FROM learning_effects ORDER BY nr;
```

> **Uwaga:** Dane formularzy (Zał. 1–9) są w `data/studenci.json`, nie w bazie SQLite.

---

## Architektura projektu

```
flask-app-form/
├── app.py                  # Główna aplikacja – trasy, logika formularzy, workflow
├── auth.py                 # Logowanie/wylogowanie, Flask-Login setup
├── models.py               # Modele SQLAlchemy (User, LearningEffect)
├── config.py               # Konfiguracja z .env
├── seed.py                 # Seeduje: 7 użytkowników, 13 efektów, formularze dla 3 studentów
├── generate_pdf.py         # Generowanie PDF przez WeasyPrint (aktywne)
├── generate_pdf_latex.py   # Generowanie PDF przez xelatex/MiKTeX (gotowe, wymaga MiKTeX)
├── generate_docx.py        # Generowanie DOCX (legacy, nieużywane w UI)
│
├── templates/
│   ├── base.html           # Layout: awatar inicjały, sidebar, readonly-banner
│   ├── login.html          # Logowanie z 5 szybkimi przyciskami (Student 1, 2, ...)
│   ├── index.html          # Dashboard – lista studentów / panel studenta
│   ├── podglad.html        # Profil studenta: karty załączników, workflow, odrzucanie z uwagami
│   ├── regulamin.html      # Regulamin praktyk
│   ├── zal1.html–zal9.html # Formularze wejściowe (edytowalne)
│   ├── print/              # Szablony druku HTML (WeasyPrint)
│   └── latex/              # Szablony LaTeX (.tex.j2) – 13 formularzy + base.tex
│
├── static/
│   └── css/base.css        # Cały arkusz stylów (~1350 linii)
│
├── data/
│   └── studenci.json       # Magazyn danych formularzy (JSON, klucz = nr albumu)
│
├── instance/
│   └── ems.db              # Baza SQLite (tworzona automatycznie)
│
└── documentation/          # Dokumentacja PDF i diagramy ERD
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

```
draft     → Szkic (domyślny, można edytować)
pending   → Oczekuje (wysłany do zatwierdzenia, zablokowany do edycji)
approved  → Zatwierdzone (zaakceptowany przez recenzenta)
rejected  → Odrzucono (recenzent odrzucił z komentarzem, można poprawić i wysłać ponownie)
```

Pola meta przy odrzuceniu: `_rejection_comment`, `_rejection_by`, `_field_comments` (lista `{field, note}`).

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
| `/student/<nr>/<zal>/formularz` | GET | `formularz_podglad` | Podgląd formularza (readonly) |
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
- **`FORM_FIELDS`** – dict: klucz → lista polskich nazw pól (dla dropdown w recenzji)

### Helpery

```python
build_prefill(nr='')      # pre-fill formularza na podstawie roli: student→imię/nr, uopz→opiekun, itp.
can_edit_form(key)        # bool: czy current_user może edytować ten formularz (ROLE_FORM_ACCESS)
guard_form(key)           # redirect lub None: blokada dla nieuprawnionych ról
guard_edit(nr, key)       # redirect lub None: blokada gdy dokument pending/approved (admin pomija)
_persist(nr, key, record) # zapisuje rekord do JSON; blokuje zapis gdy pending/approved (nie-admin)
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

## System ról (RBAC)

| Rola | Kod | Tworzy/edytuje formularze | Widzi |
|------|-----|--------------------------|-------|
| **Student** | `student` | Zał. 1, 2a, 4b, 5, 6, 7, 7a | Tylko swoje dokumenty |
| **Opiekun Uczelniany** | `uopz` | Zał. 2, 4a | Wszystkich studentów |
| **Opiekun Zakładowy** | `zopz` | Zał. 3, 4, 9 | Wszystkich studentów |
| **Dziekanat** | `dziekanat` | Zał. 8 | Wszystkich + może usuwać |
| **Administrator** | `admin` | Wszystkie formularze | Wszystko + tryb nadpisania |

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
| album_number | Text | Numer albumu (tylko studenci) |
| is_active | Integer | 1 = aktywny, 0 = zablokowany |
| email_verified | Integer | 0/1 |
| last_login_at | DateTime | Ostatnie logowanie |
| failed_login_attempts | Integer | Licznik błędnych prób (przygotowane) |
| locked_until | DateTime | Blokada konta (przygotowane) |
| avatar_url | Text | URL awataru (przygotowane) |

### `learning_effects`
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | Integer PK | |
| nr | Integer UNIQUE | Numer efektu (1–13) |
| opis | Text | Pełny opis efektu uczenia się |

---

## Co jest zaimplementowane

- **Logowanie** email/hasło przez Flask-Login; 5+2 szybkich przycisków na stronie logowania
- **CRUD** dla wszystkich 9 załączników (+ warianty 2a, 4a, 4b, 7a) – łącznie 13 formularzy
- **RBAC** – 5 ról z pełną kontrolą dostępu (`guard_form`, `guard_edit`, `ROLE_FORM_ACCESS`)
- **Blokada edycji** – dokumenty `pending`/`approved` są zablokowane; admin może zawsze edytować
- **Workflow zatwierdzania** – draft → pending → approved / rejected → draft
- **Odrzucanie z uwagami** – recenzent wybiera pola z dropdown i dopisuje co poprawić; uwagi widoczne studentowi
- **Podgląd formularza (readonly)** – przycisk „Przejrzyj" otwiera formularz w trybie tylko do odczytu bez modyfikowania 13 szablonów (JS overlay w base.html)
- **Dashboard studenta** z przewodnikiem krok-po-kroku i statusem każdego załącznika
- **Dashboard pracowniczy** z listą studentów i sekcją dokumentów oczekujących na zatwierdzenie
- **Generowanie PDF** przez WeasyPrint (`generate_pdf.py`) + widoki druku HTML (`templates/print/`)
- **Szablony LaTeX** dla wszystkich 13 formularzy (`templates/latex/`) + `generate_pdf_latex.py` – gotowe, wymagają MiKTeX
- **Awatar z inicjałami** (AK, IM…) w nagłówku i sidebarze; kolor zależy od roli
- **Auto-wypełnianie formularzy** – `build_prefill()` wstawia dane z profilu zalogowanego użytkownika
- **Dane testowe** – 7 kont (3 studenci × 3 specjalności × różne firmy), realistyczne statusy workflow
- **Przycisk admina „Wypełnij danymi testowymi"** – wypełnia wszystkie 13 formularzy jednym kliknięciem

---

## Co wymaga dokończenia / poprawy

- **Blokowanie konta po błędach logowania** – pola `failed_login_attempts` i `locked_until` są w modelu, brak logiki w `auth.py`
- **Weryfikacja e-mail** – pole `email_verified` w modelu, brak mechanizmu wysyłania maili
- **Logowanie OAuth przez Microsoft** – pola w modelu i `.env`, brak tras (msal lub authlib)
- **Panel administracyjny użytkowników** – brak strony do zarządzania kontami (zmiana roli, blokada, reset hasła)
- **Przełączenie PDF na LaTeX** – po zainstalowaniu MiKTeX podmień w `app.py` trasie `pobierz_pdf`: `generate_pdf` → `generate_pdf_latex`
- **Powiadomienia e-mail** – student powinien dostać e-mail gdy dokument zostanie zatwierdzony lub odrzucony
- **Walidacja formularzy** – część pól nie ma walidacji po stronie serwera (np. format daty, numery ocen)

---

## Co można dodać w przyszłości

- **Eksport do Excel / CSV** – zestawienie wszystkich studentów z ocenami do pobrania przez dziekanat
- **Wyszukiwarka i filtry** na liście studentów (po nazwisku, specjalności, statusie dokumentów)
- **Historia zmian dokumentu** – kto i kiedy zmienił status, lista poprzednich wersji
- **Podpis elektroniczny** – integracja z ePUAP lub podpisem kwalifikowanym dla oficjalnych dokumentów
- **Masowe operacje** – zatwierdzanie/odrzucanie wielu dokumentów naraz przez opiekuna
- **Strona profilu użytkownika** – zmiana hasła, danych kontaktowych, awataru
- **Powiadomienia w aplikacji** – bell icon z listą zdarzeń (dokument zatwierdzony, odrzucony, wysłany)
- **Wieloletnia archiwizacja** – rok akademicki jako dodatkowy wymiar w JSON / przeniesienie do bazy
- **Import danych z USOS / Excel** – wgranie listy studentów zamiast ręcznego tworzenia kont
- **Mobilny widok** – layout jest responsywny, ale formularze z wieloma polami mogą być trudne na telefonie
- **Testy automatyczne** – brak jakichkolwiek testów jednostkowych/integracyjnych

---

## Generowanie PDF – LaTeX (xelatex)

Szablony LaTeX w `templates/latex/` są gotowe. Do uruchomienia potrzebny jest MiKTeX.

```bash
winget install MiKTeX.MiKTeX
```

Lub pobierz z: https://miktex.org/download

### Przełączenie z WeasyPrint na LaTeX

W `app.py`, trasa `pobierz_pdf`:
```python
# Obecne (WeasyPrint):
buf = generate_pdf(app, zal_key, ctx)

# Po zainstalowaniu MiKTeX:
buf = generate_pdf_latex(zal_key, ctx)
```

Delimitery Jinja2 w szablonach `.tex.j2` (bezpieczne dla LaTeXa): `(( ))`, `((* *))`, `((# #))`.

---

## Zmienne środowiskowe (.env)

```env
SECRET_KEY=twoj-sekretny-klucz-min-32-znaki
DATABASE_URL=sqlite:///ems.db
```

---

## Najczęstsze problemy

| Problem | Rozwiązanie |
|---------|-------------|
| `ModuleNotFoundError` | Użyj `venv\Scripts\python` zamiast `python` |
| „Brak danych dla tego numeru albumu" | Uruchom `venv\Scripts\python seed.py` |
| Puste formularze / brak efektów | Uruchom seed — tworzy efekty uczenia się |
| Port 5000 zajęty | Zmień w `.env`: `FLASK_PORT=5001` |
| `ems.db` zablokowany przy usuwaniu | Zatrzymaj serwer (Ctrl+C), potem usuń plik |
