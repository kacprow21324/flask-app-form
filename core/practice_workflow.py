from decimal import Decimal


STANDARD_STEPS = (
    {
        "phase": 0,
        "key": "zal9",
        "nr": "9",
        "title": "Oświadczenie instytucji o przyjęciu studenta",
        "owner_role": "zopz",
        "owner_label": "Opiekun zakładowy",
        "hint": "Zakład potwierdza przyjęcie studenta i wskazuje opiekuna.",
    },
    {
        "phase": 1,
        "key": "zal1",
        "nr": "1",
        "title": "Porozumienie z zakładem pracy",
        "owner_role": "student",
        "owner_label": "Student",
        "hint": "Student przygotowuje porozumienie, a UOPZ je zatwierdza.",
    },
    {
        "phase": 2,
        "key": "zal2",
        "nr": "2",
        "title": "Program praktyki zawodowej",
        "owner_role": "uopz",
        "owner_label": "Opiekun uczelniany",
        "hint": "UOPZ określa ramowy program praktyki.",
    },
    {
        "phase": 3,
        "key": "zal2a",
        "nr": "2a",
        "title": "Program i harmonogram praktyki",
        "owner_role": "student",
        "owner_label": "Student",
        "hint": "Student przygotowuje harmonogram, który zatwierdza ZOPZ.",
    },
    {
        "phase": 4,
        "key": "zal6",
        "nr": "6",
        "title": "Dziennik praktyki zawodowej",
        "owner_role": "student",
        "owner_label": "Student",
        "hint": "Student prowadzi dziennik, a po zakończeniu zatwierdza go ZOPZ.",
    },
    {
        "phase": 5,
        "key": "zal4",
        "nr": "4",
        "title": "Potwierdzenie efektów uczenia się",
        "owner_role": "zopz",
        "owner_label": "Opiekun zakładowy",
        "hint": "ZOPZ potwierdza osiągnięte efekty uczenia się.",
    },
    {
        "phase": 6,
        "key": "report",
        "nr": "7/7a",
        "title": "Sprawozdanie z praktyki",
        "owner_role": "student",
        "owner_label": "Student",
        "hint": "Załącznik 7 dla studiów stacjonarnych albo 7a dla niestacjonarnych.",
    },
    {
        "phase": 7,
        "key": "zal3",
        "nr": "3",
        "title": "Karta praktyki zawodowej i oceny",
        "owner_role": "zopz",
        "owner_label": "Opiekun zakładowy",
        "hint": "ZOPZ uzupełnia kartę i ocenę, a UOPZ ją zatwierdza.",
    },
    {
        "phase": 8,
        "key": "zal5",
        "nr": "5",
        "title": "Kwestionariusz ankiety",
        "owner_role": "student",
        "owner_label": "Student",
        "hint": "Student ocenia przebieg zakończonej praktyki.",
    },
    {
        "phase": 9,
        "key": "zal8",
        "nr": "8",
        "title": "Protokół zaliczenia praktyki",
        "owner_role": "dziekanat",
        "owner_label": "Dziekanat",
        "hint": "Dziekanat wpisuje oceny i zamyka obieg praktyki.",
    },
)

OPTIONAL_EXPERIENCE_STEPS = (
    {
        "key": "zal4b",
        "nr": "4b",
        "title": "Wniosek o zaliczenie na podstawie doświadczenia zawodowego",
        "owner_label": "Student",
    },
    {
        "key": "zal4a",
        "nr": "4a",
        "title": "Merytoryczna ocena wniosku",
        "owner_label": "Opiekun uczelniany",
    },
)


def report_key(student):
    return "zal7a" if getattr(student, "study_mode", None) == "niestacjonarne" else "zal7"


def steps_for_student(student):
    steps = []
    selected_report = report_key(student)
    for definition in STANDARD_STEPS:
        step = dict(definition)
        if step["key"] == "report":
            step["key"] = selected_report
            step["nr"] = "7a" if selected_report == "zal7a" else "7"
            step["title"] = (
                "Sprawozdanie z praktyki (niestacjonarne)"
                if selected_report == "zal7a"
                else "Sprawozdanie z praktyki zawodowej"
            )
        steps.append(step)
    return steps


def overview_phases():
    phases = []
    for definition in STANDARD_STEPS:
        keys = (
            ["zal7", "zal7a"]
            if definition["key"] == "report"
            else [definition["key"]]
        )
        phases.append({
            "nr": definition["phase"],
            "label": f"Faza {definition['phase']}",
            "subtitle": definition["owner_label"],
            "keys": keys,
        })
    return phases


def step_states(student, statuses):
    result = []
    previous_complete = True
    for definition in steps_for_student(student):
        status = statuses.get(definition["key"])
        complete = status == "approved"
        state = "completed" if complete else ("current" if previous_complete else "locked")
        result.append({
            **definition,
            "status": status or "not_started",
            "complete": complete,
            "state": state,
            "unlocked": previous_complete,
        })
        previous_complete = previous_complete and complete
    return result


def step_access(student, statuses):
    return {step["key"]: step for step in step_states(student, statuses)}


def unmet_previous_steps(student, form_key, statuses):
    access = step_access(student, statuses)
    step = access.get(form_key)
    if step is None:
        if form_key in {"zal7", "zal7a"}:
            return [{"form_key": report_key(student), "reason": "wrong_report"}]
        return []
    if step["unlocked"]:
        return []
    unmet = []
    for candidate in step_states(student, statuses):
        if candidate["key"] == form_key:
            break
        if not candidate["complete"]:
            unmet.append({
                "form_key": candidate["key"],
                "nr": candidate["nr"],
                "title": candidate["title"],
                "required_status": "approved",
                "actual": candidate["status"],
            })
    return unmet


def practice_result(student, statuses, internship):
    final_complete = statuses.get("zal8") == "approved"
    grade = getattr(internship, "grade_k", None)
    if not final_complete:
        return {"code": "in_progress", "label": "Praktyka w toku"}
    if grade is not None and Decimal(str(grade)) >= Decimal("3"):
        return {"code": "passed", "label": "Praktyka zaliczona"}
    return {"code": "failed", "label": "Praktyka niezaliczona"}


_REQUIRED_FIELDS = {
    "zal9": (
        ("nazwa_instytucji", "nazwa instytucji"),
        ("termin_od", "data rozpoczęcia"),
        ("termin_do", "data zakończenia"),
        ("opiekun_imie_nazwisko", "dane opiekuna zakładowego"),
        ("opiekun_email", "e-mail opiekuna zakładowego"),
        ("upowazniont_imie_nazwisko", "osoba upoważniona"),
    ),
    "zal1": (
        ("nazwa_zakladu", "nazwa zakładu pracy"),
        ("adres_zakladu", "adres zakładu pracy"),
        ("data_start", "data rozpoczęcia"),
        ("data_end", "data zakończenia"),
        ("specjalnosc", "specjalność"),
    ),
    "zal2": (
        ("zaklad_pracy", "zakład pracy"),
        ("data_start", "data rozpoczęcia"),
        ("data_end", "data zakończenia"),
    ),
    "zal2a": (
        ("miejsce_praktyki", "miejsce praktyki"),
        ("data_start", "data rozpoczęcia"),
        ("data_end", "data zakończenia"),
    ),
    "zal3": (
        ("zaklad_pracy", "zakład pracy"),
        ("data_start", "data rozpoczęcia"),
        ("data_end", "data zakończenia"),
        ("ocena_zakladowa_param", "ocena zakładowa"),
        ("ocena_uczelniana_param", "ocena uczelniana"),
        ("ocena_sprawozdania", "ocena sprawozdania"),
    ),
    "zal7": (
        ("miejsce_praktyki", "miejsce praktyki"),
        ("charakterystyka", "charakterystyka zakładu"),
        ("opis_prac", "opis wykonanych prac"),
        ("wiedza_umiejetnosci", "opis zdobytej wiedzy i umiejętności"),
    ),
    "zal7a": (
        ("miejsce_praktyki", "miejsce praktyki"),
        ("charakterystyka", "charakterystyka zakładu"),
        ("opis_prac", "opis wykonanych prac"),
        ("wiedza_umiejetnosci", "opis zdobytej wiedzy i umiejętności"),
    ),
    "zal8": (
        ("ocena_s", "ocena sprawozdania"),
        ("ocena_u", "ocena uczelniana"),
        ("ocena_z", "ocena zakładowa"),
        ("ocena_e", "ocena egzaminu"),
        ("ocena_k", "ocena końcowa"),
    ),
}


def completion_errors(form_key, record):
    errors = [
        f"Uzupełnij pole: {label}."
        for field, label in _REQUIRED_FIELDS.get(form_key, ())
        if not str(record.get(field) or "").strip()
    ]
    if form_key == "zal2a":
        if not record.get("harmonogram"):
            errors.append("Dodaj co najmniej jedną pozycję harmonogramu.")
        if not any(
            str(item.get("dzial_prace") or "").strip()
            for item in record.get("efekty_plan", [])
        ):
            errors.append("Przypisz prace do efektów uczenia się.")
    elif form_key == "zal6":
        diary = record.get("dziennik") or []
        if not diary:
            errors.append("Dziennik musi zawierać co najmniej jeden wpis.")
        elif any(
            not str(entry.get("data") or "").strip()
            or not str(entry.get("opis") or "").strip()
            for entry in diary
        ):
            errors.append("Każdy wpis dziennika musi mieć datę i opis pracy.")
    elif form_key == "zal4":
        effects = record.get("efekty") or []
        if not effects or any(
            not str(effect.get("status") or "").strip()
            for effect in effects
        ):
            errors.append("Określ status wszystkich efektów uczenia się.")
    elif form_key == "zal5":
        answers = record.get("pytania") or []
        if len(answers) < 14 or any(
            not str(answer.get("odpowiedz") or "").strip()
            for answer in answers
        ):
            errors.append("Odpowiedz na wszystkie pytania ankiety.")
    return errors
