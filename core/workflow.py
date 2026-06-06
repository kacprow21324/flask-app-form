"""
Warstwa obiegu dokumentów oparta na bazie danych.

Status każdego dokumentu (album + formularz) oraz pełny dziennik zdarzeń
(kto/kiedy/co) są zapisywane w MariaDB w tabelach `document_workflow`
i `document_log`. Treść formularzy nadal jest w `data/studenci.json`, ale
to baza jest źródłem prawdy dla kolejek recenzentów i historii.

Funkcje są bezpieczne do wołania spoza kontekstu żądania (actor opcjonalny).

Przejścia stanów realizowane przez DocumentFSM (core.fsm).
"""
from flask_login import current_user

from core.models import db, DocumentWorkflow, DocumentLog
from core.fsm import DocumentFSM, InvalidTransition
from core.audit import log_action


def _actor():
    """Zwraca (id, imię i nazwisko, rola) zalogowanego użytkownika lub (None, 'system', None)."""
    try:
        if current_user and current_user.is_authenticated:
            return current_user.id, current_user.full_name, current_user.role
    except Exception:
        pass
    return None, "system", None


def log_event(album_number, form_key, action, comment=None):
    """Dopisuje wpis do dziennika zdarzeń (nie commit-uje samodzielnie)."""
    aid, aname, arole = _actor()
    db.session.add(DocumentLog(
        album_number=album_number, form_key=form_key, action=action,
        actor_id=aid, actor_name=aname, actor_role=arole,
        comment=comment,
    ))


def set_status(album_number, form_key, status, *, reviewer_role=None,
               rejection_comment=None, rejection_by=None, action=None,
               log_comment=None):
    """
    Zapisuje stan dokumentu w bazie i dopisuje zdarzenie do dziennika.

    `action` to etykieta zdarzenia (np. 'submitted'); jeśli pominięta, używany
    jest sam `status`. Zwraca obiekt DocumentWorkflow.
    """
    wf = DocumentWorkflow.query.filter_by(
        album_number=album_number, form_key=form_key).first()
    old_status = wf.status if wf is not None else None
    if wf is None:
        wf = DocumentWorkflow(album_number=album_number, form_key=form_key)
        db.session.add(wf)
    wf.status = status
    if reviewer_role is not None:
        wf.reviewer_role = reviewer_role
    wf.rejection_comment = rejection_comment
    wf.rejection_by = rejection_by
    log_event(album_number, form_key, action or status,
              comment=log_comment if log_comment is not None else rejection_comment)
    audit_action = {
        "created": "create",
        "updated": "update",
    }.get(action or status, action or status)
    log_action(
        audit_action,
        "document",
        f"{album_number}/{form_key}",
        before={"status": old_status},
        after={"status": status, "reviewer_role": reviewer_role},
    )
    db.session.commit()
    return wf


def delete_doc(album_number, form_key):
    """Usuwa stan obiegu dokumentu i zapisuje zdarzenie usunięcia."""
    DocumentWorkflow.query.filter_by(
        album_number=album_number, form_key=form_key).delete()
    log_event(album_number, form_key, "deleted")
    log_action("delete", "document", f"{album_number}/{form_key}")
    db.session.commit()


def get_logs(album_number, form_key=None, limit=200):
    """Zwraca listę zdarzeń (najnowsze pierwsze) dla studenta lub konkretnego dokumentu."""
    q = DocumentLog.query.filter_by(album_number=album_number)
    if form_key:
        q = q.filter_by(form_key=form_key)
    return q.order_by(DocumentLog.created_at.desc(), DocumentLog.id.desc()).limit(limit).all()


def do_transition(album_number: str, form_key: str, event: str,
                  reviewer_role=None, comment=None):
    """
    Wykonuje przejście maszyny stanowej dla dokumentu.

    Pobiera aktualny stan z DocumentWorkflow, waliduje przejście przez FSM,
    zapisuje nowy stan i zdarzenie w dzienniku.

    Rzuca InvalidTransition jeśli przejście niedozwolone.
    Zwraca nowy obiekt DocumentWorkflow.
    """
    wf = DocumentWorkflow.query.filter_by(
        album_number=album_number, form_key=form_key).first()
    current_state = wf.status if wf else 'draft'

    new_state = DocumentFSM.transition(current_state, event)  # rzuca InvalidTransition

    _, actor_name, _ = _actor()
    return set_status(
        album_number, form_key, new_state,
        reviewer_role=reviewer_role,
        rejection_comment=comment if new_state == "rejected" else None,
        rejection_by=actor_name if new_state == "rejected" else None,
        action=event,
        log_comment=comment,
    )


def get_document(album_number: str, form_key: str):
    """Return the workflow row for one document, or None."""
    return DocumentWorkflow.query.filter_by(
        album_number=album_number,
        form_key=form_key,
    ).first()


def get_status(album_number: str, form_key: str, default="draft") -> str:
    """Return the authoritative document status from MariaDB."""
    row = get_document(album_number, form_key)
    return row.status if row is not None else default


def get_statuses(album_number: str) -> dict:
    """Zwraca słownik {form_key: status} dla wszystkich dokumentów studenta z bazy."""
    rows = DocumentWorkflow.query.filter_by(album_number=album_number).all()
    return {r.form_key: r.status for r in rows}
