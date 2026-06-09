"""Deterministic sample data used by ETAP 11A PDF tests and artifacts."""

from copy import deepcopy


EFFECT_MAP = {
    1: "Potrafi analizować wymagania i dobierać narzędzia informatyczne.",
    2: "Konfiguruje systemy operacyjne, usługi sieciowe i bazy danych.",
    3: "Stosuje zasady bezpieczeństwa informacji i ochrony danych.",
    4: "Dokumentuje wykonane zadania oraz przedstawia ich rezultaty.",
    5: "Współpracuje w zespole i komunikuje problemy techniczne.",
    6: "Planuje pracę, ocenia ryzyko i przestrzega zasad BHP.",
}

PROFILES = (
    {
        "name": "Anna Żółć",
        "album": "31001",
        "specialty": "Administracja systemów i sieci komputerowych",
        "company": "Łączność i Rozwój Sp. z o.o.",
        "city": "Elbląg",
        "supervisor": "inż. Michał Górski",
    },
    {
        "name": "Łukasz Ćwikła",
        "album": "31002",
        "specialty": "Projektowanie baz danych i oprogramowanie użytkowe",
        "company": "R&D Północ S.A.",
        "city": "Gdańsk",
        "supervisor": "mgr inż. Joanna Wróbel",
    },
    {
        "name": "Małgorzata Ździebło",
        "album": "31003",
        "specialty": "Technologie internetowe i multimedialne",
        "company": "Źródło Danych sp. z o.o.",
        "city": "Olsztyn",
        "supervisor": "Paweł Jaśkiewicz",
    },
)


DIARY_TASKS = (
    "Konfiguracja środowiska testowego oraz kontrola dostępu użytkowników.",
    "Analiza wymagań i przygotowanie dokumentacji technicznej rozwiązania.",
    "Implementacja modułu obsługi danych oraz testy poprawności walidacji.",
    "Przegląd logów, diagnoza błędów i przygotowanie propozycji poprawek.",
    "Konfiguracja kopii zapasowej oraz próba odtworzenia danych.",
    "Aktualizacja instrukcji wdrożenia i prezentacja wyników zespołowi.",
)


def _diary_entries(profile, count=24, long_text=False):
    entries = []
    for index in range(count):
        task = DIARY_TASKS[index % len(DIARY_TASKS)]
        if long_text:
            task = (
                f"{task} Wpis {index + 1}: sprawdzono również znaki specjalne "
                r"R&D, 100%, plik_testowy, C:\backup oraz identyfikator #PDF. "
                "Opis zawiera rozbudowane uzasadnienie wykonanych czynności, "
                "wyniki testów i wnioski przekazane opiekunowi praktyki."
            )
        entries.append({
            "dzien": str(index + 1),
            "data": f"2026-07-{(index % 28) + 1:02d}",
            "godziny": "8",
            "opis": task,
            "efekty": f"{(index % 6) + 1}, {((index + 1) % 6) + 1}",
            "podpis": profile["supervisor"],
        })
    return entries


def diary_context(profile, count=24, long_text=False):
    return {
        "data": {
            "imie_nazwisko": profile["name"],
            "nr_albumu": profile["album"],
            "specjalnosc": profile["specialty"],
            "rok_akademicki": "2025/2026",
            "miejsce_praktyki": f'{profile["company"]}, {profile["city"]}',
            "data_start": "2026-07-01",
            "data_end": "2026-08-15",
            "dziennik": _diary_entries(profile, count, long_text),
        }
    }


def effects_context(profile):
    return {
        "data": {
            "imie_nazwisko": profile["name"],
            "nr_albumu": profile["album"],
            "specjalnosc": profile["specialty"],
            "wymiar_godzin": "960",
            "potwierdzenie_opiekuna": (
                f'{profile["supervisor"]}, {profile["city"]}, 2026-08-18'
            ),
            "opinia_opiekuna": (
                "Student/ka osiągnął/osiągnęła wszystkie wskazane efekty."
            ),
            "efekty": [
                {"nr": number, "status": "osiągnięty"}
                for number in EFFECT_MAP
            ],
        },
        "effect_map": deepcopy(EFFECT_MAP),
    }


def report_context(profile, long_text=False):
    detail = (
        "Praktyka obejmowała analizę wymagań, konfigurację środowiska, "
        "implementację, testy, dokumentowanie wyników i współpracę z zespołem."
    )
    if long_text:
        detail = " ".join([detail] * 18)
    return {
        "data": {
            "imie_nazwisko": profile["name"],
            "nr_albumu": profile["album"],
            "specjalnosc": profile["specialty"],
            "rok_akademicki": "2025/2026",
            "miejsce_praktyki": f'{profile["company"]}, {profile["city"]}',
            "charakterystyka": (
                f'{profile["company"]} realizuje projekty informatyczne '
                "dla klientów sektora publicznego i prywatnego."
            ),
            "opis_prac": detail,
            "wiedza_umiejetnosci": (
                "Rozwinięto umiejętność diagnozowania problemów, bezpiecznej "
                "pracy z danymi oraz tworzenia czytelnej dokumentacji."
            ),
            "data": "2026-08-20",
            "podpis_studenta": profile["name"],
        }
    }


def protocol_context(profile):
    return {
        "data": {
            "imie_nazwisko": profile["name"],
            "nr_albumu": profile["album"],
            "data_zaliczenia": "2026-09-02",
            "przewodniczacy": "dr Irena Malinowska",
            "czlonek_2": "mgr Tomasz Witek",
            "czlonek_3": "mgr Anna Kowalczyk",
            "czlonek_4": "",
            "miejsca_praktyki": [{
                "nazwa": f'{profile["company"]}, {profile["city"]}',
                "okres": "2026-07-01 - 2026-08-15",
                "dni": "30",
            }],
            "ocena_s": "5,0",
            "ocena_u": "4,5",
            "ocena_z": "5,0",
            "mini_zadania": [
                {
                    "tresc": "Omów najważniejszy problem techniczny.",
                    "ocena": "5,0",
                },
                {
                    "tresc": "Przedstaw sposób zabezpieczenia danych.",
                    "ocena": "4,5",
                },
            ],
            "ocena_e": "5,0",
            "ocena_k": "4,9",
            "data_s": "2026-08-25",
            "podpis_s": "dr Irena Malinowska",
        }
    }


def artifact_documents():
    documents = []
    for profile in PROFILES:
        album = profile["album"]
        documents.extend([
            (f"dziennik_{album}.pdf", "zal6", diary_context(profile)),
            (f"efekty_{album}.pdf", "zal4", effects_context(profile)),
            (f"raport_koncowy_{album}.pdf", "zal7", report_context(profile)),
            (f"protokol_{album}.pdf", "zal8", protocol_context(profile)),
        ])
    return documents
