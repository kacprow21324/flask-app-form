"""
Maszyna stanowa obiegu dokumentów ANS Elbląg.

Stany pojedynczego dokumentu:

    draft ──submit──► pending ──approve──► approved
                       │
                     reject
                       │
                    rejected ──submit──► pending   (auto przy edycji)

Klasa DocumentFSM definiuje:
  - dozwolone przejścia stanów (twarde — blokują nieprawidłowe akcje)
  - przejścia dokumentów wymagających recenzji i dokumentów kończonych
    bezpośrednio przez ich autora
"""

# ── Wyjątki ────────────────────────────────────────────────────────────────────

class FSMError(Exception):
    """Bazowy wyjątek maszyny stanowej."""

class InvalidTransition(FSMError):
    def __init__(self, state, event):
        super().__init__(
            f"Niedozwolone przejście: stan='{state}' zdarzenie='{event}'. "
            f"Dostępne: {DocumentFSM.available_events(state)}"
        )

class GuardFailed(FSMError):
    """Próba wykonania przejścia przez nieuprawnioną rolę."""


# ── Maszyna stanowa ────────────────────────────────────────────────────────────

class DocumentFSM:
    """
    Finite State Machine dla obiegu dokumentu.
    Użycie:
        new_state = DocumentFSM.transition('draft', 'submit')
        unmet = DocumentFSM.check_prerequisites('zal8', statuses_dict)
    """

    # Wszystkie stany
    STATES = ('draft', 'pending', 'approved', 'rejected')

    # (stan_początkowy, zdarzenie) → stan_końcowy
    TRANSITIONS: dict[tuple[str, str], str] = {
        ('draft',    'submit'):  'pending',
        ('rejected', 'submit'):  'pending',   # auto po poprawieniu odrzuconego
        ('pending',  'approve'): 'approved',
        ('pending',  'reject'):  'rejected',
        ('draft',    'complete'): 'approved',
    }

    # Rola → dozwolone zdarzenia (pusty set = wszyscy)
    ROLE_EVENTS: dict[str, set[str]] = {
        'student':   {'submit', 'complete'},
        'uopz':      {'submit', 'approve', 'reject', 'complete'},
        'zopz':      {'submit', 'approve', 'reject', 'complete'},
        'dziekanat': {'submit', 'approve', 'reject', 'complete'},
        'admin':     {'submit', 'approve', 'reject', 'complete'},
    }

    # Zależności fazowe: klucz = formularz, wartość = lista (form_key, wymagany_status)
    # To są MIĘKKIE wymagania — aplikacja pokazuje ostrzeżenie, ale nie blokuje.
    PREREQUISITES: dict[str, list[tuple[str, str]]] = {
        # Faza 1A
        'zal3':  [('zal1', 'approved')],                  # Karta praktyki po Porozumieniu
        # Faza 1B
        'zal4a': [('zal4b', 'pending')],                  # Ocena po złożeniu Wniosku
        # Faza 2
        'zal6':  [('zal2a', 'approved')],                 # Dziennik po zatwierdzeniu Programu
        # Faza 3
        'zal7':  [('zal6', 'approved')],                  # Sprawozdanie po zatwierdzeniu Dziennika
        'zal7a': [('zal4b', 'approved')],                 # Sprawozdanie SN po Wniosku
        # Faza 4
        'zal8':  [('zal3', 'approved'), ('zal7', 'approved')],
    }

    # Opis ludzki każdego zdarzenia
    EVENT_LABELS: dict[str, str] = {
        'submit':  'Wyślij do zatwierdzenia',
        'approve': 'Zatwierdź',
        'reject':  'Odrzuć',
        'complete': 'Zakończ etap',
    }

    # Opis ludzki każdego stanu
    STATE_LABELS: dict[str, str] = {
        'draft':    'Szkic',
        'pending':  'Oczekuje',
        'approved': 'Zatwierdzone',
        'rejected': 'Odrzucone',
    }

    # ── Metody klasowe ─────────────────────────────────────────────────────────

    @classmethod
    def transition(cls, state: str, event: str) -> str:
        """
        Wykonuje przejście i zwraca nowy stan.
        Rzuca InvalidTransition jeśli przejście jest niedozwolone.
        """
        key = (state, event)
        if key not in cls.TRANSITIONS:
            raise InvalidTransition(state, event)
        return cls.TRANSITIONS[key]

    @classmethod
    def can_transition(cls, state: str, event: str) -> bool:
        """Zwraca True jeśli przejście jest dozwolone ze stanu state."""
        return (state, event) in cls.TRANSITIONS

    @classmethod
    def available_events(cls, state: str) -> list[str]:
        """Lista zdarzeń dostępnych z danego stanu."""
        return [ev for (s, ev) in cls.TRANSITIONS if s == state]

    @classmethod
    def role_can(cls, role: str, event: str) -> bool:
        """Sprawdza czy rola może wywołać zdarzenie."""
        allowed = cls.ROLE_EVENTS.get(role, set())
        return event in allowed

    @classmethod
    def check_prerequisites(cls, zal_key: str, statuses: dict) -> list[dict]:
        """
        Sprawdza zależności fazowe.
        Zwraca listę niespełnionych warunków jako słowniki:
          {'form_key': 'zal6', 'required_status': 'approved', 'actual': 'draft'}
        Pusta lista = wszystkie warunki spełnione.
        """
        unmet = []
        for req_key, req_status in cls.PREREQUISITES.get(zal_key, []):
            actual = statuses.get(req_key)
            if actual != req_status:
                unmet.append({
                    'form_key': req_key,
                    'required_status': req_status,
                    'actual': actual or 'nie_wypełniony',
                })
        return unmet

    @classmethod
    def prerequisites_ok(cls, zal_key: str, statuses: dict) -> bool:
        """True jeśli wszystkie zależności fazowe są spełnione."""
        return len(cls.check_prerequisites(zal_key, statuses)) == 0
