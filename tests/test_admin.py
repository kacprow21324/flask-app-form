import io
import os
import re
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.admin import (
    CSVImportError,
    import_students_csv,
    parse_student_csv,
    progress_report_csv,
    students_export_csv,
)
from core.models import Internship, User, db
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash


class AdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app
        cls.app.config.update(TESTING=True, SERVER_NAME="localhost")

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.admin = self._user(
                "panel-admin@example.test", "admin",
            )
            self.dean = self._user(
                "panel-dean@example.test", "dziekanat",
            )
            self.uopz = self._user(
                "panel-uopz@example.test", "uopz",
            )
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @staticmethod
    def _user(email, role, album_number=None):
        user = User(
            email=email,
            password_hash=generate_password_hash("TestPassword123!"),
            first_name=role,
            last_name="Panel",
            role=role,
            album_number=album_number,
            is_active=1,
        )
        db.session.add(user)
        return user

    def login(self, email):
        response = self.client.get("/login")
        token = re.search(
            rb'name="_csrf_token" value="([^"]+)"',
            response.data,
        ).group(1).decode()
        return self.client.post("/login", data={
            "email": email,
            "password": "TestPassword123!",
            "_csrf_token": token,
        })

    def test_admin_panel_access(self):
        self.assertEqual(self.login("panel-uopz@example.test").status_code, 302)
        self.assertEqual(self.client.get("/administracja/").status_code, 403)

        self.client = self.app.test_client()
        self.assertEqual(self.login("panel-dean@example.test").status_code, 302)
        self.assertEqual(self.client.get("/administracja/").status_code, 200)

    def test_csv_import_creates_and_updates_students(self):
        csv_content = (
            "email;first_name;last_name;album_number;speciality;"
            "study_mode;gender;semester;study_year\n"
            "student.one@example.test;Jan;Kowalski;26001;ASiSK;"
            "stacjonarne;M;6;3\n"
        ).encode("utf-8")
        with self.app.app_context():
            result = import_students_csv(FileStorage(
                stream=io.BytesIO(csv_content),
                filename="students.csv",
            ))
            db.session.commit()
            self.assertEqual(result, {"created": 1, "updated": 0, "total": 1})
            student = User.query.filter_by(album_number="26001").one()
            self.assertEqual(student.first_name, "Jan")

            updated_content = csv_content.replace(b"Jan", b"Janusz")
            result = import_students_csv(FileStorage(
                stream=io.BytesIO(updated_content),
                filename="students.csv",
            ))
            db.session.commit()
            self.assertEqual(result["updated"], 1)
            self.assertEqual(student.first_name, "Janusz")

    def test_csv_import_rejects_entire_invalid_file(self):
        content = (
            "email;first_name;last_name;album_number\n"
            "bad-email;Jan;Kowalski;26001\n"
            "valid@example.test;Anna;Nowak;abc\n"
        ).encode("utf-8")
        with self.app.app_context():
            before = User.query.count()
            with self.assertRaises(CSVImportError):
                import_students_csv(FileStorage(
                    stream=io.BytesIO(content),
                    filename="invalid.csv",
                ))
            self.assertEqual(User.query.count(), before)

    def test_progress_report_contains_internship_totals(self):
        with self.app.app_context():
            student = self._user(
                "report-student@example.test",
                "student",
                "26002",
            )
            db.session.flush()
            db.session.add(Internship(
                student_id=student.id,
                academic_year="2025/2026",
                total_hours=240,
                total_days=30,
                status="active",
            ))
            db.session.commit()
            report = progress_report_csv("2025/2026").decode("utf-8-sig")
            self.assertIn("26002", report)
            self.assertIn(";240;30;", report)

    def test_student_export_is_compatible_with_import(self):
        with self.app.app_context():
            student = self._user(
                "21255@student.ans-elblag.pl",
                "student",
                "21255",
            )
            student.speciality = "ASiSK"
            student.study_mode = "stacjonarne"
            student.gender = "M"
            student.semester = "6"
            student.study_year = "3"
            db.session.commit()

            rows = parse_student_csv(FileStorage(
                stream=io.BytesIO(students_export_csv()),
                filename="studenci.csv",
            ))
            exported = next(
                row for row in rows if row["album_number"] == "21255"
            )
            self.assertEqual(exported["email"], student.email)
            self.assertEqual(exported["study_year"], "3")
            self.assertEqual(exported["gender"], "M")


if __name__ == "__main__":
    unittest.main()
