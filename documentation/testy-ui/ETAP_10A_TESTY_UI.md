# ETAP 10A - testowanie i weryfikacja interfejsu użytkownika

Data wykonania: 7 czerwca 2026 r.

## Środowisko testowe

- aplikacja Flask uruchomiona w Docker Compose,
- baza testowa SQLite oraz MongoDB 7,
- Playwright 1.52,
- Chromium i Firefox,
- rozdzielczość desktopowa 1440 x 1000,
- rozdzielczość mobilna 390 x 844.

Testy są odtwarzalne poleceniem:

```powershell
docker-compose -f docker-compose.e2e.yml up --build `
  --abort-on-container-exit --exit-code-from e2e e2e
docker-compose -f docker-compose.e2e.yml down --volumes
```

Wynik ostatniego przebiegu: **10/10 testów zakończonych powodzeniem**.

## 1. Lista i stan widoków

| Widok | Funkcja | Status | Uwagi |
|---|---|---|---|
| Logowanie | Logowanie lokalne i Microsoft Entra ID | OK | Sprawdzono przekierowanie niezalogowanego użytkownika |
| Dashboard | Widok startowy zależny od roli | OK | Student, opiekunowie, dziekanat i administrator |
| Podgląd studenta | Zbiorczy stan dokumentów i praktyki | OK | Dostęp kontrolowany przez role |
| Załączniki 1-9 | Wprowadzanie dokumentacji praktyki | OK | Sprawdzono otwarcie wszystkich 14 formularzy |
| Części praktyki | Dodawanie i edycja części praktyki | OK | Operacje dostępne dla dziekanatu i administratora |
| Obieg dokumentów | Wysyłanie, akceptacja i odrzucanie dokumentów | OK | Widok zależny od roli |
| Przydziały | Powiązanie studentów z opiekunami | OK | Widok zarządczy |
| Administracja | Użytkownicy, import CSV, raporty i REST API | OK | Dodano panel studentów korzystający z `/api/students` |
| Konfiguracja | Efekty uczenia, specjalności i ustawienia | OK | Widok administratora |
| Powiadomienia | Lista i odczyt powiadomień | OK | Nawigacja działa |
| Profil | Dane użytkownika i zmiana hasła | OK | Formularz dostępny po zalogowaniu |
| Regulamin | Podgląd dokumentu regulaminu | OK | Widok dostępny z menu |
| Wydruk/PDF | Podgląd i pobieranie dokumentów | OK | Zależne od stanu dokumentu |

Spójność nazw przycisków i sekcji sprawdzono podczas przejścia przez widoki.
Menu boczne ma wspólne nazwy, stan aktywny oraz wersję mobilną.

## 2. Testy formularzy

| Formularz / operacja | Dane testowe | Oczekiwany rezultat | Wynik |
|---|---|---|---|
| Załącznik 1 | Brak imienia i nazwiska | Komunikat „Pole jest wymagane” | OK |
| Załącznik 1 | `Jan 123` | Odrzucenie cyfr w nazwie | OK |
| Załącznik 1 | NIP `123` | Komunikat o wymaganych 10 cyfrach | OK |
| Załącznik 1 | Data końca przed datą początku | Komunikat o błędnym zakresie dat | OK |
| Dziennik praktyk | Numer dnia `121` | Odrzucenie wartości poza 1-120 | OK |
| Dziennik praktyk | Liczba godzin `9` | Odrzucenie wartości poza 1-8 | OK |
| Dziennik praktyk | Opis krótszy niż 20 znaków | Komunikat o zbyt krótkim opisie | OK |
| Części praktyki | Poprawna firma i daty | Utworzenie części praktyki | OK |
| Części praktyki | Zmieniona nazwa i liczba godzin | Aktualizacja części praktyki | OK |
| Student REST | Poprawne dane studenta | Utworzenie i wpis w tabeli | OK |
| Student REST | Istniejący numer albumu | Błąd 409 widoczny w interfejsie | OK |
| Student REST | Edycja nazwiska | Aktualizacja przez PUT | OK |
| Student REST | Usunięcie po potwierdzeniu | Dezaktywacja przez DELETE | OK |

Przyciski formularzy mają opis czynności, a operacje usuwania wymagają
potwierdzenia.

## 3. Komunikacja frontend - API

Panel w widoku administracyjnym komunikuje się bezpośrednio z REST API za
pomocą `fetch`. Token CSRF jest przekazywany w nagłówku `X-CSRF-Token`.

| Metoda | Żądanie | Status | Reakcja interfejsu |
|---|---|---|---|
| GET | `/api/students` | 200 | Wyświetlenie tabeli studentów |
| POST | `/api/students` | 201 | Dodanie wiersza i komunikat sukcesu |
| PUT | `/api/students/<id>` | 200 | Aktualizacja danych w tabeli |
| DELETE | `/api/students/<id>` | 204 | Usunięcie wiersza z tabeli |
| POST | Powtórzony numer albumu | 409 | Czytelny komunikat błędu |
| GET | Symulowana utrata połączenia | błąd sieci | Komunikat o braku połączenia |

Zapis żądań: [api-traffic-crud.json](screenshots/api-traffic-crud.json).

Dowody:

- [POST 201](screenshots/03-api-post-201.png)
- [GET/POST/PUT/DELETE i dziennik HTTP](screenshots/04-api-crud-http-log.png)
- [obsługa 409](screenshots/05-api-error-409.png)
- [utrata połączenia](screenshots/06-api-offline-error.png)
- [panel API w Firefox](screenshots/11-firefox-api-panel.png)

## 4. Walidacja po stronie klienta

| Lp. | Przypadek | Oczekiwane zachowanie | Wynik |
|---|---|---|---|
| 1 | Puste pole imienia i nazwiska | Blokada i komunikat | OK |
| 2 | Cyfry w imieniu i nazwisku | Komunikat o dozwolonych znakach | OK |
| 3 | Niepoprawny e-mail | Walidacja formatu przeglądarki | OK |
| 4 | NIP krótszy niż 10 cyfr | Komunikat walidacji | OK |
| 5 | Pusty numer albumu w panelu API | Blokada wysłania formularza | OK |
| 6 | Data końca wcześniejsza od początku | Komunikat walidacji | OK |
| 7 | Dzień dziennika równy 0 | Odrzucenie wartości | OK |
| 8 | Dzień dziennika większy niż 120 | Odrzucenie wartości | OK |
| 9 | Godziny równe 0 | Odrzucenie wartości | OK |
| 10 | Godziny większe niż 8 | Odrzucenie wartości | OK |
| 11 | Opis wpisu krótszy niż 20 znaków | Komunikat o długości | OK |
| 12 | Puste wymagane pola formularza API | Blokada przez HTML5 `required` | OK |

Komunikaty są wyświetlane bezpośrednio pod polem, mają kontrastowy kolor i
opisują sposób poprawienia danych. Walidacja klienta nie zastępuje walidacji
serwerowej.

Dowody:

- [walidacja Załącznika 1](screenshots/07-validation-zal1.png)
- [walidacja dziennika](screenshots/08-validation-diary.png)

## 5. UX i responsywność

Testy wykonano w Chromium i Firefox. W trybie mobilnym sprawdzono otwieranie
menu, zamykanie przez przycisk, kliknięcie tła i klawisz Escape. Formularze
przechodzą do układu jednokolumnowego, a nagłówek i przyciski nie wychodzą poza
obszar ekranu.

Interfejs informuje użytkownika o:

- powodzeniu utworzenia, aktualizacji i usunięcia danych,
- błędach walidacji,
- konfliktach danych zwróconych przez API,
- utracie połączenia z API,
- operacjach wymagających potwierdzenia.

Dowody:

- [menu mobilne 390 x 844](screenshots/10-mobile-menu.png)
- [widok studenta w Firefox](screenshots/12-firefox-student-view.png)

## 6. Analiza błędów JavaScript

Każdy test przechwytuje błędy `console.error` i nieobsłużone wyjątki strony.
W scenariuszach pozytywnych nie wykryto błędów JavaScript. W scenariuszu
negatywnym oczekiwane są wpisy przeglądarki dotyczące odpowiedzi 409 i
przerwanego żądania; interfejs obsługuje je i pokazuje komunikat użytkownikowi.

Szczegółowy raport: [RAPORT_BLEDOW_UI.md](RAPORT_BLEDOW_UI.md).

## 7. Automatyzacja i artefakty

Scenariusze znajdują się w `tests/e2e/test_smoke.py`. GitHub Actions uruchamia
je w osobnym zadaniu i zawsze publikuje katalog `documentation/testy-ui/screenshots`
jako artefakt `ui-test-evidence`.

Pełna dokumentacja techniczna frontendu znajduje się w
[../FRONTEND.md](../FRONTEND.md).
