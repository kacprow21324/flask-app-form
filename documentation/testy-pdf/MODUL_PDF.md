# Analiza techniczna modułu PDF

## Struktura

| Element | Odpowiedzialność |
|---|---|
| `core/generate_pdf_latex.py` | Render Jinja2, escapowanie danych i uruchomienie XeLaTeX |
| `templates/latex/base.tex` | Wspólny preambuła, fonty, marginesy, pola i numeracja |
| `templates/latex/*.tex.j2` | Szablony 13 typów dokumentów |
| `core/documents.py` | Wersjonowanie, fingerprint, SHA-256 i zapis pliku |
| `core/web.py` | Autoryzacja, pobieranie danych, endpointy i komunikaty błędów |
| `core/retention.py` | Pakiety ZIP, manifest i kontrola integralności |
| `scripts/generate_pdf_test_artifacts.py` | Odtwarzalne przykłady i podglądy etapu 11A |
| `tests/test_pdf_generation.py` | Rzeczywiste testy kompilacji i zawartości |

## Biblioteki i narzędzia

- Jinja2 - podstawienie danych do szablonu,
- XeLaTeX - skład dokumentu PDF,
- `fontspec` i `polyglossia` - fonty Unicode i język polski,
- `geometry`, `tabularx`, `longtable`, `fancyhdr`, `amssymb` - układ,
- PyMuPDF - analiza i render podglądów,
- `hashlib` - sumy SHA-256,
- `zipfile` - eksport zbiorczy.

`core/generate_pdf.py` z WeasyPrint pozostaje obsługą starszego mechanizmu
HTML, natomiast produkcyjny endpoint pobierania używa XeLaTeX.

## Proces generowania

1. Użytkownik żąda PDF dla studenta i formularza.
2. Backend sprawdza rolę oraz dostęp do rekordu.
3. Pobierany jest formularz i numer jego rewizji.
4. Generacja jest dozwolona tylko dla aktualnej zatwierdzonej rewizji.
5. Obliczane są checksum danych i wersja szablonu.
6. Jeżeli identyczny dokument istnieje, zwracana jest wersja archiwalna.
7. Jinja2 renderuje źródło `.tex` z escapowaniem wartości.
8. XeLaTeX uruchamia się dwa razy z `-no-shell-escape`.
9. Moduł sprawdza kod wyjścia, timeout, obecność pliku i sygnaturę `%PDF-`.
10. PDF jest zapisywany, wersjonowany i rejestrowany w audycie.
11. `send_file` zwraca załącznik z właściwą nazwą i MIME.

## Bezpieczeństwo

- lista kluczy szablonów jest ograniczona wyrażeniem regularnym,
- endpoint dopuszcza tylko skonfigurowane załączniki,
- wartości użytkownika są escapowane dla LaTeX,
- kompilacja ma `-no-shell-escape` i limit 60 sekund,
- ścieżki archiwum są sprawdzane względem katalogu danych,
- dostęp jest kontrolowany według roli i przypisań,
- PDF jest powiązany z rewizją danych i wersją szablonu,
- integralność plików zabezpiecza SHA-256.

## Wydajność

Pomiar 12 reprezentatywnych dokumentów:

- łączny czas: około 13,44 s,
- średnio: około 1,07 s na dokument,
- maksimum: około 1,19 s,
- ponowne pobranie tej samej rewizji nie uruchamia kompilatora.

Największy koszt stanowi uruchomienie dwóch procesów XeLaTeX. Zapis i odczyt
pliku są małe w porównaniu z czasem kompilacji.

## Optymalizacje

1. Przenieść masową generację do kolejki zadań.
2. Równolegle generować niezależne dokumenty z ograniczeniem liczby procesów.
3. Utrzymać obecny cache po fingerprintach danych i szablonu.
4. Dodać metryki czasu i błędów kompilacji do Prometheusa.
5. Dla dużych archiwów użyć strumieniowania lub magazynu obiektowego.
