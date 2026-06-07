from datetime import date, datetime
import re

from core.models import Company, Internship, InternshipPart, User, db


ACADEMIC_YEAR_PATTERN = re.compile(r"^\d{4}/\d{4}$")
PART_STATUSES = {"planned", "active", "completed", "cancelled"}


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


def ensure_default_part(internship):
    if internship is None:
        return None
    part = (
        InternshipPart.query.filter_by(internship_id=internship.id)
        .order_by(InternshipPart.part_number)
        .first()
    )
    if part is not None:
        return part
    part = InternshipPart(
        internship=internship,
        part_number=1,
        name="Część 1",
        company_id=internship.company_id,
        uopz_id=internship.uopz_id,
        zopz_id=internship.zopz_id,
        start_date=internship.start_date,
        end_date=internship.end_date,
        planned_hours=internship.total_hours or 0,
        total_hours=internship.total_hours or 0,
        total_days=internship.total_days or 0,
        status=(
            internship.status
            if internship.status in {"active", "completed"}
            else "planned"
        ),
    )
    db.session.add(part)
    return part


def next_part_number(internship):
    highest = (
        db.session.query(db.func.max(InternshipPart.part_number))
        .filter(InternshipPart.internship_id == internship.id)
        .scalar()
    )
    return int(highest or 0) + 1


def sync_internship_totals(internship):
    active_parts = [
        part for part in internship.parts
        if part.status != "cancelled"
    ]
    internship.total_hours = sum(part.total_hours or 0 for part in active_parts)
    internship.total_days = sum(part.total_days or 0 for part in active_parts)
    starts = [part.start_date for part in active_parts if part.start_date]
    ends = [part.end_date for part in active_parts if part.end_date]
    internship.start_date = min(starts) if starts else None
    internship.end_date = max(ends) if ends else None
    if active_parts and all(part.status == "completed" for part in active_parts):
        internship.status = "completed"
    elif any(part.status == "active" for part in active_parts):
        internship.status = "active"
    elif active_parts:
        internship.status = "draft"
    else:
        internship.status = "draft"
    return internship


def save_internship_part(
    internship,
    *,
    part=None,
    name,
    company_name=None,
    start_date=None,
    end_date=None,
    planned_hours=0,
    total_hours=0,
    total_days=0,
    status="planned",
    uopz=None,
    zopz=None,
):
    name = str(name or "").strip()
    if not name:
        raise ValueError("Nazwa części praktyki jest wymagana.")
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start_date and start is None:
        raise ValueError("Nieprawidłowa data rozpoczęcia.")
    if end_date and end is None:
        raise ValueError("Nieprawidłowa data zakończenia.")
    if start and end and end < start:
        raise ValueError("Data zakończenia nie może być wcześniejsza od rozpoczęcia.")

    def nonnegative(value, label):
        try:
            parsed = int(str(value or 0).strip())
        except (TypeError, ValueError):
            raise ValueError(f"{label} musi być liczbą całkowitą.") from None
        if parsed < 0:
            raise ValueError(f"{label} nie może być ujemna.")
        return parsed

    if status not in PART_STATUSES:
        raise ValueError("Nieprawidłowy status części praktyki.")

    company = None
    company_name = str(company_name or "").strip()
    if company_name:
        company = Company.query.filter_by(name=company_name).first()
        if company is None:
            company = Company(name=company_name)
            db.session.add(company)
            db.session.flush()

    if part is None:
        part = InternshipPart(
            internship=internship,
            part_number=next_part_number(internship),
        )
        db.session.add(part)
    elif part.internship_id != internship.id:
        raise ValueError("Część nie należy do wskazanej praktyki.")

    part.name = name
    part.company_id = company.id if company else None
    part.start_date = start
    part.end_date = end
    part.planned_hours = nonnegative(planned_hours, "Planowana liczba godzin")
    part.total_hours = nonnegative(total_hours, "Zrealizowana liczba godzin")
    part.total_days = nonnegative(total_days, "Liczba dni")
    part.status = status
    part.uopz_id = getattr(uopz, "id", None)
    part.zopz_id = getattr(zopz, "id", None)
    db.session.flush()
    sync_internship_totals(internship)
    return part


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
        db.session.flush()

    part = ensure_default_part(internship)
    part_id = record.get("internship_part_id")
    if part_id:
        try:
            selected_part = db.session.get(InternshipPart, int(part_id))
        except (TypeError, ValueError):
            selected_part = None
        if selected_part is not None and selected_part.internship_id == internship.id:
            part = selected_part
    update_part_from_document = len(internship.parts) <= 1 or bool(part_id)

    company = _get_or_create_company(form_key, record) if form_key else None
    if company is not None:
        internship.company_id = company.id
        if update_part_from_document:
            part.company_id = company.id

    start = _parse_date(
        record.get("data_start") or record.get("termin_od") or record.get("okres_od")
    )
    end = _parse_date(
        record.get("data_end") or record.get("termin_do") or record.get("okres_do")
    )
    if start:
        internship.start_date = start
        if update_part_from_document:
            part.start_date = start
    if end:
        internship.end_date = end
        if update_part_from_document:
            part.end_date = end
    if record.get("nr_porozumienia"):
        internship.agreement_number = str(record["nr_porozumienia"]).strip()

    if form_key == "zal6" and update_part_from_document:
        entries = record.get("dziennik", [])
        part.total_days = len(entries)
        part.total_hours = sum(
            int(entry.get("godziny", 0) or 0)
            for entry in entries
            if str(entry.get("godziny", "")).strip().isdigit()
        )
    hours = record.get("liczba_godzin")
    if (
        hours
        and form_key != "zal6"
        and update_part_from_document
        and not part.total_hours
    ):
        try:
            part.total_hours = max(0, int(str(hours).strip()))
        except ValueError:
            pass
    if document_status == "approved" and form_key == "zal8":
        internship.status = "completed"
        for internship_part in internship.parts:
            if internship_part.status != "cancelled":
                internship_part.status = "completed"
    elif internship.status == "draft" and form_key:
        internship.status = "active"
        if part.status == "planned":
            part.status = "active"

    sync_internship_totals(internship)

    if commit:
        db.session.commit()
    return internship
