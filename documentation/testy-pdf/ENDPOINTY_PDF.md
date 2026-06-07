# Endpointy PDF i archiwów

## Generowanie aktualnego dokumentu

```http
GET /student/<nr_albumu>/<zal_key>/pobierz
```

Przykład:

```http
GET /student/21001/zal6/pobierz
```

Endpoint:

- wymaga zalogowania,
- sprawdza dostęp do studenta,
- akceptuje wyłącznie skonfigurowany typ załącznika,
- wymaga aktualnej zatwierdzonej rewizji,
- generuje albo zwraca istniejącą wersję,
- ustawia `Content-Type: application/pdf`,
- zwraca nazwę `Zal_<numer>_<album>.pdf`.

Przy braku danych, zatwierdzenia albo silnika użytkownik jest przekierowany do
widoku studenta z komunikatem błędu. Nieudany dokument nie jest archiwizowany.

## Pobranie konkretnej wersji

```http
GET /dokumenty-wygenerowane/<document_id>/pobierz
```

| Status | Znaczenie |
|---|---|
| 200 | Plik został zwrócony |
| 403 | Brak dostępu do studenta lub typu dokumentu |
| 404 | Rekord wersji nie istnieje |
| 410 | Rekord istnieje, ale pliku brakuje |
| 500 | Nieprawidłowa ścieżka archiwum |

## Podgląd do wydruku

```http
GET /student/<nr_albumu>/<zal_key>/drukuj
```

Zwraca widok HTML zatwierdzonej rewizji przeznaczony do podglądu i wydruku.

## Utworzenie pakietu ZIP

```http
POST /student/<nr_albumu>/usun
```

Historyczna nazwa endpointu oznacza obecnie archiwizację, nie fizyczne
usunięcie. Operacja jest dostępna dla administratora i dziekanatu. Tworzy ZIP,
blokuje rekord do edycji i ustawia okres retencji.

## Pobranie ZIP

```http
GET /archiwa/<package_id>/pobierz
```

Endpoint sprawdza rolę, status pakietu, sumę kontrolną archiwum i manifestu.
Zwraca `application/zip`; uszkodzony albo brakujący pakiet daje HTTP 410.

## Przykład curl

Endpointy wymagają zalogowanej sesji:

```bash
curl -b cookies.txt -OJ \
  http://localhost:5000/student/21001/zal6/pobierz
```
