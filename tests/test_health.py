import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app as application_module
from core.models import db


class HealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application_module.app
        cls.app.config.update(TESTING=True)

    def setUp(self):
        with self.app.app_context():
            db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_liveness_does_not_depend_on_databases(self):
        response = self.client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    @patch("core.health.store.ping")
    def test_readiness_checks_both_databases(self, mongo_ping):
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["checks"], {
            "mariadb": "ok",
            "mongodb": "ok",
        })
        mongo_ping.assert_called_once_with()

    @patch("core.health.store.ping", side_effect=RuntimeError("mongo down"))
    def test_readiness_returns_503_when_mongo_is_unavailable(self, _mongo_ping):
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["checks"]["mongodb"], "error")
