import os
import re
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.models import Internship, User, db
from werkzeug.security import generate_password_hash


class DocumentAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app
        cls.app.config.update(TESTING=True, SERVER_NAME="localhost")

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            admin = User(
                email="document-admin@example.test",
                password_hash=generate_password_hash("TestPassword123!"),
                first_name="Api",
                last_name="Admin",
                role="admin",
                is_active=1,
            )
            student = User(
                email="document-student@example.test",
                password_hash=generate_password_hash("TestPassword123!"),
                first_name="Jan",
                last_name="Student",
                role="student",
                album_number="29001",
                is_active=1,
            )
            db.session.add_all([admin, student])
            db.session.flush()
            internship = Internship(
                student_id=student.id,
                academic_year="2025/2026",
                status="active",
            )
            db.session.add(internship)
            db.session.commit()
            self.internship_id = internship.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self):
        response = self.client.get("/login")
        token = re.search(
            rb'name="_csrf_token" value="([^"]+)"',
            response.data,
        ).group(1).decode()
        response = self.client.post("/login", data={
            "email": "document-admin@example.test",
            "password": "TestPassword123!",
            "_csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/api/csrf-token")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["csrf_token"]

    def test_document_create_filter_get_and_delete(self):
        token = self.login()
        headers = {"X-CSRF-Token": token}
        created = self.client.post(
            "/api/documents",
            json={
                "name": "Dziennik praktyk",
                "document_type": "diary",
                "uploaded_at": "2026-07-10T12:30:00",
                "internship_id": self.internship_id,
                "verification_status": "pending",
                "supervisor_comment": "Do sprawdzenia.",
            },
            headers=headers,
        )
        self.assertEqual(created.status_code, 201)
        document_id = created.get_json()["id"]

        listed = self.client.get(
            f"/api/documents?internship_id={self.internship_id}",
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()["documents"]), 1)

        fetched = self.client.get(f"/api/documents/{document_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(
            fetched.get_json()["supervisor_comment"],
            "Do sprawdzenia.",
        )

        deleted = self.client.delete(
            f"/api/documents/{document_id}", headers=headers,
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.get(f"/api/documents/{document_id}").status_code,
            404,
        )

    def test_document_validates_status_and_internship(self):
        token = self.login()
        headers = {"X-CSRF-Token": token}
        invalid_status = self.client.post(
            "/api/documents",
            json={
                "name": "Dziennik",
                "document_type": "diary",
                "internship_id": self.internship_id,
                "verification_status": "unknown",
            },
            headers=headers,
        )
        self.assertEqual(invalid_status.status_code, 400)

        unknown_internship = self.client.post(
            "/api/documents",
            json={
                "name": "Dziennik",
                "document_type": "diary",
                "internship_id": 999999,
            },
            headers=headers,
        )
        self.assertEqual(unknown_internship.status_code, 404)
