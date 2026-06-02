"""
Magazyn treści formularzy (Zał. 1–9) w MongoDB.

Każdy formularz studenta jest osobnym dokumentem w kolekcji `practice_forms`:

    { "_id": "<nr_albumu>:<zal_key>",
      "album_number": "21001", "form_key": "zal6",
      "data": { ... pełna treść formularza ... },
      "updated_at": <datetime> }

Moduł wystawia ten sam interfejs co dawny zapis w `studenci.json`
(`load_data()` / `save_data()`), zwracając zagnieżdżony słownik
`{nr_albumu: {zal_key: dane}}`, więc reszta aplikacji nie wymaga zmian.
"""
import os
from datetime import datetime

from pymongo import MongoClient

_DEFAULT_URL = "mongodb://mongo:27017/ems"
_client = None
_collection = None


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


def _doc_id(album_number, form_key):
    return f"{album_number}:{form_key}"


def load_data():
    """Zwraca {nr_albumu: {zal_key: dane}} – wszystkie formularze z Mongo."""
    data = {}
    for doc in _coll().find():
        data.setdefault(doc["album_number"], {})[doc["form_key"]] = doc.get("data", {})
    return data


def save_data(all_data):
    """
    Synchronizuje cały stan formularzy z Mongo: zapisuje obecne dokumenty
    i usuwa te, których już nie ma w `all_data` (obsługa kasowania załączników).
    """
    coll = _coll()
    present = set()
    for album_number, forms in all_data.items():
        for form_key, record in forms.items():
            if not isinstance(record, dict):
                continue
            coll.update_one(
                {"_id": _doc_id(album_number, form_key)},
                {"$set": {
                    "album_number": album_number,
                    "form_key": form_key,
                    "data": record,
                    "updated_at": datetime.utcnow(),
                }},
                upsert=True,
            )
            present.add(_doc_id(album_number, form_key))
    for doc in coll.find({}, {"_id": 1}):
        if doc["_id"] not in present:
            coll.delete_one({"_id": doc["_id"]})


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
                    "data": record, "updated_at": datetime.utcnow(),
                }},
                upsert=True,
            )
            count += 1
    return count
