import os
import re
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.models import User, db
from werkzeug.security import generate_password_hash


class InternshipAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app
        cls.app.config.update(TESTING=True, SERVER_NAME="localhost")

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            admin = User(
                email="internship-admin@example.test",
                password_hash=generate_password_hash("TestPassword123!"),
                first_name="Api",
                last_name="Admin",
                role="admin",
                is_active=1,
            )
            student = User(
                email="internship-student@example.test",
                password_hash=generate_password_hash("TestPassword123!"),
                first_name="Jan",
                last_name="Student",
                role="student",
                album_number="28001",
                is_active=1,
            )
            db.session.add_all([admin, student])
            db.session.commit()
            self.student_id = student.id
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
            "email": "internship-admin@example.test",
            "password": "TestPassword123!",
            "_csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/api/csrf-token")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["csrf_token"]

    def test_internship_create_filter_update_and_delete(self):
        token = self.login()
        headers = {"X-CSRF-Token": token}
        created = self.client.post(
            "/api/internships",
            json={
                "student_id": self.student_id,
                "company_name": "Example Company",
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
                "status": "draft",
            },
            headers=headers,
        )
        self.assertEqual(created.status_code, 201)
        internship_id = created.get_json()["id"]
        self.assertEqual(created.get_json()["academic_year"], "2025/2026")

        listed = self.client.get(
            f"/api/internships?student_id={self.student_id}",
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()["internships"]), 1)

        updated = self.client.put(
            f"/api/internships/{internship_id}",
            json={"status": "active"},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["status"], "active")

        deleted = self.client.delete(
            f"/api/internships/{internship_id}", headers=headers,
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.get(f"/api/internships/{internship_id}").status_code,
            404,
        )

    def test_internship_rejects_invalid_dates_and_unknown_student(self):
        token = self.login()
        headers = {"X-CSRF-Token": token}
        invalid_dates = self.client.post(
            "/api/internships",
            json={
                "student_id": self.student_id,
                "company_name": "Example Company",
                "start_date": "2026-08-01",
                "end_date": "2026-07-01",
                "status": "draft",
            },
            headers=headers,
        )
        self.assertEqual(invalid_dates.status_code, 400)

        unknown_student = self.client.post(
            "/api/internships",
            json={
                "student_id": 999999,
                "company_name": "Example Company",
                "start_date": "2026-07-01",
                "end_date": "2026-08-01",
                "status": "draft",
            },
            headers=headers,
        )
        self.assertEqual(unknown_student.status_code, 404)
