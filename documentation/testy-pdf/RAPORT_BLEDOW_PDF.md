# Raport błędów modułu PDF

Data audytu: 7 czerwca 2026 r.

| ID | Problem | Skutek | Rozwiązanie | Stan |
|---|---|---|---|---|
| PDF-01 | Wspólny szablon wyłączał numery stron | Dziennik nie spełniał wymagań numeracji | Dodano stopkę `Strona N` | Naprawiony |
| PDF-02 | Dziennik używał `tabularx` | Tabela nie mogła poprawnie przechodzić na kolejne strony | Zastosowano `longtable` z powtarzanym nagłówkiem | Naprawiony |
| PDF-03 | Makro pola wymuszało jedną linię | Długa specjalność nachodziła na sąsiednią kolumnę | Dodano dynamiczne łamanie tekstu | Naprawiony |
| PDF-04 | Pole podpisu miało stałą wysokość | Długi podpis wychodził poza ramkę | Zastosowano dynamiczną wysokość | Naprawiony |
| PDF-05 | Brak pakietu `amssymb` | Załączniki 3 i 4b nie kompilowały pól wyboru | Dodano `amssymb` | Naprawiony |
| PDF-06 | Dodatkowy `&` w tabeli Załącznika 5 | Ankieta nie kompilowała się | Separator jest dodawany tylko między kolumnami | Naprawiony |
| PDF-07 | Brak rozróżnienia błędów XeLaTeX | Brak silnika mógł wyglądać jak brak szablonu | Dodano osobne wyjątki silnika, timeoutu i kompilacji | Naprawiony |
| PDF-08 | Różne fonty Windows/Docker | Dokument mógł mieć inny układ zależnie od środowiska | Ujednolicono fonty Latin Modern | Naprawiony |

## Ryzyko resztkowe

- podpisy są tekstowe, a nie kryptograficzne,
- produkcyjna generacja wielu nowych PDF-ów jest synchroniczna,
- bardzo duże pakiety powinny być w przyszłości obsługiwane przez kolejkę zadań,
- testy pobierania obejmują Chromium i Firefox, ale nie Safari/WebKit,
- ręczna kontrola wizualna nadal jest potrzebna po większej zmianie stylów.

## Propozycje dalszych zabezpieczeń

1. Wprowadzić limit długości pól tekstowych zależny od typu dokumentu.
2. Generować duże pakiety w zadaniu asynchronicznym.
3. Dodać podpis PAdES, jeżeli dokumenty mają uzyskać moc formalną.
4. Monitorować czas kompilacji i liczbę błędów XeLaTeX.
5. Przechowywać źródło `.tex` dla dokumentów wymagających audytu.
