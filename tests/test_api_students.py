import os
import re
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.models import User, db
from werkzeug.security import generate_password_hash


class StudentAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app
        cls.app.config.update(TESTING=True, SERVER_NAME="localhost")

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            db.session.add(User(
                email="api-admin@example.test",
                password_hash=generate_password_hash("TestPassword123!"),
                first_name="Api",
                last_name="Admin",
                role="admin",
                is_active=1,
            ))
            db.session.commit()
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
            "email": "api-admin@example.test",
            "password": "TestPassword123!",
            "_csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/api/csrf-token")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["csrf_token"]

    def test_students_require_authentication_and_return_json_error(self):
        response = self.client.get("/api/students")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.get_json()["error"], "Authentication required.")

    def test_complete_student_crud(self):
        token = self.login()
        headers = {"X-CSRF-Token": token}
        payload = {
            "first_name": "Anna",
            "last_name": "Nowak",
            "album_number": "27001",
            "email": "anna.nowak@example.test",
        }

        created = self.client.post(
            "/api/students", json=payload, headers=headers,
        )
        self.assertEqual(created.status_code, 201)
        student_id = created.get_json()["id"]

        listed = self.client.get("/api/students")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()["students"]), 1)

        fetched = self.client.get(f"/api/students/{student_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.get_json()["album_number"], "27001")

        payload["last_name"] = "Kowalska"
        updated = self.client.put(
            f"/api/students/{student_id}",
            json=payload,
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["last_name"], "Kowalska")

        deleted = self.client.delete(
            f"/api/students/{student_id}", headers=headers,
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.get(f"/api/students/{student_id}").status_code,
            404,
        )

    def test_student_validation_and_conflict(self):
        token = self.login()
        headers = {"X-CSRF-Token": token}
        invalid = self.client.post(
            "/api/students",
            json={
                "first_name": "Anna",
                "last_name": "Nowak",
                "album_number": "abc",
                "email": "invalid",
            },
            headers=headers,
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["code"], "validation_error")

        payload = {
            "first_name": "Anna",
            "last_name": "Nowak",
            "album_number": "27001",
            "email": "anna.nowak@example.test",
        }
        self.assertEqual(
            self.client.post(
                "/api/students", json=payload, headers=headers,
            ).status_code,
            201,
        )
        duplicate = self.client.post(
            "/api/students", json=payload, headers=headers,
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_unknown_student_returns_404_json(self):
        self.login()
        response = self.client.get("/api/students/999999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Student not found.")
