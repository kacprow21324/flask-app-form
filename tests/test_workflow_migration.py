import unittest
from unittest.mock import Mock, patch

from core import workflow_migration


class WorkflowMigrationTests(unittest.TestCase):
    def test_cleanup_is_blocked_when_statuses_differ(self):
        with (
            patch.object(
                workflow_migration,
                "synchronize_workflow_rows",
                return_value={"created": 0, "mismatches": [{"form_key": "zal1"}]},
            ),
            patch.object(workflow_migration, "_coll") as collection_factory,
        ):
            with self.assertRaises(RuntimeError):
                workflow_migration.remove_mongo_workflow_metadata()

        collection_factory.assert_not_called()

    def test_cleanup_unsets_only_workflow_fields(self):
        collection = Mock()
        collection.update_many.return_value.modified_count = 3
        collection.count_documents.return_value = 0

        with (
            patch.object(
                workflow_migration,
                "synchronize_workflow_rows",
                return_value={"created": 2, "mismatches": []},
            ),
            patch.object(workflow_migration, "_coll", return_value=collection),
        ):
            result = workflow_migration.remove_mongo_workflow_metadata()

        update = collection.update_many.call_args.args[1]
        self.assertEqual(set(update["$unset"]), {
            f"data.{field}"
            for field in workflow_migration.WORKFLOW_METADATA_FIELDS
        })
        self.assertEqual(update["$inc"], {"revision": 1})
        self.assertEqual(result, {"created": 2, "cleaned": 3, "remaining": 0})


if __name__ == "__main__":
    unittest.main()
