# Raport błędów interfejsu

Data weryfikacji: 7 czerwca 2026 r.

| ID | Problem | Sposób odtworzenia | Rozwiązanie | Stan |
|---|---|---|---|---|
| UI-01 | Menu boczne było stale ukryte na ekranie mobilnym | Ustawić szerokość 390 px i nacisnąć przycisk menu | Dodano wysuwane menu, tło, Escape i poprawne `aria-expanded` | Naprawiony |
| UI-02 | Frontend nie wykonywał żadnych operacji przez nowe REST API | Otworzyć DevTools i przejść po aplikacji | Dodano panel studentów w administracji z GET, POST, PUT i DELETE | Naprawiony |
| UI-03 | Brak walidacji numeru dnia i godzin w dzienniku po stronie klienta | Wpisać dzień 121 albo 9 godzin | Dodano zakresy 1-120 oraz 1-8 z komunikatami przy polach | Naprawiony |
| UI-04 | Brak wspólnej walidacji pól e-mail | Wpisać tekst bez poprawnego formatu adresu | Dodano walidację `input[type=email]` i zachowano walidację HTML5 | Naprawiony |
| UI-05 | Utrata połączenia z API nie miała reprezentacji w interfejsie | Przerwać GET `/api/students` | Dodano obsługę wyjątku `fetch` i komunikat o braku połączenia | Naprawiony |

## Weryfikacja konsoli

- brak nieobsłużonych wyjątków `pageerror` w 10 scenariuszach,
- brak `console.error` w scenariuszach pozytywnych,
- odpowiedź 409 i celowo przerwane żądanie generują techniczny wpis
  przeglądarki, ale są przechwycone przez interfejs,
- testy po poprawkach zakończyły się wynikiem 10/10.

## Ryzyko resztkowe

- automatyczne testy obejmują Chromium i Firefox, ale nie Safari/WebKit,
- ocena czytelności treści ma częściowo charakter manualny,
- zrzuty pokazują reprezentatywne scenariusze, a nie każdy ekran aplikacji,
- testy mobilne używają emulowanego viewportu, nie fizycznego urządzenia.
