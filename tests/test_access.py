import os
import re
import tempfile
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
import core.web as web_module
from core.documents import archive_pdf
from core.models import GeneratedDocument
from core.models import Attachment, Internship, InternshipPart, User, db
from core.internships import current_academic_year, ensure_internship
from werkzeug.security import generate_password_hash


class AccessControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app
        cls.app.config.update(TESTING=True, SERVER_NAME="localhost")
        with cls.app.app_context():
            db.create_all()
            cls.student_a = cls._user(
                "student-a@example.test", "student", "21001",
            )
            cls.student_b = cls._user(
                "student-b@example.test", "student", "21002",
            )
            cls.uopz = cls._user("uopz@example.test", "uopz")
            cls.zopz = cls._user("zopz@example.test", "zopz")
            cls.dziekanat = cls._user("dziekanat@example.test", "dziekanat")
            cls.admin = cls._user("admin@example.test", "admin")
            db.session.flush()
            db.session.add(Attachment(
                key="zal1",
                nr="1",
                title="Test attachment",
                reviewer_role="uopz",
                reviewer_label="UOPZ",
                sort_order=1,
            ))
            cls.admin_id = cls.admin.id
            db.session.add(Internship(
                student_id=cls.student_a.id,
                uopz_id=cls.uopz.id,
                academic_year="2025/2026",
            ))
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()

    @classmethod
    def _user(cls, email, role, album_number=None):
        user = User(
            email=email,
            first_name=role,
            last_name="Test",
            role=role,
            album_number=album_number,
            is_active=1,
        )
        user.password_hash = generate_password_hash("TestPassword123!")
        db.session.add(user)
        return user

    def setUp(self):
        self.client = self.app.test_client()
        self.forms = {
            "21001": {"zal1": {"imie_nazwisko": "Student A"}},
            "21002": {"zal1": {"imie_nazwisko": "Student B"}},
        }
        self.load_data_patch = patch.object(
            web_module, "load_data", return_value=self.forms,
        )
        self.load_data_patch.start()

    def tearDown(self):
        self.load_data_patch.stop()

    def login(self, email, client=None):
        client = client or self.client
        response = client.get("/login")
        token = re.search(
            rb'name="_csrf_token" value="([^"]+)"',
            response.data,
        ).group(1).decode()
        return client.post("/login", data={
            "email": email,
            "password": "TestPassword123!",
            "_csrf_token": token,
        })

    def csrf_for(self, path, client=None):
        client = client or self.client
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        return re.search(
            rb'name="_csrf_token" value="([^"]+)"',
            response.data,
        ).group(1).decode()

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_student_can_open_own_record_but_not_another_student(self):
        self.assertEqual(self.login("student-a@example.test").status_code, 302)
        own = self.client.get("/student/21001")
        other = self.client.get("/student/21002")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 403)

    def test_uopz_can_open_only_assigned_student(self):
        self.assertEqual(self.login("uopz@example.test").status_code, 302)
        assigned = self.client.get("/student/21001")
        unassigned = self.client.get("/student/21002")
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(unassigned.status_code, 403)

    def test_admin_can_open_any_student(self):
        self.assertEqual(self.login("admin@example.test").status_code, 302)
        self.assertEqual(self.client.get("/student/21002").status_code, 200)

    def test_new_internship_has_no_automatic_supervisors(self):
        with self.app.app_context():
            student = self._user(
                "student-no-assignment@example.test",
                "student",
                "21999",
            )
            db.session.flush()
            internship = ensure_internship(
                student.album_number,
                "zal6",
                {
                    "rok_akademicki": "2025/2026",
                    "dziennik": [
                        {"dzien": "1", "godziny": "8"},
                        {"dzien": "2", "godziny": "6"},
                    ],
                },
            )
            self.assertIsNone(internship.uopz_id)
            self.assertIsNone(internship.zopz_id)
            self.assertEqual(internship.total_days, 2)
            self.assertEqual(internship.total_hours, 14)
            db.session.rollback()

    def test_only_dean_office_and_admin_can_open_assignments(self):
        self.assertEqual(self.login("uopz@example.test").status_code, 302)
        self.assertEqual(self.client.get("/przydzialy").status_code, 403)

        dean_client = self.app.test_client()
        self.assertEqual(
            self.login("dziekanat@example.test", dean_client).status_code,
            302,
        )
        response = dean_client.get("/przydzialy?rok=2025/2026")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"21001", response.data)
        self.assertIn(b"21002", response.data)

    def test_dean_assignment_grants_supervisor_access(self):
        year = current_academic_year()
        self.assertEqual(self.login("dziekanat@example.test").status_code, 302)
        token = self.csrf_for(f"/przydzialy?rok={year}")
        with self.app.app_context():
            student_b = User.query.filter_by(album_number="21002").one()
            uopz = User.query.filter_by(email="uopz@example.test").one()
            zopz = User.query.filter_by(email="zopz@example.test").one()
            student_id = student_b.id
            uopz_id = uopz.id
            zopz_id = zopz.id
        response = self.client.post("/przydzialy", data={
            "_csrf_token": token,
            "student_id": student_id,
            "academic_year": year,
            "uopz_id": uopz_id,
            "zopz_id": zopz_id,
        })
        self.assertEqual(response.status_code, 302)

        supervisor_client = self.app.test_client()
        self.assertEqual(
            self.login("uopz@example.test", supervisor_client).status_code,
            302,
        )
        self.assertEqual(
            supervisor_client.get("/student/21002").status_code,
            200,
        )

        with self.app.app_context():
            internship = Internship.query.filter_by(
                student_id=student_id,
                academic_year=year,
            ).one()
            db.session.delete(internship)
            db.session.commit()

    def test_dean_can_create_multiple_internship_parts(self):
        year = "2030/2031"
        self.assertEqual(self.login("dziekanat@example.test").status_code, 302)
        token = self.csrf_for(f"/czesci-praktyki?nr=21002&rok={year}")
        with self.app.app_context():
            student = User.query.filter_by(album_number="21002").one()
            uopz = User.query.filter_by(email="uopz@example.test").one()
            student_id = student.id
            uopz_id = uopz.id

        for name, company, hours, days in (
            ("Część w firmie A", "Firma A", 80, 10),
            ("Część w firmie B", "Firma B", 120, 15),
        ):
            response = self.client.post("/czesci-praktyki", data={
                "_csrf_token": token,
                "nr": "21002",
                "academic_year": year,
                "action": "save",
                "name": name,
                "company_name": company,
                "start_date": "2030-07-01",
                "end_date": "2030-07-31",
                "planned_hours": hours,
                "total_hours": hours,
                "total_days": days,
                "status": "completed",
                "uopz_id": uopz_id,
                "zopz_id": "",
            })
            self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            internship = Internship.query.filter_by(
                student_id=student_id,
                academic_year=year,
            ).one()
            self.assertEqual(len(internship.parts), 2)
            self.assertEqual(
                [part.part_number for part in internship.parts],
                [1, 2],
            )
            self.assertEqual(internship.total_hours, 200)
            self.assertEqual(internship.total_days, 25)
            db.session.delete(internship)
            db.session.commit()

    def test_supervisor_access_can_come_from_internship_part(self):
        year = "2031/2032"
        with self.app.app_context():
            student = User.query.filter_by(album_number="21002").one()
            uopz = User.query.filter_by(email="uopz@example.test").one()
            internship = Internship(
                student_id=student.id,
                academic_year=year,
            )
            db.session.add(internship)
            db.session.flush()
            db.session.add(InternshipPart(
                internship_id=internship.id,
                part_number=1,
                name="Część z osobnym opiekunem",
                uopz_id=uopz.id,
                status="active",
            ))
            db.session.commit()
            internship_id = internship.id

        self.assertEqual(self.login("uopz@example.test").status_code, 302)
        self.assertEqual(self.client.get("/student/21002").status_code, 200)

        with self.app.app_context():
            db.session.delete(db.session.get(Internship, internship_id))
            db.session.commit()

    def test_workflow_visibility_follows_assignments(self):
        self.assertEqual(self.login("uopz@example.test").status_code, 302)
        response = self.client.get("/obieg?rok=2025/2026")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"21001", response.data)
        self.assertNotIn(b"21002", response.data)

        dean_client = self.app.test_client()
        self.assertEqual(
            self.login("dziekanat@example.test", dean_client).status_code,
            302,
        )
        response = dean_client.get("/obieg?rok=2025/2026")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"21001", response.data)
        self.assertIn(b"21002", response.data)

    def test_post_without_csrf_is_rejected(self):
        response = self.client.post("/login", data={
            "email": "student-a@example.test",
            "password": "TestPassword123!",
        })
        self.assertEqual(response.status_code, 400)

    def test_security_headers_are_present(self):
        response = self.client.get("/login")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response.headers[
            "Content-Security-Policy"
        ])

    def test_pdf_archive_writes_file_and_database_metadata(self):
        pdf_bytes = b"%PDF-1.4\narchive-test\n%%EOF"
        with self.app.app_context(), tempfile.TemporaryDirectory() as directory:
            admin = db.session.get(User, self.admin_id)
            document, path = archive_pdf(
                pdf_bytes,
                base_dir=directory,
                album_number="21001",
                form_key="zal1",
                file_name="zal1.pdf",
                generated_by=admin,
                source_revision=1,
                source_digest="a" * 64,
                template_version="latex-test",
            )
            db.session.flush()

            self.assertTrue(os.path.isfile(path))
            with open(path, "rb") as handle:
                self.assertEqual(handle.read(), pdf_bytes)
            self.assertEqual(document.file_size_bytes, len(pdf_bytes))
            self.assertEqual(document.mime_type, "application/pdf")
            self.assertEqual(document.generated_by, self.admin_id)
            self.assertEqual(
                db.session.get(GeneratedDocument, document.id).file_name,
                "zal1.pdf",
            )
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
