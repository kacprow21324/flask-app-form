import unittest

from core.fsm import DocumentFSM, InvalidTransition


class DocumentFSMTests(unittest.TestCase):
    def test_all_supported_transitions(self):
        expected = {
            ("draft", "submit"): "pending",
            ("rejected", "submit"): "pending",
            ("pending", "approve"): "approved",
            ("pending", "reject"): "rejected",
            ("draft", "complete"): "approved",
        }
        for transition, target in expected.items():
            with self.subTest(transition=transition):
                self.assertEqual(DocumentFSM.transition(*transition), target)

    def test_terminal_and_invalid_transitions_are_rejected(self):
        for state, event in (
            ("approved", "submit"),
            ("approved", "reject"),
            ("draft", "approve"),
            ("rejected", "approve"),
        ):
            with self.subTest(state=state, event=event):
                with self.assertRaises(InvalidTransition):
                    DocumentFSM.transition(state, event)

    def test_role_permissions(self):
        self.assertTrue(DocumentFSM.role_can("student", "submit"))
        self.assertTrue(DocumentFSM.role_can("student", "complete"))
        self.assertFalse(DocumentFSM.role_can("student", "approve"))
        self.assertTrue(DocumentFSM.role_can("zopz", "reject"))
        self.assertFalse(DocumentFSM.role_can("unknown", "submit"))

    def test_prerequisites_report_missing_and_wrong_states(self):
        # zal9 nie ma już prerequisites (usunięte z obiegu)
        self.assertTrue(DocumentFSM.prerequisites_ok("zal9", {}))
        unmet = DocumentFSM.check_prerequisites(
            "zal8",
            {"zal3": "approved", "zal7": "pending"},
        )
        self.assertEqual(unmet, [{
            "form_key": "zal7",
            "required_status": "approved",
            "actual": "pending",
        }])
        self.assertTrue(DocumentFSM.prerequisites_ok(
            "zal8",
            {"zal3": "approved", "zal7": "approved"},
        ))


if __name__ == "__main__":
    unittest.main()
