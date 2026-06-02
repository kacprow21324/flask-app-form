"""
Walidacja danych formularzy – jedno źródło prawdy dla serwera.
Klient (static/js/form-validate.js) odzwierciedla te same reguły dla podglądu
„na bieżąco", ale to TE funkcje decydują o przyjęciu danych.

Każda funkcja zwraca (ok: bool, msg: str) – msg jest pusty gdy ok=True.
"""
from datetime import datetime

# Minimalna długość opisu wpisu dziennika (Zał. 6)
DIARY_MIN_LEN = 100

_NAME_EXTRA = "-'"  # dozwolone znaki niełacińskie w nazwisku poza literami


def is_valid_full_name(v):
    """Imię i nazwisko: ≥2 wyrazy, każdy ≥2 znaki, tylko litery (też polskie), '-' lub apostrof."""
    v = (v or "").strip()
    if not v:
        return False, "Pole jest wymagane."
    tokens = v.split()
    if len(tokens) < 2:
        return False, "Podaj imię i nazwisko (co najmniej dwa wyrazy oddzielone spacją)."
    for t in tokens:
        if len(t) < 2:
            return False, "Każdy człon musi mieć co najmniej 2 znaki."
        if not all(ch.isalpha() or ch in _NAME_EXTRA for ch in t):
            return False, "Imię i nazwisko może zawierać tylko litery, spacje, łącznik i apostrof (bez cyfr)."
    return True, ""


def is_valid_album(v):
    """Numer albumu: same cyfry, 4–6 znaków."""
    v = (v or "").strip()
    if not v:
        return False, "Pole jest wymagane."
    if not v.isdigit():
        return False, "Numer albumu może zawierać tylko cyfry."
    if not (4 <= len(v) <= 6):
        return False, "Numer albumu powinien mieć od 4 do 6 cyfr."
    return True, ""


def validate_nip(v, *, required=False):
    """NIP: 10 cyfr (separatory dozwolone) + poprawna suma kontrolna."""
    raw = (v or "").strip()
    if not raw:
        return (False, "Pole jest wymagane.") if required else (True, "")
    digits = raw.replace("-", "").replace(" ", "")
    if not digits.isdigit() or len(digits) != 10:
        return False, "NIP musi składać się z 10 cyfr."
    weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    checksum = sum(int(d) * w for d, w in zip(digits, weights)) % 11
    if checksum == 10 or checksum != int(digits[9]):
        return False, "Nieprawidłowy NIP (błędna suma kontrolna)."
    return True, ""


def is_valid_date(v, *, required=False):
    """Data w formacie RRRR-MM-DD."""
    v = (v or "").strip()
    if not v:
        return (False, "Pole jest wymagane.") if required else (True, "")
    try:
        datetime.strptime(v, "%Y-%m-%d")
        return True, ""
    except ValueError:
        return False, "Nieprawidłowa data (format RRRR-MM-DD)."


def validate_date_range(start, end):
    """Data zakończenia nie może być wcześniejsza niż rozpoczęcia."""
    s, e = (start or "").strip(), (end or "").strip()
    if not s or not e:
        return True, ""
    try:
        ds = datetime.strptime(s, "%Y-%m-%d")
        de = datetime.strptime(e, "%Y-%m-%d")
    except ValueError:
        return False, "Nieprawidłowy format daty (RRRR-MM-DD)."
    if de < ds:
        return False, "Data zakończenia musi być późniejsza niż data rozpoczęcia."
    return True, ""


def validate_diary_opis(v):
    """Opis wpisu dziennika: tylko minimalna długość."""
    v = (v or "").strip()
    if not v:
        return False, "Opis jest wymagany."
    if len(v) < DIARY_MIN_LEN:
        return False, f"Opis za krótki (min. {DIARY_MIN_LEN} znaków, jest {len(v)})."
    return True, ""
