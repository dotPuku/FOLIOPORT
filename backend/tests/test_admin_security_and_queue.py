import unittest
from unittest.mock import patch

from app import create_app
from app.extensions import db, limiter
from app.models import AdminUser, Profile, Skill
from werkzeug.security import generate_password_hash


class AdminSecurityAndQueueTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
            "JWT_SECRET_KEY": "admin-api-test-secret-longer-than-32",
            "JWT_COOKIE_SECURE": False,
            "RATELIMIT_ENABLED": True,
            "RATELIMIT_STORAGE_URI": "memory://",
            "CORS_ORIGINS": ["https://folioport.example.test"],
            "QDRANT_URL": "",
            "QDRANT_API_KEY": "",
        })
        limiter.reset()
        self.sync_entity_patcher = patch(
            "app.routes.admin.sync_entity",
            return_value={"indexed": 0, "warning": None},
        )
        self.sync_entity_patcher.start()
        with self.app.app_context():
            db.create_all()
            db.session.add(AdminUser(
                username="admin",
                email="admin@example.test",
                password_hash=generate_password_hash("correct-horse-battery-staple"),
            ))
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        self.sync_entity_patcher.stop()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def login(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "correct-horse-battery-staple"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json["csrf_token"]

    def test_login_issues_only_an_httponly_cookie_and_csrf_token(self):
        self.app.config["JWT_COOKIE_SECURE"] = True
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "correct-horse-battery-staple"},
            base_url="https://localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrf_token", response.json)
        self.assertNotIn("access_token", response.json)
        cookie = response.headers["Set-Cookie"]
        self.assertIn("folioport_access_token=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertEqual(self.client.get("/api/auth/me", base_url="https://localhost").status_code, 200)

    def test_csrf_is_required_for_admin_mutations_and_logout(self):
        csrf = self.login()
        denied = self.client.post(
            "/api/admin/skills",
            json={"name": "Python", "category": "Programming"},
        )
        self.assertEqual(denied.status_code, 401)

        created = self.client.post(
            "/api/admin/skills",
            json={"name": "Python", "category": "Programming"},
            headers={"X-CSRF-TOKEN": csrf},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["name"], "Python")

        logout = self.client.post(
            "/api/auth/logout",
            json={},
            headers={"X-CSRF-TOKEN": csrf},
        )
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_crud_validation_rejects_missing_and_out_of_range_fields(self):
        csrf = self.login()
        headers = {"X-CSRF-TOKEN": csrf}

        missing_category = self.client.post(
            "/api/admin/skills",
            json={"name": "Python"},
            headers=headers,
        )
        self.assertEqual(missing_category.status_code, 400)
        self.assertIn("Category", missing_category.json["error"])

        invalid_years = self.client.post(
            "/api/admin/skills",
            json={"name": "Python", "category": "Programming", "years_experience": -1},
            headers=headers,
        )
        self.assertEqual(invalid_years.status_code, 400)

        invalid_date = self.client.post(
            "/api/admin/experience",
            json={
                "company": "Example Co",
                "title": "Engineer",
                "start_date": "2022",
            },
            headers=headers,
        )
        self.assertEqual(invalid_date.status_code, 400)
        with self.app.app_context():
            self.assertEqual(Skill.query.count(), 0)

    def test_login_rate_limit_returns_json_429(self):
        responses = [
            self.client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "incorrect"},
            )
            for _ in range(6)
        ]

        self.assertEqual([response.status_code for response in responses[:5]], [401] * 5)
        self.assertEqual(responses[5].status_code, 429)
        self.assertIn("error", responses[5].json)

    def test_reindex_job_processes_at_most_five_records_per_request(self):
        with self.app.app_context():
            db.session.add(Profile(id=1, full_name="Candidate"))
            db.session.add_all([
                Skill(name=f"Skill {index}", category="Testing")
                for index in range(6)
            ])
            db.session.commit()
        csrf = self.login()
        headers = {"X-CSRF-TOKEN": csrf}
        queued = self.client.post("/api/admin/reindex", json={}, headers=headers)

        self.assertEqual(queued.status_code, 202)
        job_id = queued.json["job"]["id"]
        self.assertEqual(queued.json["job"]["total_entities"], 7)
        with patch("app.routes.admin.clear_index") as clear_index, patch(
            "app.routes.admin.sync_entities",
            side_effect=lambda entities: {"indexed": len(entities), "warning": None},
        ) as sync_entities:
            first = self.client.post(
                f"/api/admin/reindex/jobs/{job_id}/process",
                json={},
                headers=headers,
            )
            second = self.client.post(
                f"/api/admin/reindex/jobs/{job_id}/process",
                json={},
                headers=headers,
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json["job"]["status"], "running")
        self.assertEqual(first.json["job"]["processed_entities"], 5)
        self.assertEqual(second.json["job"]["status"], "completed")
        self.assertEqual(second.json["job"]["processed_entities"], 7)
        self.assertEqual([len(call.args[0]) for call in sync_entities.call_args_list], [5, 2])
        clear_index.assert_called_once()

    def test_cors_allows_credentials_only_for_configured_origin(self):
        allowed = self.client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://folioport.example.test",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        denied = self.client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://attacker.example.test",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(allowed.headers.get("Access-Control-Allow-Origin"), "https://folioport.example.test")
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertIn("x-csrf-token", allowed.headers.get("Access-Control-Allow-Headers", "").lower())
        self.assertIsNone(denied.headers.get("Access-Control-Allow-Origin"))


if __name__ == "__main__":
    unittest.main()
