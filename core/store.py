"""
Magazyn treści formularzy (Zał. 1–9) w MongoDB.

Każdy formularz studenta jest osobnym dokumentem w kolekcji `practice_forms`:

    { "_id": "<nr_albumu>:<zal_key>",
      "album_number": "21001", "form_key": "zal6",
      "data": { ... pełna treść formularza ... },
      "updated_at": <datetime> }

Odczyty zbiorcze zachowują format dawnego pliku `studenci.json`:
`{nr_albumu: {zal_key: dane}}`. Zapisy i usunięcia zawsze dotyczą jednego
formularza albo jednego studenta, aby równoległe żądania nie nadpisywały
pozostałych dokumentów.
"""
import os
from datetime import datetime

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

_DEFAULT_URL = "mongodb://mongo:27017/ems"
_client = None
_collection = None

WORKFLOW_METADATA_FIELDS = {
    "_status",
    "_rejection_comment",
    "_rejection_by",
    "_approved_by",
    "_approved_role",
    "_approved_at",
}


def _coll():
    """Leniwe połączenie z MongoDB (jedno na proces)."""
    global _client, _collection
    if _collection is None:
        url = os.environ.get("MONGO_URL", _DEFAULT_URL)
        _client = MongoClient(url, serverSelectionTimeoutMS=5000)
        db = _client.get_default_database()  # nazwa bazy pochodzi ze ścieżki URL (…/ems)
        _collection = db["practice_forms"]
        _collection.create_index(
            [("album_number", 1), ("form_key", 1)], unique=True, name="uq_album_form")
    return _collection


def ping():
    """Sprawdza połączenie z MongoDB bez odczytu danych formularzy."""
    _coll().database.command("ping")


def _doc_id(album_number, form_key):
    return f"{album_number}:{form_key}"


def without_workflow_metadata(record):
    """Return form content without workflow metadata owned by MariaDB."""
    return {
        key: value
        for key, value in record.items()
        if key not in WORKFLOW_METADATA_FIELDS
    }


def load_data():
    """Zwraca {nr_albumu: {zal_key: dane}} – wszystkie formularze z Mongo."""
    data = {}
    for doc in _coll().find():
        data.setdefault(doc["album_number"], {})[doc["form_key"]] = doc.get("data", {})
    return data


def get_student_forms(album_number):
    """Zwraca wszystkie formularze jednego studenta."""
    forms = {}
    for doc in _coll().find({"album_number": album_number}):
        forms[doc["form_key"]] = doc.get("data", {})
    return forms


def get_form(album_number, form_key):
    """Zwraca treść jednego formularza albo None."""
    doc = _coll().find_one(
        {"_id": _doc_id(album_number, form_key)},
        {"data": 1},
    )
    return doc.get("data", {}) if doc else None


def get_form_revision(album_number, form_key):
    """Zwraca aktualną rewizję dokumentu; starsze dokumenty mają rewizję 0."""
    doc = _coll().find_one(
        {"_id": _doc_id(album_number, form_key)},
        {"revision": 1},
    )
    if not doc:
        return None
    return doc.get("revision", 0)


class ConcurrentUpdateError(RuntimeError):
    """Dokument został zmieniony od czasu jego odczytu."""


def save_form(album_number, form_key, record, expected_revision=None):
    """
    Atomowo zapisuje jeden formularz i zwiększa jego rewizję.

    `expected_revision` włącza optimistic locking. Brak zgodności oznacza,
    że inny proces zapisał dokument wcześniej i zgłaszany jest konflikt.
    """
    coll = _coll()
    document_id = _doc_id(album_number, form_key)
    values = {
        "album_number": album_number,
        "form_key": form_key,
        "data": without_workflow_metadata(record),
        "updated_at": datetime.utcnow(),
    }

    if expected_revision is None:
        doc = coll.find_one_and_update(
            {"_id": document_id},
            {"$set": values, "$inc": {"revision": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc["revision"]

    revision_filter = {"revision": expected_revision}
    if expected_revision == 0:
        revision_filter = {
            "$or": [{"revision": 0}, {"revision": {"$exists": False}}],
        }
    doc = coll.find_one_and_update(
        {"_id": document_id, **revision_filter},
        {"$set": values, "$inc": {"revision": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if doc:
        return doc["revision"]

    if expected_revision == 0:
        try:
            coll.insert_one({
                "_id": document_id,
                **values,
                "revision": 1,
            })
            return 1
        except DuplicateKeyError:
            pass
    raise ConcurrentUpdateError(
        f"Formularz {album_number}/{form_key} został zmieniony przez inny proces."
    )


def delete_form(album_number, form_key):
    """Usuwa wyłącznie wskazany formularz."""
    result = _coll().delete_one({"_id": _doc_id(album_number, form_key)})
    return result.deleted_count > 0


def delete_student_forms(album_number):
    """Usuwa wszystkie formularze jednego studenta i zwraca ich klucze."""
    coll = _coll()
    keys = [
        doc["form_key"]
        for doc in coll.find({"album_number": album_number}, {"form_key": 1})
    ]
    if keys:
        coll.delete_many({"album_number": album_number})
    return keys


def import_from_json(json_path):
    """Jednorazowy import z pliku studenci.json do Mongo (tylko gdy kolekcja pusta)."""
    import json
    coll = _coll()
    if coll.estimated_document_count() > 0:
        return 0
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0
    count = 0
    for album_number, forms in data.items():
        for form_key, record in forms.items():
            if not isinstance(record, dict):
                continue
            coll.update_one(
                {"_id": _doc_id(album_number, form_key)},
                {"$set": {
                    "album_number": album_number, "form_key": form_key,
                    "data": without_workflow_metadata(record),
                    "updated_at": datetime.utcnow(),
                }},
                upsert=True,
            )
            count += 1
    return count
