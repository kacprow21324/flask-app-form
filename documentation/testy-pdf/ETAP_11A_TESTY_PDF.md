# ETAP 11A - testowanie i weryfikacja generowania PDF

Data wykonania: 7 czerwca 2026 r.

## Wynik ogólny

- 13/13 testów modułu PDF,
- kompilacja wszystkich 13 szablonów LaTeX,
- 3 dzienniki praktyk dla różnych studentów,
- 3 potwierdzenia efektów uczenia,
- 3 raporty końcowe i 3 protokoły zaliczenia,
- pobieranie sprawdzone w Chromium i Firefox,
- 12 przykładowych PDF oraz 13 podglądów PNG,
- zbiorcze archiwum ZIP z dokumentami i danymi testowymi.

Źródłem danych przykładów jest
[`dane_wejsciowe.json`](przyklady/dane_wejsciowe.json). Wyniki, czasy,
liczby stron i sumy SHA-256 znajdują się w
[`manifest.json`](przyklady/manifest.json).

## Środowisko

- Python 3.11,
- Jinja2,
- XeLaTeX z TeX Live,
- Latin Modern Roman i Latin Modern Sans,
- PyMuPDF do odczytu tekstu, kontroli formatu A4 i tworzenia podglądów,
- Docker Compose,
- Playwright: Chromium i Firefox.

## 1. Dziennik praktyk

Każdy dokument zawiera 24 wpisy, dane studenta, miejsce praktyki, daty,
godziny, efekty i podpis tekstowy opiekuna.

| Dokument | Dane wejściowe | Strony | Nagłówek | Tabela | Polskie znaki | Numeracja |
|---|---|---:|---|---|---|---|
| [31001](przyklady/dziennik_31001.pdf) | Anna Żółć | 2 | OK | OK | OK | OK |
| [31002](przyklady/dziennik_31002.pdf) | Łukasz Ćwikła | 2 | OK | OK | OK | OK |
| [31003](przyklady/dziennik_31003.pdf) | Małgorzata Ździebło | 2 | OK | OK | OK | OK |

Tabela używa `longtable`, dzieli się między strony i powtarza nagłówek.
Automatyczny test z 70 długimi wpisami tworzy co najmniej cztery strony i
sprawdza obecność ostatniego wpisu oraz numerów stron.

Podglądy:

- [strona 1](podglady/dziennik_31001_strona_1.png)
- [strona 2](podglady/dziennik_31001_strona_2.png)

## 2. Potwierdzenie efektów uczenia

| Dokument | Student | Lista efektów | Dane studenta | Układ | Wynik |
|---|---|---|---|---|---|
| [31001](przyklady/efekty_31001.pdf) | Anna Żółć | 6/6 | zgodne | czytelny | OK |
| [31002](przyklady/efekty_31002.pdf) | Łukasz Ćwikła | 6/6 | zgodne | czytelny | OK |
| [31003](przyklady/efekty_31003.pdf) | Małgorzata Ździebło | 6/6 | zgodne | czytelny | OK |

Test automatyczny odczytuje tekst z PDF i porównuje imię, numer albumu, opis
efektu oraz status z rekordem wejściowym. Endpoint aplikacji został dodatkowo
sprawdzony na danych zasianych w bazach środowiska E2E.

Podgląd: [potwierdzenie efektów](podglady/efekty_31002_strona_1.png).

## 3. Raport końcowy

W projekcie rolę raportu końcowego pełni Załącznik 7, a podsumowanie zaliczenia
znajduje się w Załączniku 8.

| Student | Raport | Protokół | Daty | Podsumowanie | Formatowanie |
|---|---|---|---|---|---|
| Anna Żółć | [PDF](przyklady/raport_koncowy_31001.pdf) | [PDF](przyklady/protokol_31001.pdf) | OK | kompletne | OK |
| Łukasz Ćwikła | [PDF](przyklady/raport_koncowy_31002.pdf) | [PDF](przyklady/protokol_31002.pdf) | OK | kompletne | OK |
| Małgorzata Ździebło | [PDF](przyklady/raport_koncowy_31003.pdf) | [PDF](przyklady/protokol_31003.pdf) | OK | kompletne | OK |

Sprawdzono dane studenta, miejsce praktyki, opis prac, wiedzę i umiejętności,
daty, komisję, miejsca praktyki i oceny.

## 4. Szablony PDF

Automatycznie kompilowane są:

`zal1`, `zal2`, `zal2a`, `zal3`, `zal4`, `zal4a`, `zal4b`, `zal5`,
`zal6`, `zal7`, `zal7a`, `zal8`, `zal9`.

Wspólny plik `templates/latex/base.tex` zapewnia:

- stronę A4,
- marginesy 2 cm w pionie i 2,5 cm w poziomie,
- wspólny nagłówek, kolory, tabele, pola i podpisy,
- spójne fonty Latin Modern,
- numerację `Strona N`,
- łamanie długich wartości i tekstów użytkownika.

Podglądy wszystkich czterech reprezentatywnych grup dokumentów znajdują się w
katalogu [`podglady`](podglady).

## 5. Pobieranie plików

| Przeglądarka | Endpoint | Nazwa | MIME | Sygnatura | Wynik |
|---|---|---|---|---|---|
| Chromium | `/student/21001/zal1/pobierz` | `Zal_1_21001.pdf` | `application/pdf` | `%PDF-` | OK |
| Firefox | `/student/21001/zal1/pobierz` | `Zal_1_21001.pdf` | `application/pdf` | `%PDF-` | OK |

Dowody:

- [PDF pobrany w Chromium](pobieranie/chromium-Zal_1_21001.pdf)
- [PDF pobrany w Firefox](pobieranie/firefox-Zal_1_21001.pdf)
- [widok pobierania Chromium](../testy-ui/screenshots/13-pdf-download-chromium.png)
- [widok pobierania Firefox](../testy-ui/screenshots/14-pdf-download-firefox.png)

Dokument jest generowany wyłącznie dla aktualnej zatwierdzonej rewizji.
Ponowne pobranie tej samej rewizji korzysta z wersji zapisanej w archiwum.

## 6. Odporność modułu

| Lp. | Przypadek | Oczekiwane zachowanie | Wynik |
|---:|---|---|---|
| 1 | Pusta lista wpisów dziennika | Poprawny PDF bez wierszy | OK |
| 2 | Minimalne dane dla 13 szablonów | Każdy szablon się kompiluje | OK |
| 3 | 70 długich wpisów | Wielostronicowa tabela bez utraty danych | OK |
| 4 | Bardzo długi raport | Łamanie tekstu i kolejne strony | OK |
| 5 | Polskie znaki `ąęćłńóśźż` | Poprawne wyświetlanie i odczyt | OK |
| 6 | Znaki `& % _ # \` | Bezpieczne escapowanie LaTeX | OK |
| 7 | Próba `../base` jako klucz | Odrzucenie klucza | OK |
| 8 | Nieistniejący szablon | `PDFTemplateNotFound` | OK |
| 9 | Brak programu XeLaTeX | Kontrolowany komunikat użytkownika | OK |
| 10 | Timeout XeLaTeX | `PDFGenerationTimeout` | OK |
| 11 | Kod wyjścia XeLaTeX różny od zera | Log i `PDFCompilationError` | OK |
| 12 | Dokument w statusie `draft` | Brak generacji i archiwizacji | OK |
| 13 | Powtórne pobranie tej samej rewizji | Brak duplikatu, wzrost licznika | OK |

## 7. Architektura i wydajność

Szczegółowa analiza: [MODUL_PDF.md](MODUL_PDF.md).

W ostatnim przebiegu 12 dokumentów powstało w 13,44 s. Średni czas wyniósł
około 1,07 s, a najdłuższa generacja około 1,19 s. Każdy dokument jest
kompilowany dwukrotnie, aby ustabilizować numerację stron.

## 8. Rozszerzenia

- podpisy tekstowe są umieszczane w polach dokumentów,
- skrypt generuje wiele dokumentów w jednym przebiegu,
- aplikacja wersjonuje zatwierdzone PDF-y,
- pakiet archiwalny ZIP zawiera formularze, manifest i wygenerowane dokumenty,
- integralność PDF i ZIP jest chroniona sumami SHA-256,
- przykładowy eksport zbiorczy:
  [pakiet_zbiorczy_etap11a.zip](przyklady/pakiet_zbiorczy_etap11a.zip).

Podpis kryptograficzny PDF i asynchroniczny endpoint generacji masowej nie są
obecnie częścią aplikacji. Są opisane jako możliwe rozszerzenia techniczne.

## Odtworzenie

```powershell
docker-compose build flask
docker-compose run --rm -v "${PWD}:/app" flask `
  python -m unittest discover -s tests -p "test_pdf_generation.py" -v
docker-compose run --rm -v "${PWD}:/app" flask `
  python scripts/generate_pdf_test_artifacts.py
```

Test pobierania w przeglądarkach:

```powershell
docker-compose -f docker-compose.e2e.yml up --build `
  --abort-on-container-exit --exit-code-from e2e e2e
docker-compose -f docker-compose.e2e.yml down --volumes
```
