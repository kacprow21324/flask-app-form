# Plan naprawy i rozwoju aplikacji

Plan porządkuje prace według ryzyka. Każdy etap powinien być wdrażany i
testowany oddzielnie. Nowe funkcje biznesowe nie powinny być łączone w jednej
migracji z przebudową warstwy danych.

## Etap 1: bezpieczny zapis MongoDB

Status: zrealizowany.

Zakres:

- punktowy odczyt, zapis i usuwanie formularza;
- brak synchronizacji całej kolekcji podczas pojedynczego żądania;
- pole `revision` zwiększane atomowo przy zapisie;
- możliwość optimistic lockingu przez `expected_revision`;
- testy jednostkowe i integracyjne zapisu oraz konfliktu.

Kryterium odbioru:

- zapis formularza A nie zmienia formularza B;
- równoczesny zapis ze starą rewizją jest odrzucany;
- usunięcie formularza nie usuwa innych dokumentów.

## Etap 2: status dokumentu wyłącznie w MariaDB

Status: zrealizowany.

Zakres:

- odczyt statusu z `document_workflow`;
- usunięcie `_status` z nowych zapisów MongoDB;
- migracja istniejących statusów do MariaDB;
- skrypt kontroli rozbieżności przed usunięciem pól z MongoDB;
- decyzje recenzenta i komentarz odrzucenia zapisywane w jednej transakcji SQL;
- treść formularza, podpisy i komentarze do pól pozostają w MongoDB.

Kryterium odbioru:

- w MongoDB nie ma pola `_status`;
- kolejki, blokada edycji i dashboard korzystają z MariaDB;
- awaria zapisu MongoDB nie zmienia statusu workflow;
- skrypt zgodności raportuje zero rozbieżności.

## Etap 3: Flask-Migrate i Alembic

Status: zrealizowany.

Zakres:

- dodanie `Flask-Migrate`;
- utworzenie bazowej migracji odpowiadającej obecnej MariaDB;
- oznaczenie istniejącej bazy poleceniem `stamp`;
- usunięcie `db.create_all()` ze startu aplikacji;
- zastąpienie ręcznych `ALTER TABLE` wersjonowanymi migracjami;
- migracje uruchamiane jawnie przed startem nowej wersji.

Kryterium odbioru:

- pusta baza powstaje przez `flask db upgrade`;
- istniejąca baza może zostać bezpiecznie oznaczona wersją bazową;
- start aplikacji nie zmienia schematu;
- migracje działają drugi raz bez niekontrolowanych zmian.

Procedura zmiany schematu:

```powershell
docker-compose run --rm flask flask --app app db migrate -m "Opis zmiany"
docker-compose run --rm flask flask --app app db upgrade
docker-compose run --rm flask flask --app app db check
```

Na istniejącej bazie polecenie `stamp` wykonuje się tylko raz podczas
wprowadzania Alembic. Nowe środowiska zawsze używają `db upgrade`.

## Etap 4: testy automatyczne

Status: zrealizowany (79 testów jednostkowych i integracyjnych oraz 12 scenariuszy
przeglądarkowe Playwright).

Zakres:

- macierz dostępu wszystkich ról do tras i rekordów studentów;
- przejścia FSM i niedozwolone przejścia;
- walidatory formularzy i obliczanie ocen;
- integracja MariaDB i MongoDB;
- zapis równoległy oraz konflikty rewizji;
- generowanie i archiwizacja PDF;
- podstawowe scenariusze przeglądarkowe.

Zrealizowane:

- zapis punktowy MongoDB, rewizje i blokada konfliktów;
- migracja metadanych workflow;
- pełne przejścia FSM i zależności;
- walidatory danych;
- dostęp anonimowy, student, UOPZ i administrator;
- CSRF i nagłówki bezpieczeństwa;
- zapis pliku PDF oraz metadanych archiwum;
- migracja od pustej bazy i `db check`;
- workflow CI w GitHub Actions;
- izolowane środowisko E2E uruchamiane przez Docker Compose;
- scenariusze przeglądarkowe logowania, panelu administratora i części praktyki;
- osobny job Playwright w GitHub Actions.

Kryterium odbioru:

- testy uruchamiają się jednym poleceniem w Dockerze;
- CI blokuje wdrożenie po błędzie testu;
- krytyczne trasy mają test pozytywny i test odmowy dostępu.

## Etap 5: reguły procesu praktyk

Status: zrealizowany.

Zrealizowane:

- obsługa wielu części praktyki w jednym roku akademickim;
- osobne miejsce, terminy, opiekunowie, godziny i status każdej części;
- migracja istniejących praktyk do części początkowej bez utraty danych;
- roczny postęp sumowany z aktywnych części praktyki;
- wyliczanie oceny końcowej na serwerze według wzoru
  `K = 0,4E + 0,1S + 0,2U + 0,3Z`;
- walidacja kompletności ocen i wymóg zatwierdzonego dziennika;
- zapis składników, wyniku i historii przeliczeń w MariaDB;
- generowanie PDF wyłącznie z aktualnej, zatwierdzonej rewizji formularza;
- wersjonowanie PDF według rewizji źródła i wersji szablonu LaTeX;
- deduplikacja pobrań tej samej wersji oraz historia wersji w widoku studenta;
- suma kontrolna źródła i pliku, autor, czas zatwierdzenia i licznik pobrań;
- kompletny pakiet archiwalny ZIP: formularze, workflow, oceny, PDF i uploady;
- kontrola integralności pakietu i plików przed archiwizacją;
- konfigurowalna retencja, tryb tylko do odczytu po archiwizacji;
- anonimizacja konta i usunięcie danych źródłowych dopiero po retencji;
- jawne przypisywanie UOPZ i ZOPZ przez dziekanat/admina;
- brak automatycznego wyboru pierwszego opiekuna przy tworzeniu praktyki;
- widok postępu studenta: dokumenty, godziny i dni;
- godziny dziennika walidowane po stronie serwera (1-8 dziennie, do 120 dni
  i 960 godzin łącznie);
- dziekanat widzi wszystkich studentów, a opiekunowie tylko przypisanych;
- powiadomienia i wpis audytowy po zmianie przydziału.

- okresowe uruchamianie zadania anonimizacji przez usługę `retention`
  w konfiguracji produkcyjnej.

Kryterium odbioru:

- opiekun widzi tylko jawnie przypisane praktyki;
- reguły godzin i ocen nie zależą od JavaScriptu;
- każda wersja PDF ma źródło, sumę kontrolną i autora;
- operacja usunięcia ma zdefiniowany zakres danych i plików.

## Etap 6: podział aplikacji

Status: zrealizowany strukturalnie.

Zrealizowane:

- fabryka aplikacji `create_app`;
- `app.py` ograniczony do konfiguracji i rejestracji rozszerzeń;
- Blueprinty `auth`, `admin`, `health`, `metrics`, `main`, `documents`,
  `forms` i `operations`;
- zachowanie dotychczasowych adresów URL i nazw używanych przez szablony;
- serwisy workflow, praktyk, ocen, dokumentów, retencji i obserwowalności.

Zakres:

- repozytoria MariaDB i MongoDB;
- wspólne mechanizmy autoryzacji i obsługi błędów.

Dalsza poprawa utrzymywalności:

- fizyczny podział `core/web.py` na mniejsze moduły tras. Trasy są już
  rozdzielone logicznie między Blueprinty, ale implementacje pozostają w jednym
  module, aby ograniczyć ryzyko regresji przy migracji istniejących formularzy.

Kryterium odbioru:

- `app.py` zawiera głównie konfigurację aplikacji;
- trasy nie wykonują bezpośrednio złożonych operacji na obu bazach;
- istniejące adresy URL pozostają zgodne albo mają kontrolowaną migrację.

## Etap 7: funkcje administracyjne

Status: zrealizowany w zakresie podstawowego panelu; dalsza rozbudowa pozostaje
w backlogu.

Zrealizowane:

- centralny panel administracyjny użytkowników;
- aktywacja i dezaktywacja kont oraz reset hasła z unieważnieniem sesji;
- atomowy import studentów z CSV UTF-8 z walidacją całego pliku;
- wzór pliku importu;
- raport postępu CSV według roku akademickiego;
- przeglądarka ostatnich wpisów audytu i pakietów archiwalnych;

Pozostałe:

- przydziały opiekunów (zrealizowane);
- pełne filtrowanie i stronicowanie historii dokumentów i archiwum;
- terminy i alerty;
- raporty CSV/XLSX;
- przeglądarka `audit_logs`;
- panel aktywnych sesji;
- komplet dokumentów PDF/ZIP;
- komentarze do sekcji i autosave z rewizją.

## Etap 8: produkcja i dokumentacja

Status: zrealizowany w postaci gotowego pakietu wdrożeniowego.

Zrealizowane:

- osobny `docker-compose.prod.yml` bez publicznych portów baz;
- użytkownik aplikacyjny MongoDB i uwierzytelnienie;
- single-tenant Microsoft Entra ID z walidacją `tid`, `iss`, domeny i `oid`;
- Nginx, TLS, HSTS i obsługa zaufanych nagłówków reverse proxy;
- kontener aplikacji uruchamiany jako użytkownik bez uprawnień root;
- backup obu baz i `/app/data` oraz automatyczny test odtworzenia;
- liveness, readiness, Prometheus, reguły alertów i logi JSON;
- cykliczna retencja i anonimizacja.

Zakres:

- bazy dostępne tylko w sieci wewnętrznej Dockera;
- uwierzytelnienie MongoDB;
- logowanie kontami uczelnianymi przez Microsoft Entra ID (Azure AD),
  z ograniczeniem do skonfigurowanego tenant-a uczelni;
- reverse proxy i HTTPS;
- użytkownik bez uprawnień root w kontenerze aplikacji;
- backup MariaDB, MongoDB, uploadów i wygenerowanych dokumentów;
- okresowe testy odtwarzania backupu;
- monitoring, logi strukturalne i alerty;
- aktualizacja `CLAUDE.md`, README i diagramów;
- ujednolicenie modelu statusów.

Kryterium odbioru:

- porty baz nie są publicznie wystawione w konfiguracji produkcyjnej;
- wykonano udokumentowany test odtworzenia backupu;
- dokumentacja opisuje rzeczywiste tabele, statusy i endpointy.
