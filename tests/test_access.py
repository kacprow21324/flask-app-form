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
from core.models import (
    Attachment,
    DocumentWorkflow,
    Internship,
    InternshipPart,
    RoleFormAccess,
    User,
    db,
)
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
            db.session.add(RoleFormAccess(role="student", form_key="zal1"))
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
        self.assertIn("Dokumenty".encode(), own.data)
        self.assertIn("Historia".encode(), own.data)
        self.assertNotIn(
            b'data-section-tab="archiwum"',
            own.data,
        )

    def test_uopz_can_open_only_assigned_student(self):
        self.assertEqual(self.login("uopz@example.test").status_code, 302)
        assigned = self.client.get("/student/21001")
        unassigned = self.client.get("/student/21002")
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(unassigned.status_code, 403)

    def test_admin_can_open_any_student(self):
        self.assertEqual(self.login("admin@example.test").status_code, 302)
        response = self.client.get("/student/21002")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-section-tab="archiwum"', response.data)
        self.assertIn("Podgląd formularza".encode(), response.data)

    def test_zal1_new_form_has_system_defaults(self):
        self.assertEqual(self.login("student-a@example.test").status_code, 302)
        response = self.client.get("/zal1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'value="ZAL-1-21001"', response.data)
        self.assertIn(b'name="liczba_godzin"', response.data)
        self.assertIn(b'value="960"', response.data)
        self.assertIn(b'name="data"', response.data)
        self.assertLess(
            response.data.index("Forma studiów".encode()),
            response.data.index("Porozumienie nr".encode()),
        )
        self.assertIn("Podpis uczelnianego opiekuna".encode(), response.data)
        self.assertIn("Podpis dziekanatu".encode(), response.data)

    def test_zal1_save_enforces_system_values_and_normalizes_company_data(self):
        self.assertEqual(self.login("student-a@example.test").status_code, 302)
        token = self.csrf_for("/zal1")
        with patch.object(
            web_module, "_persist", return_value=("saved", 200),
        ) as persist:
            response = self.client.post("/zal1", data={
                "_csrf_token": token,
                "imie_nazwisko": "Student Test",
                "nr_albumu": "21001",
                "nr_porozumienia": "PODMIENIONY",
                "miejscowosc": "elbląg",
                "data": "2000-01-01",
                "specjalnosc": "Testowa",
                "rodzaj_studiow": "stacjonarne",
                "nazwa_zakladu": "Firma Testowa",
                "adres_zakladu": "ul. Portowa 12, Elbląg",
                "nip_zakladu": "",
                "reprezentant_nazwisko": "jan kowalski",
                "reprezentant_stanowisko": "Prezes",
                "email_zakladu": "KONTAKT@FIRMA.PL",
                "uczelniany_opiekun": "Anna Opiekun",
                "data_start": "2026-07-01",
                "data_end": "2026-12-31",
                "liczba_godzin": "960",
            })
        self.assertEqual(response.status_code, 200)
        record = persist.call_args.args[2]
        self.assertEqual(record["nr_porozumienia"], "ZAL-1-21001")
        self.assertNotEqual(record["data"], "2000-01-01")
        self.assertEqual(record["miejscowosc"], "Elbląg")
        self.assertEqual(record["reprezentant_nazwisko"], "Jan Kowalski")
        self.assertEqual(record["email_zakladu"], "kontakt@firma.pl")
        self.assertEqual(record["liczba_godzin"], "960")

    def test_html_print_preview_is_available_for_a_draft(self):
        self.assertEqual(self.login("student-a@example.test").status_code, 302)
        with patch.object(web_module, "get_form", return_value={
            "nr_porozumienia": "ZAL-1-21001",
            "nr_albumu": "21001",
            "imie_nazwisko": "Student Test",
            "liczba_godzin": "960",
        }):
            response = self.client.get("/student/21001/zal1/drukuj")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"ZAL-1-21001", response.data)

    def test_dean_office_can_sign_approved_zal1(self):
        with self.app.app_context():
            db.session.add(DocumentWorkflow(
                album_number="21001",
                form_key="zal1",
                status="approved",
                reviewer_role="uopz",
                approved_revision=1,
            ))
            db.session.commit()

        self.assertEqual(self.login("dziekanat@example.test").status_code, 302)
        token = self.csrf_for("/student/21001")
        record = {"imie_nazwisko": "Student Test"}
        with (
            patch.object(web_module, "get_form", return_value=record),
            patch.object(web_module, "save_form", return_value=2),
        ):
            response = self.client.post(
                "/student/21001/zal1/podpisz-dziekanat",
                data={"_csrf_token": token},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("dziekanat Test", record["podpis_dziekanatu"])
        with self.app.app_context():
            state = DocumentWorkflow.query.filter_by(
                album_number="21001",
                form_key="zal1",
            ).one()
            self.assertEqual(state.approved_revision, 2)
            DocumentWorkflow.query.filter_by(
                album_number="21001",
                form_key="zal1",
            ).delete()
            db.session.commit()

    def test_student_sidebar_uses_single_documents_entry(self):
        self.assertEqual(self.login("student-a@example.test").status_code, 302)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Moje dokumenty".encode(), response.data)
        self.assertNotIn("Obieg dokumentów".encode(), response.data)
        self.assertNotIn("Moje formularze".encode(), response.data)

    def test_legacy_workflow_url_uses_dashboard_view(self):
        self.assertEqual(self.login("uopz@example.test").status_code, 302)
        response = self.client.get("/obieg?rok=2025/2026")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Dashboard".encode(), response.data)
        self.assertIn(b"21001", response.data)
        self.assertNotIn("Obieg dokumentów".encode(), response.data)

    def test_canonical_practices_view_contains_both_tabs(self):
        self.assertEqual(self.login("dziekanat@example.test").status_code, 302)
        response = self.client.get("/praktyki?tab=opiekunowie&rok=2025/2026")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Opiekunowie".encode(), response.data)
        self.assertIn("Części praktyki".encode(), response.data)

        response = self.client.get(
            "/praktyki?tab=czesci&nr=21001&rok=2025/2026",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Opiekunowie".encode(), response.data)
        self.assertIn("Części praktyki".encode(), response.data)

    def test_reviewer_queue_lists_only_actionable_documents(self):
        with self.app.app_context():
            db.session.add(DocumentWorkflow(
                album_number="21001",
                form_key="zal1",
                status="pending",
                reviewer_role="uopz",
            ))
            db.session.commit()

        self.assertEqual(self.login("uopz@example.test").status_code, 302)
        response = self.client.get("/do-zatwierdzenia")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"21001", response.data)
        self.assertIn("Recenzuj".encode(), response.data)

        with self.app.app_context():
            DocumentWorkflow.query.filter_by(
                album_number="21001",
                form_key="zal1",
            ).delete()
            db.session.commit()

    def test_student_cannot_open_reviewer_queue(self):
        self.assertEqual(self.login("student-a@example.test").status_code, 302)
        self.assertEqual(
            self.client.get("/do-zatwierdzenia").status_code,
            403,
        )

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
