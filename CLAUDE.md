# CLAUDE.md - System Rozliczania Praktyk Zawodowych

## Cel projektu

Aplikacja Flask obsługuje cyfrowy obieg dokumentacji praktyk zawodowych ANS
w Elblągu. Role systemowe: student, UOPZ, ZOPZ, dziekanat i administrator.

## Uruchomienie deweloperskie

Wymagany jest Docker Desktop.

```powershell
Copy-Item .env.example .env
# Uzupełnij SECRET_KEY, hasła MariaDB i hasła kont seed.
docker-compose up -d --build
docker-compose run --rm flask flask --app app db upgrade
docker-compose run --rm flask python -m core.seed
```

Aplikacja: `http://localhost:5000`.

Tryb `DEBUG_LOGIN_BUTTONS=true` działa wyłącznie razem z `FLASK_DEBUG=true`.
Nie wolno włączać go w środowisku produkcyjnym.

## Testy

```powershell
docker-compose run --rm flask python -m unittest discover -s tests -v
docker-compose run --rm flask flask --app app db check
docker-compose -f docker-compose.e2e.yml up --build `
  --abort-on-container-exit --exit-code-from e2e e2e
docker-compose -f docker-compose.e2e.yml down --volumes
```

Aktualny zestaw: 79 testów jednostkowych i integracyjnych oraz 12 scenariuszy
Playwright. GitHub Actions uruchamia oba zestawy osobno.

## Architektura

```text
app.py                         fabryka create_app i rejestracja rozszerzeń
core/web.py                    implementacje tras podzielone na 4 Blueprinty
core/auth.py                   sesje, hasła, Microsoft Entra ID i Google OAuth
core/admin.py                  panel, import CSV i raporty
core/workflow.py               autorytatywny FSM dokumentów w MariaDB
core/internships.py            lata akademickie i części praktyki
core/grades.py                 obliczanie i historia oceny końcowej
core/documents.py              wersjonowane zatwierdzone PDF-y
core/retention.py              ZIP, retencja, anonimizacja i usuwanie źródeł
core/store.py                  punktowy zapis formularzy w MongoDB
core/health.py                 liveness i readiness
core/observability.py          Prometheus i logi żądań
core/models.py                 modele SQLAlchemy
migrations/                    wersjonowany schemat Alembic
```

Blueprinty:

- `auth` - logowanie, OAuth i wylogowanie;
- `admin` - panel administracyjny;
- `health` i `metrics` - operacje produkcyjne;
- `main` - dashboard, profil i części praktyki;
- `documents` - workflow, recenzja, PDF i archiwa;
- `forms` - formularze Zał. 1-9;
- `operations` - przydziały, konfiguracja i dane testowe.

`app.py` ma pozostać mały. Nowej logiki biznesowej nie należy dodawać do
fabryki aplikacji. `core/web.py` jest nadal dużym modułem i przy kolejnych
zmianach trasy należy przenosić z niego do fizycznych modułów Blueprintów.

## Dane

MariaDB przechowuje użytkowników, przydziały, części praktyki, workflow,
oceny, historię PDF, archiwa, audyt i konfigurację. MongoDB przechowuje
wyłącznie treść formularzy i ich rewizje.

Status dokumentu jest autorytatywny wyłącznie w `document_workflow`:

```text
draft -> pending -> approved
                  -> rejected -> pending
```

Pola `_status` i inne metadane workflow nie są zapisywane w nowych dokumentach
MongoDB.

## Reguły biznesowe

- Student może mieć wiele części praktyki w jednym roku akademickim.
- Anulowane części nie wchodzą do rocznych sum godzin i dni.
- Dziennik dopuszcza 1-8 godzin dziennie, maksymalnie 120 dni i 960 godzin.
- Ocena końcowa: `K = 0,4E + 0,1S + 0,2U + 0,3Z`.
- Ocena wymaga kompletnych składników i zatwierdzonego dziennika.
- PDF powstaje tylko dla dokładnej zatwierdzonej rewizji formularza.
- Usunięcie studenta oznacza najpierw kompletną archiwizację.
- Anonimizacja usuwa dane źródłowe dopiero po upływie retencji.
- UOPZ i ZOPZ widzą tylko jawnie przypisane praktyki lub ich części.

## Migracje

Każda zmiana modelu wymaga migracji:

```powershell
docker-compose run --rm flask flask --app app db migrate -m "Opis"
docker-compose run --rm flask flask --app app db upgrade
docker-compose run --rm flask flask --app app db check
```

Nie używać `db.create_all()` przy starcie aplikacji. `stamp` jest przeznaczony
wyłącznie do jednorazowego oznaczenia istniejącej bazy podczas wdrożenia
Alembic.

## Microsoft Entra ID

Produkcja używa aplikacji single-tenant. Wymagane zmienne:

```text
MS_CLIENT_ID
MS_CLIENT_SECRET
MS_TENANT_ID
MS_REDIRECT_URI
MS_ALLOWED_EMAIL_DOMAINS
MS_STAFF_EMAIL_DOMAIN
```

Student musi istnieć wcześniej w `users`. Pracownik z App Role `UOPZ`,
`Dziekanat` albo `Admin` jest tworzony lub synchronizowany przy logowaniu.
Pierwsze logowanie wiąże konto z niezmiennym identyfikatorem
`microsoft_tenant_id + microsoft_object_id`. Walidowane są tenant, issuer,
domena adresu oraz jednoznaczność roli pracownika.

ZOPZ jest zapraszany jednorazowym linkiem do praktyki lub jej części.
Konfiguracja opcjonalnej wysyłki: `SMTP_*`, `MAIL_FROM`, `PUBLIC_BASE_URL`.

## Produkcja

Pełna instrukcja: `documentation/WDROZENIE_PRODUKCYJNE.md`.

`docker-compose.prod.yml` zapewnia:

- Nginx z HTTPS i HSTS;
- brak publicznych portów MariaDB i MongoDB;
- użytkownika aplikacyjnego MongoDB;
- proces Flask bez uprawnień root;
- Prometheus, readiness i reguły alertów;
- cykliczne zadanie retencji;
- trwały wolumen `/app/data`.

Backup:

```sh
ENV_FILE=.env.production deploy/backup.sh
deploy/verify-restore.sh backups/TIMESTAMP
```

Backup obejmuje MariaDB, MongoDB, uploady, PDF-y i archiwa.
