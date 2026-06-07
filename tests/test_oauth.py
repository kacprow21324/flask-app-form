import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.auth import AuthError, resolve_microsoft_user
from core.models import User, db
from werkzeug.security import generate_password_hash


TENANT_ID = "11111111-2222-3333-4444-555555555555"
OBJECT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class MicrosoftOAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app
        cls.app.config.update(
            TESTING=True,
            MS_TENANT_ID=TENANT_ID,
            MS_ALLOWED_EMAIL_DOMAINS=("ans-elblag.pl",),
        )

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            db.session.add(User(
                email="student@ans-elblag.pl",
                password_hash=generate_password_hash("TestPassword123!"),
                first_name="Jan",
                last_name="Student",
                role="student",
                album_number="26001",
                is_active=1,
            ))
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @staticmethod
    def claims(**overrides):
        values = {
            "tid": TENANT_ID,
            "oid": OBJECT_ID,
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "preferred_username": "student@ans-elblag.pl",
        }
        values.update(overrides)
        return values

    def test_existing_user_is_linked_by_immutable_microsoft_identity(self):
        with self.app.app_context():
            user = resolve_microsoft_user(self.claims())
            db.session.commit()

            self.assertEqual(user.microsoft_tenant_id, TENANT_ID)
            self.assertEqual(user.microsoft_object_id, OBJECT_ID)
            self.assertEqual(user.email_verified, 1)

    def test_account_from_another_tenant_is_rejected(self):
        with self.app.app_context(), self.assertRaises(AuthError):
            resolve_microsoft_user(self.claims(
                tid="99999999-2222-3333-4444-555555555555",
            ))

    def test_account_outside_allowed_domain_is_rejected(self):
        with self.app.app_context(), self.assertRaises(AuthError):
            resolve_microsoft_user(self.claims(
                preferred_username="student@outlook.com",
            ))

    def test_linked_email_cannot_be_taken_by_another_microsoft_identity(self):
        with self.app.app_context():
            resolve_microsoft_user(self.claims())
            db.session.commit()

            with self.assertRaises(AuthError):
                resolve_microsoft_user(self.claims(
                    oid="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
                ))
