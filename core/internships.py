from datetime import date, datetime
import re

from core.models import Company, Internship, User, db


ACADEMIC_YEAR_PATTERN = re.compile(r"^\d{4}/\d{4}$")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def current_academic_year(reference_date=None):
    today = reference_date or date.today()
    return (
        f"{today.year}/{today.year + 1}"
        if today.month >= 10
        else f"{today.year - 1}/{today.year}"
    )


def normalize_academic_year(value, *, default_current=True):
    year = str(value or "").strip().split()[0] if value else ""
    if not year:
        return current_academic_year() if default_current else None
    if not ACADEMIC_YEAR_PATTERN.fullmatch(year):
        return None
    start, end = (int(part) for part in year.split("/"))
    if end != start + 1:
        return None
    return year


def _academic_year(record=None):
    raw = (record or {}).get("rok_akademicki", "")
    if raw:
        normalized = normalize_academic_year(raw, default_current=False)
        if normalized:
            return normalized
    start = _parse_date(
        (record or {}).get("data_start")
        or (record or {}).get("termin_od")
        or (record or {}).get("okres_od")
    )
    if start:
        return (
            f"{start.year}/{start.year + 1}"
            if start.month >= 10
            else f"{start.year - 1}/{start.year}"
        )
    return current_academic_year()


def get_or_create_internship(student, academic_year):
    year = normalize_academic_year(academic_year, default_current=False)
    if student is None or student.role != "student" or year is None:
        return None
    internship = Internship.query.filter_by(
        student_id=student.id,
        academic_year=year,
    ).first()
    if internship is None:
        internship = Internship(student_id=student.id, academic_year=year)
        db.session.add(internship)
    return internship


def _company_values(form_key, record):
    mappings = {
        "zal1": (
            record.get("nazwa_zakladu"),
            record.get("nip_zakladu"),
            record.get("adres_zakladu"),
        ),
        "zal2": (record.get("zaklad_pracy"), None, None),
        "zal3": (record.get("zaklad_pracy"), None, None),
        "zal4b": (record.get("pracodawca"), None, record.get("adres_pracodawcy")),
        "zal6": (record.get("miejsce_praktyki"), None, None),
        "zal9": (record.get("nazwa_instytucji"), None, None),
    }
    return mappings.get(form_key, (None, None, None))


def _get_or_create_company(form_key, record):
    name, nip, address = _company_values(form_key, record)
    name = (name or "").strip()
    nip = (nip or "").strip() or None
    address = (address or "").strip() or None
    if not name:
        return None

    company = Company.query.filter_by(nip=nip).first() if nip else None
    if company is None:
        company = Company.query.filter_by(name=name).first()
    if company is None:
        company = Company(name=name, nip=nip)
        db.session.add(company)
        db.session.flush()

    if nip and not company.nip:
        company.nip = nip
    if address:
        company.address = address
    if form_key == "zal1":
        company.representative_name = (
            record.get("reprezentant_nazwisko", "").strip() or company.representative_name
        )
        company.representative_position = (
            record.get("reprezentant_stanowisko", "").strip()
            or company.representative_position
        )
    if form_key == "zal9":
        company.phone = record.get("opiekun_telefon", "").strip() or company.phone
        company.email = record.get("opiekun_email", "").strip() or company.email
    return company


def ensure_internship(
    album_number,
    form_key=None,
    record=None,
    *,
    document_status=None,
    commit=False,
):
    student = User.query.filter_by(role="student", album_number=str(album_number)).first()
    if student is None:
        return None

    record = record or {}
    year = _academic_year(record)
    has_period = bool(
        record.get("rok_akademicki")
        or record.get("data_start")
        or record.get("termin_od")
        or record.get("okres_od")
    )
    if has_period:
        internship = Internship.query.filter_by(
            student_id=student.id, academic_year=year,
        ).first()
    else:
        internship = (
            Internship.query.filter_by(student_id=student.id)
            .order_by(Internship.updated_at.desc(), Internship.id.desc())
            .first()
        )
    if internship is None:
        internship = get_or_create_internship(student, year)

    company = _get_or_create_company(form_key, record) if form_key else None
    if company is not None:
        internship.company_id = company.id

    start = _parse_date(
        record.get("data_start") or record.get("termin_od") or record.get("okres_od")
    )
    end = _parse_date(
        record.get("data_end") or record.get("termin_do") or record.get("okres_do")
    )
    if start:
        internship.start_date = start
    if end:
        internship.end_date = end
    if record.get("nr_porozumienia"):
        internship.agreement_number = str(record["nr_porozumienia"]).strip()

    if form_key == "zal6":
        entries = record.get("dziennik", [])
        internship.total_days = len(entries)
        internship.total_hours = sum(
            int(entry.get("godziny", 0) or 0)
            for entry in entries
            if str(entry.get("godziny", "")).strip().isdigit()
        )
    hours = record.get("liczba_godzin")
    if hours and form_key != "zal6" and not internship.total_hours:
        try:
            internship.total_hours = max(0, int(str(hours).strip()))
        except ValueError:
            pass
    if document_status == "approved" and form_key == "zal8":
        internship.status = "completed"
    elif internship.status == "draft" and form_key:
        internship.status = "active"

    if commit:
        db.session.commit()
    return internship
