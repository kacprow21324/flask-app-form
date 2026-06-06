import unittest
from types import SimpleNamespace

from core.internships import normalize_academic_year
from core.progress import summarize_progress


class ProgressTests(unittest.TestCase):
    def test_progress_counts_documents_and_internship_values(self):
        rows = [
            SimpleNamespace(status="approved", reviewer_role="uopz"),
            SimpleNamespace(status="pending", reviewer_role="uopz"),
            SimpleNamespace(status="rejected", reviewer_role="zopz"),
            SimpleNamespace(status="draft", reviewer_role=None),
        ]
        internship = SimpleNamespace(total_hours=480, total_days=60)

        result = summarize_progress(
            rows,
            total_documents=8,
            internship=internship,
            reviewer_role="uopz",
        )

        self.assertEqual(result["started"], 4)
        self.assertEqual(result["approved"], 1)
        self.assertEqual(result["pending_for_role"], 1)
        self.assertEqual(result["started_percent"], 50)
        self.assertEqual(result["hours_percent"], 50)
        self.assertEqual(result["days_percent"], 50)

    def test_academic_year_validation_rejects_invalid_ranges(self):
        self.assertEqual(
            normalize_academic_year("2025/2026", default_current=False),
            "2025/2026",
        )
        self.assertIsNone(
            normalize_academic_year("2025/2027", default_current=False),
        )
        self.assertIsNone(
            normalize_academic_year("not-a-year", default_current=False),
        )


if __name__ == "__main__":
    unittest.main()
