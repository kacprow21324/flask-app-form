import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.internships import save_internship_part
from core.models import Internship, User, db


class InternshipPartTests(unittest.TestCase):
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

    def test_cancelled_parts_are_excluded_from_annual_totals(self):
        with self.app.app_context():
            student = User(
                email="parts-student@example.test",
                password_hash="unused",
                first_name="Jan",
                last_name="Testowy",
                role="student",
                album_number="22001",
            )
            db.session.add(student)
            db.session.flush()
            internship = Internship(
                student_id=student.id,
                academic_year="2025/2026",
            )
            db.session.add(internship)
            db.session.flush()

            save_internship_part(
                internship,
                name="Część pierwsza",
                total_hours=80,
                total_days=10,
                status="completed",
            )
            second = save_internship_part(
                internship,
                name="Część druga",
                total_hours=120,
                total_days=15,
                status="active",
            )
            self.assertEqual(internship.total_hours, 200)
            self.assertEqual(internship.total_days, 25)

            save_internship_part(
                internship,
                part=second,
                name=second.name,
                total_hours=120,
                total_days=15,
                status="cancelled",
            )
            self.assertEqual(internship.total_hours, 80)
            self.assertEqual(internship.total_days, 10)

            first = internship.parts[0]
            save_internship_part(
                internship,
                part=first,
                name=first.name,
                total_hours=80,
                total_days=10,
                status="cancelled",
            )
            self.assertEqual(internship.total_hours, 0)
            self.assertEqual(internship.total_days, 0)
            self.assertEqual(internship.status, "draft")

    def test_part_dates_must_be_ordered(self):
        with self.app.app_context():
            student = User(
                email="dates-student@example.test",
                password_hash="unused",
                first_name="Anna",
                last_name="Testowa",
                role="student",
                album_number="22002",
            )
            db.session.add(student)
            db.session.flush()
            internship = Internship(
                student_id=student.id,
                academic_year="2025/2026",
            )
            db.session.add(internship)
            db.session.flush()

            with self.assertRaisesRegex(ValueError, "wcześniejsza"):
                save_internship_part(
                    internship,
                    name="Nieprawidłowy termin",
                    start_date="2026-08-10",
                    end_date="2026-08-01",
                )


if __name__ == "__main__":
    unittest.main()
