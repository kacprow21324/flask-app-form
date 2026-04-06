from flask import Flask, render_template, request
import json
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_FILE = os.path.join(DATA_DIR, "studenci.json")

EFFECTS = [
    {
        "nr": 1,
        "opis": (
            "Ma wiedzę na temat sposobu realizacji zadań inżynierskich "
            "dotyczących informatyki z zachowaniem standardów i norm "
            "technicznych"
        ),
    },
    {
        "nr": 2,
        "opis": (
            "Zna technologie, narzędzia, metody, techniki oraz sprzęt "
            "stosowane w informatyce"
        ),
    },
    {
        "nr": 3,
        "opis": (
            "Zna ekonomiczne, prawne skutki własnych działań podejmowanych "
            "w ramach praktyki oraz ograniczenia wynikające z prawa "
            "autorskiego i kodeksu pracy"
        ),
    },
    {
        "nr": 4,
        "opis": "Zna zasady bezpieczeństwa pracy i ergonomii w zawodzie informatyka",
    },
    {
        "nr": 5,
        "opis": (
            "Pozyskuje informacje odnośnie technologii, metod, technik, "
            "sprzętu wymaganego do realizacji powierzonego zadania, "
            "posługując się rozmaitymi źródłami literaturowymi i zasobami "
            "publikowanymi w języku polskim jak i angielskim"
        ),
    },
    {
        "nr": 6,
        "opis": (
            "W oparciu o kontakty ze środowiskiem inżynierskim zakładu, "
            "potrafi podnieść swoje kompetencje, wiedzę i umiejętności, "
            "co najmniej z dwóch zakresów: zadania dotyczące sprzętu i "
            "oprogramowania: np.: programowania, administrowanie siecią "
            "komputerową, konserwacja sprzętu i oprogramowania, bieżące "
            "usuwanie usterek, administrowanie zasobami informatycznymi, "
            "zakładu pracy / instytucji, (e)-usługami."
        ),
    },
    {
        "nr": 7,
        "opis": (
            "Opracowuje dokumentację dotyczącą realizacji podejmowanych "
            "zadań w ramach praktyki, a także referuje ustnie prezentowane "
            "w niej zagadnienia"
        ),
    },
    {
        "nr": 8,
        "opis": (
            "Potrafi zidentyfikować problem informatyczny występujący "
            "w zakładzie pracy / instytucji, opisać go, przedstawić "
            "koncepcję rozwiązania i ją zrealizować."
        ),
    },
    {
        "nr": 9,
        "opis": (
            "Potrafi rozwiązać rzeczywiste zadanie inżynierskie z zakresu "
            "działalności informatycznej zakładu pracy/instytucji stosując "
            "normy i standardy stosowane w informatyce oraz biorąc pod "
            "uwagę aspekty środowiskowe i etyczne."
        ),
    },
    {
        "nr": 10,
        "opis": "Pracuje w zespole zajmującym się zawodowo branżą IT,",
    },
    {
        "nr": 11,
        "opis": (
            "Przestrzega zasad etyki zawodowej i zgodnie z tymi zasadami "
            "korzysta z wiedzy i pomocy doświadczonych kolegów"
        ),
    },
    {
        "nr": 12,
        "opis": (
            "Kontaktując się z osobami spoza branży potrafi zarówno "
            "pozyskać od nich niezbędne informacje do realizacji "
            "planowanego zadania, jak i przekazać im w sposób zrozumiały "
            "informacje i opinie z zakresu informatyki"
        ),
    },
    {
        "nr": 13,
        "opis": (
            "Dostrzega w praktyce tempo deaktualizacji wiedzy informatycznej "
            "oraz skutki działalności informatyków w szczególności "
            "ekonomiczne i społeczne"
        ),
    },
]


def is_valid_full_name(value):
    parts = value.split()
    return len(parts) >= 2


def is_digits_only(value):
    return value.isdigit()


def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}


def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


@app.route("/")
def index():
    data = load_data()
    students = []
    for nr_albumu in sorted(data.keys()):
        forms = data.get(nr_albumu, {})
        imie_nazwisko = ""
        if "zal4" in forms:
            imie_nazwisko = forms["zal4"].get("imie_nazwisko", "")
        elif "zal6" in forms:
            imie_nazwisko = forms["zal6"].get("imie_nazwisko", "")
        students.append(
            {
                "nr_albumu": nr_albumu,
                "imie_nazwisko": imie_nazwisko,
                "has_zal4": "zal4" in forms,
                "has_zal6": "zal6" in forms,
            }
        )
    return render_template("index.html", students=students)


@app.route("/podglad/<nr_albumu>")
def podglad(nr_albumu):
    data = load_data()
    student = data.get(nr_albumu)
    if not student:
        return render_template("podglad.html", nr_albumu=nr_albumu, missing=True)
    return render_template(
        "podglad.html",
        nr_albumu=nr_albumu,
        zal4=student.get("zal4"),
        zal6=student.get("zal6"),
        missing=False,
    )


@app.route("/zal4", methods=["GET", "POST"])
def zal4():
    if request.method == "POST":
        imie_nazwisko = request.form.get("imie_nazwisko", "").strip()
        nr_albumu = request.form.get("nr_albumu", "").strip()
        kierunek = request.form.get("kierunek", "").strip()
        specjalnosc = request.form.get("specjalnosc", "").strip()
        wymiar_godzin = request.form.get("wymiar_godzin", "").strip()
        potwierdzenie_opiekuna = request.form.get("potwierdzenie_opiekuna", "").strip()
        opinia_opiekuna = request.form.get("opinia_opiekuna", "").strip()

        if not is_valid_full_name(imie_nazwisko):
            return render_template(
                "zal4.html",
                error="Podaj imię i nazwisko (co najmniej dwa wyrazy).",
                effects=EFFECTS,
            )

        if not nr_albumu:
            return render_template(
                "zal4.html",
                error="Podaj numer albumu.",
                effects=EFFECTS,
            )

        if not is_digits_only(nr_albumu):
            return render_template(
                "zal4.html",
                error="Numer albumu może zawierać tylko cyfry.",
                effects=EFFECTS,
            )

        efekty = []
        for effect in EFFECTS:
            status = request.form.get(f"efekt_{effect['nr']}", "")
            efekty.append({"nr": effect["nr"], "status": status})

        zal4_data = {
            "imie_nazwisko": imie_nazwisko,
            "nr_albumu": nr_albumu,
            "kierunek": kierunek,
            "specjalnosc": specjalnosc,
            "wymiar_godzin": wymiar_godzin,
            "potwierdzenie_opiekuna": potwierdzenie_opiekuna,
            "opinia_opiekuna": opinia_opiekuna,
            "efekty": efekty,
        }

        data = load_data()
        data.setdefault(nr_albumu, {})
        data[nr_albumu]["zal4"] = zal4_data
        save_data(data)

        return render_template("zal4.html", saved=True, effects=EFFECTS)

    return render_template("zal4.html", effects=EFFECTS)


@app.route("/zal6", methods=["GET", "POST"])
def zal6():
    if request.method == "POST":
        imie_nazwisko = request.form.get("imie_nazwisko", "").strip()
        nr_albumu = request.form.get("nr_albumu", "").strip()
        kierunek = request.form.get("kierunek", "").strip()
        specjalnosc = request.form.get("specjalnosc", "").strip()
        rok_akademicki = request.form.get("rok_akademicki", "").strip()
        miejsce_praktyki = request.form.get("miejsce_praktyki", "").strip()
        data_start = request.form.get("data_start", "").strip()
        data_end = request.form.get("data_end", "").strip()
        wykaz_zalacznikow = request.form.get("wykaz_zalacznikow", "").strip()

        if not is_valid_full_name(imie_nazwisko):
            return render_template(
                "zal6.html",
                error="Podaj imię i nazwisko (co najmniej dwa wyrazy).",
                effects=EFFECTS,
            )

        if not nr_albumu:
            return render_template(
                "zal6.html",
                error="Podaj numer albumu.",
                effects=EFFECTS,
            )

        if not is_digits_only(nr_albumu):
            return render_template(
                "zal6.html",
                error="Numer albumu może zawierać tylko cyfry.",
                effects=EFFECTS,
            )

        dni = request.form.getlist("dzien[]")
        daty = request.form.getlist("data[]")
        opisy = request.form.getlist("opis[]")
        efekty = request.form.getlist("efekty[]")
        podpisy = request.form.getlist("podpis[]")

        dziennik = []
        for dzien, data, opis, efekt, podpis in zip(dni, daty, opisy, efekty, podpisy):
            dziennik.append(
                {
                    "dzien": dzien,
                    "data": data,
                    "opis": opis,
                    "efekty": efekt,
                    "podpis": podpis,
                }
            )

        zal6_data = {
            "imie_nazwisko": imie_nazwisko,
            "nr_albumu": nr_albumu,
            "kierunek": kierunek,
            "specjalnosc": specjalnosc,
            "rok_akademicki": rok_akademicki,
            "miejsce_praktyki": miejsce_praktyki,
            "data_start": data_start,
            "data_end": data_end,
            "wykaz_zalacznikow": wykaz_zalacznikow,
            "dziennik": dziennik,
        }

        data = load_data()
        data.setdefault(nr_albumu, {})
        data[nr_albumu]["zal6"] = zal6_data
        save_data(data)

        return render_template("zal6.html", saved=True, effects=EFFECTS)

    return render_template("zal6.html", effects=EFFECTS)


if __name__ == "__main__":
    app.run(debug=True)
