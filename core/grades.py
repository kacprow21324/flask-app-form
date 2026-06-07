from decimal import Decimal, InvalidOperation
import re

from core.models import GradeCalculation, db


FORMULA_VERSION = "K-0.4E-0.1S-0.2U-0.3Z-v1"
WEIGHTS = {
    "e": Decimal("0.4"),
    "s": Decimal("0.1"),
    "u": Decimal("0.2"),
    "z": Decimal("0.3"),
}
ALLOWED_GRADES = {
    Decimal("2"),
    Decimal("3"),
    Decimal("3.5"),
    Decimal("4"),
    Decimal("4.5"),
    Decimal("5"),
}


class GradeValidationError(ValueError):
    pass


def parse_grade(value):
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None
    numeric_text = text if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text) else None
    if numeric_text is None:
        match = re.search(r"\(([2-5](?:\.5)?)\)", text)
        if not match:
            raise GradeValidationError(f"Nieprawidłowa ocena: {value}.")
        numeric_text = match.group(1)
    try:
        grade = Decimal(numeric_text)
    except InvalidOperation:
        raise GradeValidationError(f"Nieprawidłowa ocena: {value}.") from None
    if grade not in ALLOWED_GRADES:
        raise GradeValidationError(
            "Ocena musi należeć do skali: 2, 3, 3.5, 4, 4.5, 5."
        )
    return grade


def require_approved_diary(status):
    if status != "approved":
        raise GradeValidationError(
            "Ocena końcowa może zostać obliczona dopiero po zatwierdzeniu dziennika praktyki."
        )


def round_final_grade(weighted_result):
    if weighted_result < Decimal("2.75"):
        return Decimal("2")
    if weighted_result < Decimal("3.25"):
        return Decimal("3")
    if weighted_result < Decimal("3.75"):
        return Decimal("3.5")
    if weighted_result < Decimal("4.25"):
        return Decimal("4")
    if weighted_result < Decimal("4.75"):
        return Decimal("4.5")
    return Decimal("5")


def calculate_final_grade(*, grade_e, grade_s, grade_u, grade_z):
    grades = {
        "e": parse_grade(grade_e),
        "s": parse_grade(grade_s),
        "u": parse_grade(grade_u),
        "z": parse_grade(grade_z),
    }
    present = {key for key, value in grades.items() if value is not None}
    if not present:
        return None
    if len(present) != len(grades):
        missing = ", ".join(key.upper() for key in grades if grades[key] is None)
        raise GradeValidationError(
            f"Do obliczenia oceny końcowej brakuje składników: {missing}."
        )
    weighted = sum(grades[key] * WEIGHTS[key] for key in grades)
    return {
        "grades": grades,
        "weighted_result": weighted.quantize(Decimal("0.01")),
        "final_grade": round_final_grade(weighted),
    }


def grade_to_text(value):
    if value is None:
        return ""
    decimal_value = Decimal(value)
    if decimal_value == decimal_value.to_integral():
        return str(decimal_value.quantize(Decimal("1")))
    return str(decimal_value.normalize())


def store_final_grade(internship, calculation, *, actor=None):
    if internship is None or calculation is None:
        return None
    grades = calculation["grades"]
    internship.grade_e = grades["e"]
    internship.grade_s = grades["s"]
    internship.grade_u = grades["u"]
    internship.grade_z = grades["z"]
    internship.grade_k = calculation["final_grade"]

    latest = (
        GradeCalculation.query.filter_by(internship_id=internship.id)
        .order_by(GradeCalculation.id.desc())
        .first()
    )
    values = (
        grades["e"],
        grades["s"],
        grades["u"],
        grades["z"],
        calculation["weighted_result"],
        calculation["final_grade"],
    )
    if latest is not None:
        latest_values = (
            latest.grade_e,
            latest.grade_s,
            latest.grade_u,
            latest.grade_z,
            latest.weighted_result,
            latest.final_grade,
        )
        if latest_values == values and latest.formula_version == FORMULA_VERSION:
            return latest

    history = GradeCalculation(
        internship=internship,
        grade_e=grades["e"],
        grade_s=grades["s"],
        grade_u=grades["u"],
        grade_z=grades["z"],
        weighted_result=calculation["weighted_result"],
        final_grade=calculation["final_grade"],
        formula_version=FORMULA_VERSION,
        calculated_by=getattr(actor, "id", None),
    )
    db.session.add(history)
    return history
