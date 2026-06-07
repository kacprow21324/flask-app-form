import io
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
import core.web as web_module
from core import workflow
from core.documents import archive_pdf, source_checksum
from core.generate_pdf_latex import PDFEngineUnavailable
from core.models import (
    Attachment,
    DocumentWorkflow,
    GeneratedDocument,
    Internship,
    User,
    db,
)
from werkzeug.security import generate_password_hash


class DocumentVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app
        cls.app.config.update(TESTING=True, SERVER_NAME="localhost")

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.student = User(
                email="pdf-student@example.test",
                password_hash=generate_password_hash("TestPassword123!"),
                first_name="Pdf",
                last_name="Student",
                role="student",
                album_number="24001",
                is_active=1,
            )
            db.session.add(self.student)
            db.session.flush()
            db.session.add(Attachment(
                key="zal1",
                nr="1",
                title="Porozumienie",
                reviewer_role="uopz",
                reviewer_label="UOPZ",
                sort_order=1,
            ))
            db.session.add(Internship(
                student_id=self.student.id,
                academic_year="2025/2026",
            ))
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self):
        response = self.client.get("/login")
        import re
        token = re.search(
            rb'name="_csrf_token" value="([^"]+)"',
            response.data,
        ).group(1).decode()
        return self.client.post("/login", data={
            "email": "pdf-student@example.test",
            "password": "TestPassword123!",
            "_csrf_token": token,
        })

    def test_archive_deduplicates_same_source_and_versions_new_revision(self):
        with self.app.app_context(), tempfile.TemporaryDirectory() as directory:
            student = User.query.filter_by(album_number="24001").one()
            record = {"pole": "wartość"}
            digest = source_checksum(record)
            first, first_path = archive_pdf(
                b"%PDF-first",
                base_dir=directory,
                album_number="24001",
                form_key="zal1",
                file_name="zal1.pdf",
                generated_by=student,
                source_revision=3,
                source_digest=digest,
                source_approved_at=datetime.utcnow(),
                template_version="latex-test",
            )
            db.session.flush()
            duplicate, duplicate_path = archive_pdf(
                b"%PDF-first",
                base_dir=directory,
                album_number="24001",
                form_key="zal1",
                file_name="zal1.pdf",
                generated_by=student,
                source_revision=3,
                source_digest=digest,
                source_approved_at=datetime.utcnow(),
                template_version="latex-test",
            )
            db.session.flush()
            second, _ = archive_pdf(
                b"%PDF-second",
                base_dir=directory,
                album_number="24001",
                form_key="zal1",
                file_name="zal1.pdf",
                generated_by=student,
                source_revision=4,
                source_digest=source_checksum({"pole": "nowa wartość"}),
                source_approved_at=datetime.utcnow(),
                template_version="latex-test",
            )
            db.session.flush()

            self.assertEqual(first.id, duplicate.id)
            self.assertEqual(first_path, duplicate_path)
            self.assertEqual(GeneratedDocument.query.count(), 2)
            self.assertEqual(first.document_version, 1)
            self.assertEqual(first.is_current, 0)
            self.assertEqual(second.document_version, 2)
            self.assertEqual(second.is_current, 1)

    def test_draft_document_cannot_generate_pdf(self):
        self.assertEqual(self.login().status_code, 302)
        with self.app.app_context():
            db.session.add(DocumentWorkflow(
                album_number="24001",
                form_key="zal1",
                status="draft",
                reviewer_role="uopz",
            ))
            db.session.commit()

        with (
            patch.object(
                web_module,
                "get_form",
                return_value={"rok_akademicki": "2025/2026"},
            ),
            patch.object(web_module, "get_form_revision", return_value=1),
        ):
            response = self.client.get("/student/24001/zal1/pobierz")

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(GeneratedDocument.query.count(), 0)

    def test_approval_records_exact_source_revision(self):
        with self.app.app_context(), patch(
            "core.workflow.get_form_revision",
            return_value=9,
        ):
            workflow.set_status(
                "24001",
                "zal1",
                "approved",
                reviewer_role="uopz",
                action="approve",
            )
            state = DocumentWorkflow.query.filter_by(
                album_number="24001",
                form_key="zal1",
            ).one()
            self.assertEqual(state.approved_revision, 9)

            workflow.set_status(
                "24001",
                "zal1",
                "draft",
                reviewer_role="uopz",
                action="updated",
            )
            self.assertIsNone(state.approved_revision)

    def test_same_approved_revision_is_generated_only_once(self):
        self.assertEqual(self.login().status_code, 302)
        with self.app.app_context():
            db.session.add(DocumentWorkflow(
                album_number="24001",
                form_key="zal1",
                status="approved",
                reviewer_role="uopz",
                approved_revision=7,
            ))
            db.session.commit()

        record = {
            "rok_akademicki": "2025/2026",
            "imie_nazwisko": "Pdf Student",
            "nr_albumu": "24001",
        }
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(web_module, "DATA_DIR", directory),
                patch.object(web_module, "get_form", return_value=record),
                patch.object(
                    web_module,
                    "get_form_revision",
                    return_value=7,
                ),
                patch(
                    "core.generate_pdf_latex.get_template_version",
                    return_value="latex-test",
                ),
                patch(
                    "core.generate_pdf_latex.generate_pdf_latex",
                    return_value=io.BytesIO(b"%PDF-approved"),
                ) as generator,
            ):
                first = self.client.get("/student/24001/zal1/pobierz")
                second = self.client.get("/student/24001/zal1/pobierz")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.mimetype, "application/pdf")
        self.assertIn(
            "Zal_1_24001.pdf",
            first.headers["Content-Disposition"],
        )
        self.assertTrue(first.data.startswith(b"%PDF-"))
        first.close()
        second.close()
        self.assertEqual(generator.call_count, 1)
        with self.app.app_context():
            document = GeneratedDocument.query.one()
            self.assertEqual(document.source_revision, 7)
            self.assertEqual(document.document_version, 1)
            self.assertEqual(document.download_count, 2)

    def test_unavailable_pdf_engine_is_handled_without_archiving(self):
        self.assertEqual(self.login().status_code, 302)
        with self.app.app_context():
            db.session.add(DocumentWorkflow(
                album_number="24001",
                form_key="zal1",
                status="approved",
                reviewer_role="uopz",
                approved_revision=3,
            ))
            db.session.commit()

        with (
            patch.object(
                web_module,
                "get_form",
                return_value={
                    "rok_akademicki": "2025/2026",
                    "imie_nazwisko": "Pdf Student",
                    "nr_albumu": "24001",
                },
            ),
            patch.object(web_module, "get_form_revision", return_value=3),
            patch(
                "core.generate_pdf_latex.generate_pdf_latex",
                side_effect=PDFEngineUnavailable("xelatex missing"),
            ),
        ):
            response = self.client.get("/student/24001/zal1/pobierz")

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertTrue(any(
                "XeLaTeX jest niedostępny" in message
                for _, message in session.get("_flashes", [])
            ))
        with self.app.app_context():
            self.assertEqual(GeneratedDocument.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
