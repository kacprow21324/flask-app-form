import os
import hashlib
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.models import (
    ArchivePackage,
    DocumentWorkflow,
    GeneratedDocument,
    Internship,
    User,
    db,
)
from core.retention import (
    anonymize_expired_archive,
    create_student_archive,
    verify_archive_package,
)


class RetentionTests(unittest.TestCase):
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

    def _student_data(self):
        student = User(
            email="archive-student@example.test",
            password_hash="unused",
            first_name="Jan",
            last_name="Archiwalny",
            role="student",
            album_number="25001",
            is_active=1,
        )
        admin = User(
            email="archive-admin@example.test",
            password_hash="unused",
            first_name="Anna",
            last_name="Admin",
            role="admin",
            is_active=1,
        )
        db.session.add_all([student, admin])
        db.session.flush()
        internship = Internship(
            student_id=student.id,
            academic_year="2025/2026",
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(DocumentWorkflow(
            album_number=student.album_number,
            form_key="zal1",
            status="approved",
            approved_revision=2,
        ))
        return student, admin, internship

    def test_archive_contains_manifest_forms_and_generated_files(self):
        with self.app.app_context(), tempfile.TemporaryDirectory() as directory:
            student, admin, internship = self._student_data()
            relative_pdf = "generated/25001/zal1/v1_test.pdf"
            pdf_path = os.path.join(directory, *relative_pdf.split("/"))
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            with open(pdf_path, "wb") as handle:
                handle.write(b"%PDF-archive")
            pdf_checksum = hashlib.sha256(b"%PDF-archive").hexdigest()
            db.session.add(GeneratedDocument(
                internship_id=internship.id,
                album_number="25001",
                form_key="zal1",
                document_version=1,
                source_revision=2,
                source_checksum="a" * 64,
                source_fingerprint="b" * 64,
                template_version="latex-test",
                file_path=relative_pdf,
                file_name="zal1.pdf",
                file_size_bytes=12,
                checksum_sha256=pdf_checksum,
                download_count=1,
                is_current=1,
            ))
            db.session.commit()

            with patch(
                "core.retention.store.get_student_forms",
                return_value={"zal1": {"imie_nazwisko": "Jan Archiwalny"}},
            ):
                package, path = create_student_archive(
                    student=student,
                    base_dir=directory,
                    actor=admin,
                    retention_years=10,
                    hash_salt="test-salt",
                )
                db.session.commit()

            self.assertTrue(verify_archive_package(package, directory))
            self.assertEqual(package.status, "active")
            self.assertEqual(student.is_active, 1)
            self.assertEqual(internship.is_archived, 1)
            with zipfile.ZipFile(path, "r") as archive:
                names = set(archive.namelist())
                self.assertIn("manifest.json", names)
                self.assertIn("forms.json", names)
                self.assertTrue(any(
                    name.startswith("generated_documents/")
                    for name in names
                ))

    def test_expired_archive_anonymizes_and_purges_sources(self):
        with self.app.app_context(), tempfile.TemporaryDirectory() as directory:
            student, admin, internship = self._student_data()
            db.session.commit()
            now = datetime.utcnow()
            with patch(
                "core.retention.store.get_student_forms",
                return_value={"zal1": {"imie_nazwisko": "Jan Archiwalny"}},
            ):
                package, archive_path = create_student_archive(
                    student=student,
                    base_dir=directory,
                    actor=admin,
                    retention_years=0,
                    hash_salt="test-salt",
                    now=now,
                )
                db.session.commit()

            with patch(
                "core.retention.store.delete_student_forms",
                return_value=["zal1"],
            ) as delete_forms:
                changed = anonymize_expired_archive(
                    package,
                    base_dir=directory,
                    now=now + timedelta(seconds=1),
                )
                db.session.commit()

            self.assertTrue(changed)
            delete_forms.assert_called_once_with("25001")
            self.assertFalse(os.path.exists(archive_path))
            self.assertEqual(package.status, "purged")
            self.assertIsNone(package.original_album_number)
            self.assertIsNone(student.album_number)
            self.assertEqual(student.first_name, "Użytkownik")
            self.assertIsNotNone(student.anonymized_at)
            workflow = DocumentWorkflow.query.one()
            self.assertTrue(workflow.album_number.startswith("anon-"))

    def test_anonymization_before_retention_is_rejected(self):
        with self.app.app_context(), tempfile.TemporaryDirectory() as directory:
            student, admin, _ = self._student_data()
            db.session.commit()
            with patch(
                "core.retention.store.get_student_forms",
                return_value={},
            ):
                package, _ = create_student_archive(
                    student=student,
                    base_dir=directory,
                    actor=admin,
                    retention_years=10,
                    hash_salt="test-salt",
                )
                db.session.commit()

            with self.assertRaisesRegex(ValueError, "jeszcze nie upłynął"):
                anonymize_expired_archive(package, base_dir=directory)


if __name__ == "__main__":
    unittest.main()
