VALID_GENDERS = {"M", "K"}


def normalize_gender(value):
    normalized = str(value or "").strip().upper()
    return normalized if normalized in VALID_GENDERS else None


def infer_gender(first_name):
    first = str(first_name or "").strip().split()[0].lower()
    male_a_exceptions = {"kuba", "seba", "bonawentura", "barnaba", "kosma"}
    if first.endswith("a") and first not in male_a_exceptions:
        return "K"
    return "M"


def gender_for_student(student, record=None):
    explicit = normalize_gender(
        getattr(student, "gender", None)
        or (record or {}).get("gender")
    )
    if explicit:
        return explicit
    first_name = getattr(student, "first_name", None)
    if not first_name:
        first_name = (record or {}).get("imie_nazwisko", "")
    return infer_gender(first_name)
