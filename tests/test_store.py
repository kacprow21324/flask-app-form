import unittest
from unittest.mock import Mock, patch

from core import store


class StoreTests(unittest.TestCase):
    def test_save_form_updates_only_requested_document(self):
        collection = Mock()
        collection.find_one_and_update.return_value = {"revision": 4}

        with patch("core.store._coll", return_value=collection):
            revision = store.save_form("21001", "zal6", {"opis": "test"})

        self.assertEqual(revision, 4)
        query, update = collection.find_one_and_update.call_args.args
        self.assertEqual(query, {"_id": "21001:zal6"})
        self.assertEqual(update["$set"]["album_number"], "21001")
        self.assertEqual(update["$set"]["form_key"], "zal6")
        self.assertEqual(update["$set"]["data"], {"opis": "test"})
        self.assertEqual(update["$inc"], {"revision": 1})

    def test_save_form_removes_workflow_metadata(self):
        collection = Mock()
        collection.find_one_and_update.return_value = {"revision": 2}
        record = {
            "opis": "treść",
            "_status": "approved",
            "_rejection_comment": "stary komentarz",
            "_field_comments": [{"field": "opis", "note": "uzupełnij"}],
        }

        with patch("core.store._coll", return_value=collection):
            store.save_form("21001", "zal7", record)

        saved = collection.find_one_and_update.call_args.args[1]["$set"]["data"]
        self.assertNotIn("_status", saved)
        self.assertNotIn("_rejection_comment", saved)
        self.assertEqual(saved["_field_comments"], record["_field_comments"])

    def test_save_form_detects_revision_conflict(self):
        collection = Mock()
        collection.find_one_and_update.return_value = None

        with patch("core.store._coll", return_value=collection):
            with self.assertRaises(store.ConcurrentUpdateError):
                store.save_form(
                    "21001",
                    "zal6",
                    {"opis": "nowsza wersja"},
                    expected_revision=3,
                )

        collection.insert_one.assert_not_called()

    def test_save_new_form_with_expected_zero_revision(self):
        collection = Mock()
        collection.find_one_and_update.return_value = None

        with patch("core.store._coll", return_value=collection):
            revision = store.save_form(
                "21001",
                "zal1",
                {"pole": "wartosc"},
                expected_revision=0,
            )

        self.assertEqual(revision, 1)
        inserted = collection.insert_one.call_args.args[0]
        self.assertEqual(inserted["_id"], "21001:zal1")
        self.assertEqual(inserted["revision"], 1)

    def test_delete_form_does_not_delete_other_documents(self):
        collection = Mock()
        collection.delete_one.return_value.deleted_count = 1

        with patch("core.store._coll", return_value=collection):
            deleted = store.delete_form("21001", "zal2")

        self.assertTrue(deleted)
        collection.delete_one.assert_called_once_with({"_id": "21001:zal2"})
        collection.delete_many.assert_not_called()


if __name__ == "__main__":
    unittest.main()
