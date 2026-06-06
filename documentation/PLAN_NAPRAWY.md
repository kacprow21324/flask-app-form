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

Status: w trakcie (24 testy jednostkowe i integracyjne).

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
- workflow CI w GitHub Actions.

Kryterium odbioru:

- testy uruchamiają się jednym poleceniem w Dockerze;
- CI blokuje wdrożenie po błędzie testu;
- krytyczne trasy mają test pozytywny i test odmowy dostępu.

## Etap 5: reguły procesu praktyk

Status: w trakcie.

Zrealizowane:

- jawne przypisywanie UOPZ i ZOPZ przez dziekanat/admina;
- brak automatycznego wyboru pierwszego opiekuna przy tworzeniu praktyki;
- widok postępu studenta: dokumenty, godziny i dni;
- godziny dziennika walidowane po stronie serwera (1-8 dziennie, do 120 dni
  i 960 godzin łącznie);
- dziekanat widzi wszystkich studentów, a opiekunowie tylko przypisanych;
- powiadomienia i wpis audytowy po zmianie przydziału.

Zakres:

- obsługa kilku części praktyki w jednym roku akademickim;
- wyliczanie oceny końcowej na serwerze;
- generowanie wersji PDF tylko z zatwierdzonego dokumentu;
- pobieranie istniejącej wersji bez tworzenia duplikatu;
- archiwizacja, anonimizacja i retencja zamiast niepełnego usuwania.

Kryterium odbioru:

- opiekun widzi tylko jawnie przypisane praktyki;
- reguły godzin i ocen nie zależą od JavaScriptu;
- każda wersja PDF ma źródło, sumę kontrolną i autora;
- operacja usunięcia ma zdefiniowany zakres danych i plików.

## Etap 6: podział aplikacji

Zakres:

- fabryka aplikacji `create_app`;
- Blueprinty: `auth`, `student`, `review`, `admin`, `documents`;
- serwisy workflow, praktyk, ocen i dokumentów;
- repozytoria MariaDB i MongoDB;
- wspólne mechanizmy autoryzacji i obsługi błędów.

Kryterium odbioru:

- `app.py` zawiera głównie konfigurację aplikacji;
- trasy nie wykonują bezpośrednio złożonych operacji na obu bazach;
- istniejące adresy URL pozostają zgodne albo mają kontrolowaną migrację.

## Etap 7: funkcje administracyjne

Status: w trakcie.

Zakres:

- użytkownicy, role, aktywacja i reset hasła;
- import studentów z CSV;
- przydziały opiekunów (zrealizowane);
- historia dokumentów i archiwum;
- terminy i alerty;
- raporty CSV/XLSX;
- przeglądarka `audit_logs`;
- panel aktywnych sesji;
- komplet dokumentów PDF/ZIP;
- komentarze do sekcji i autosave z rewizją.

## Etap 8: produkcja i dokumentacja

Zakres:

- bazy dostępne tylko w sieci wewnętrznej Dockera;
- uwierzytelnienie MongoDB;
- reverse proxy i HTTPS;
- użytkownik bez uprawnień root w kontenerze aplikacji;
- backup MariaDB, MongoDB, uploadów i wygenerowanych dokumentów;
- okresowe testy odtwarzania backupu;
- monitoring, logi strukturalne i alerty;
- aktualizacja `CLAUDE.md`, README i diagramów;
- poprawienie limitu 9660 na 960 i ujednolicenie modelu statusów.

Kryterium odbioru:

- porty baz nie są publicznie wystawione w konfiguracji produkcyjnej;
- wykonano udokumentowany test odtworzenia backupu;
- dokumentacja opisuje rzeczywiste tabele, statusy i endpointy.
