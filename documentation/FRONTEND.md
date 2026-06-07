# Dokumentacja techniczna frontendu

## Architektura

Frontend jest częścią aplikacji Flask i używa renderowania po stronie serwera.
Nie jest osobną aplikacją SPA. Rozdzielenie odpowiedzialności wygląda
następująco:

- `templates/` - szablony Jinja2 i struktura widoków,
- `static/css/base.css` - wspólne style i responsywność,
- `static/js/form-validate.js` - walidacja formularzy po stronie klienta,
- `static/js/admin-api.js` - komunikacja panelu administracyjnego z REST API,
- `static/images/` - obrazy i logotypy,
- `tests/e2e/` - testy interfejsu w Playwright,
- `frontend/README.md` - punkt wejścia do części frontendowej.

## Główne komponenty

| Komponent | Plik | Odpowiedzialność |
|---|---|---|
| Układ aplikacji | `templates/base.html` | Nagłówek, menu, komunikaty flash, CSRF i nawigacja mobilna |
| Dashboard | `templates/index.html` | Informacje i akcje zależne od roli |
| Formularze praktyk | `templates/zal*.html` | Załączniki i dziennik praktyk |
| Części praktyki | `templates/czesci_praktyki.html` | Dodawanie oraz edycja etapów praktyki |
| Administracja | `templates/administracja.html` | Użytkownicy, raporty, import i panel REST |
| Obieg dokumentów | `templates/obieg.html` | Akceptacja, odrzucanie i komentarze |
| Walidacja | `static/js/form-validate.js` | Błędy pól, dat, NIP, e-mail, dnia i godzin |
| Klient REST | `static/js/admin-api.js` | GET, POST, PUT, DELETE oraz obsługa błędów API |

## Komunikacja z API

Panel „Studenci przez REST API” używa natywnego `fetch`:

1. token CSRF jest odczytywany z elementu `<meta name="csrf-token">`,
2. GET pobiera listę studentów,
3. POST tworzy studenta,
4. PUT aktualizuje wszystkie pola studenta,
5. DELETE dezaktywuje studenta,
6. odpowiedzi błędne są odczytywane jako JSON i prezentowane użytkownikowi,
7. błąd sieci jest zamieniany na komunikat o braku połączenia.

Kontrakt API opisują `swagger.yaml` i rozdział REST API w głównym README.

## Technologie

- HTML5 i Jinja2,
- CSS3 bez zewnętrznego frameworka,
- JavaScript ES6 bez biblioteki frontendowej,
- Fetch API,
- Playwright Python,
- Flask sessions i token CSRF.

## Uruchomienie

Frontend nie wymaga osobnego procesu budowania. Jest serwowany przez Flask:

```powershell
docker-compose up --build
```

Po uruchomieniu aplikacja jest dostępna pod adresem `http://localhost:5000`.

Testy przeglądarkowe:

```powershell
docker-compose -f docker-compose.e2e.yml up --build `
  --abort-on-container-exit --exit-code-from e2e e2e
docker-compose -f docker-compose.e2e.yml down --volumes
```

## Standardy utrzymania

- wspólne elementy widoków należy dodawać do `base.html` lub makr,
- walidacja klienta musi mieć odpowiednik po stronie serwera,
- nowe operacje API powinny obsługiwać stan ładowania, sukces i błąd,
- scenariusze użytkownika powinny mieć test Playwright,
- układ należy sprawdzić co najmniej w Chromium, Firefox i widoku mobilnym.
