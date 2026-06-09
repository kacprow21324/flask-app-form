import os
import re
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.models import (
    Internship,
    InternshipPart,
    User,
    ZopzInvitation,
    db,
)
from werkzeug.security import generate_password_hash


class ZopzInvitationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app
        cls.app.config.update(
            TESTING=True,
            SERVER_NAME="localhost",
            SMTP_HOST="",
        )

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            dean = self._user("dean@example.test", "dziekanat")
            student = self._user(
                "26001@student.ans-elblag.pl", "student", "26001",
            )
            db.session.flush()
            internship = Internship(
                student_id=student.id,
                academic_year="2025/2026",
                status="active",
            )
            db.session.add(internship)
            db.session.flush()
            part = InternshipPart(
                internship_id=internship.id,
                part_number=1,
                name="Praktyka podstawowa",
                planned_hours=240,
            )
            db.session.add(part)
            db.session.commit()
            self.internship_id = internship.id
            self.part_id = part.id
            self.dean_id = dean.id
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
            last_name="Test",
            role=role,
            album_number=album_number,
            is_active=1,
        )
        db.session.add(user)
        return user

    @staticmethod
    def _csrf(response):
        return re.search(
            rb'name="_csrf_token" value="([^"]+)"',
            response.data,
        ).group(1).decode()

    def login_dean(self):
        response = self.client.get("/login")
        return self.client.post("/login", data={
            "email": "dean@example.test",
            "password": "TestPassword123!",
            "_csrf_token": self._csrf(response),
        })

    def create_invitation(self, target):
        self.login_dean()
        response = self.client.get("/administracja/")
        response = self.client.post("/administracja/zaproszenia-zopz", data={
            "_csrf_token": self._csrf(response),
            "first_name": "Jan",
            "last_name": "Kowalski",
            "email": "jan.kowalski@firma.example",
            "target": target,
        })
        self.assertEqual(response.status_code, 200)
        match = re.search(
            rb"http://localhost/auth/zaproszenie-zopz/([^\"<]+)",
            response.data,
        )
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def test_invitation_creates_account_and_assigns_whole_internship(self):
        token = self.create_invitation(f"internship:{self.internship_id}")
        self.client = self.app.test_client()
        response = self.client.get(f"/auth/zaproszenie-zopz/{token}")
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            f"/auth/zaproszenie-zopz/{token}",
            data={
                "_csrf_token": self._csrf(response),
                "password": "NewPassword123!",
                "password_confirmation": "NewPassword123!",
            },
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            user = User.query.filter_by(
                email="jan.kowalski@firma.example",
            ).one()
            internship = db.session.get(Internship, self.internship_id)
            invitation = ZopzInvitation.query.one()
            self.assertEqual(user.role, "zopz")
            self.assertEqual(internship.zopz_id, user.id)
            self.assertEqual(invitation.accepted_user_id, user.id)
            self.assertIsNotNone(invitation.accepted_at)

        self.client = self.app.test_client()
        self.assertEqual(
            self.client.get(f"/auth/zaproszenie-zopz/{token}").status_code,
            410,
        )

    def test_part_invitation_does_not_assign_whole_internship(self):
        token = self.create_invitation(f"part:{self.part_id}")
        self.client = self.app.test_client()
        response = self.client.get(f"/auth/zaproszenie-zopz/{token}")
        self.client.post(
            f"/auth/zaproszenie-zopz/{token}",
            data={
                "_csrf_token": self._csrf(response),
                "password": "NewPassword123!",
                "password_confirmation": "NewPassword123!",
            },
        )

        with self.app.app_context():
            user = User.query.filter_by(
                email="jan.kowalski@firma.example",
            ).one()
            internship = db.session.get(Internship, self.internship_id)
            part = db.session.get(InternshipPart, self.part_id)
            self.assertIsNone(internship.zopz_id)
            self.assertEqual(part.zopz_id, user.id)

    def test_new_invitation_revokes_previous_for_same_target(self):
        self.create_invitation(f"internship:{self.internship_id}")
        self.client = self.app.test_client()
        self.create_invitation(f"internship:{self.internship_id}")

        with self.app.app_context():
            invitations = ZopzInvitation.query.order_by(
                ZopzInvitation.id,
            ).all()
            self.assertEqual(len(invitations), 2)
            self.assertIsNotNone(invitations[0].revoked_at)
            self.assertTrue(invitations[1].is_pending)


if __name__ == "__main__":
    unittest.main()
