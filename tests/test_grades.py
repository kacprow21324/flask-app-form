import os
import unittest
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.grades import (
    GradeValidationError,
    calculate_final_grade,
    require_approved_diary,
    store_final_grade,
)
from core.models import GradeCalculation, Internship, User, db


class GradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_weighted_grade_is_calculated_and_rounded_on_server(self):
        result = calculate_final_grade(
            grade_e="5",
            grade_s="4",
            grade_u="3",
            grade_z="2",
        )
        self.assertEqual(result["weighted_result"], Decimal("3.60"))
        self.assertEqual(result["final_grade"], Decimal("3.5"))

    def test_grade_components_must_be_complete_and_valid(self):
        with self.assertRaisesRegex(GradeValidationError, "brakuje"):
            calculate_final_grade(
                grade_e="5",
                grade_s="",
                grade_u="4",
                grade_z="4",
            )
        with self.assertRaises(GradeValidationError):
            calculate_final_grade(
                grade_e="2.7",
                grade_s="4",
                grade_u="4",
                grade_z="4",
            )

    def test_diary_must_be_approved(self):
        with self.assertRaisesRegex(GradeValidationError, "zatwierdzeniu dziennika"):
            require_approved_diary("pending")
        require_approved_diary("approved")

    def test_grade_is_stored_in_internship_and_history_without_duplicates(self):
        with self.app.app_context():
            student = User(
                email="grade-student@example.test",
                password_hash="unused",
                first_name="Jan",
                last_name="Oceniany",
                role="student",
                album_number="23001",
            )
            db.session.add(student)
            db.session.flush()
            internship = Internship(
                student_id=student.id,
                academic_year="2025/2026",
            )
            db.session.add(internship)
            db.session.flush()
            result = calculate_final_grade(
                grade_e="5",
                grade_s="5",
                grade_u="4",
                grade_z="4",
            )

            store_final_grade(internship, result)
            db.session.flush()
            store_final_grade(internship, result)
            db.session.flush()

            self.assertEqual(internship.grade_k, Decimal("4.5"))
            self.assertEqual(GradeCalculation.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
