import unittest

from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db
from app.models import AdminUser, Education, Experience, Profile, Project, Skill
from scripts.migrate_db import migrate_database


class MigrationTests(unittest.TestCase):
    def test_empty_database_is_migrated_and_profile_seeded(self):
        app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
            "SECRET_KEY": "migration-test-secret",
            "JWT_SECRET_KEY": "migration-test-jwt-secret-longer-than-32",
            "RATELIMIT_ENABLED": False,
            "RATELIMIT_STORAGE_URI": "memory://",
        })

        migrate_database(app)

        with app.app_context():
            tables = set(inspect(db.engine).get_table_names())
            self.assertTrue({
                "admin_users",
                "education",
                "experience",
                "profile",
                "projects",
                "skills",
                "reindex_jobs",
                "reindex_job_items",
                "alembic_version",
            }.issubset(tables))
            self.assertEqual(db.session.get(Profile, 1).full_name, "Your Name")
            db.session.remove()
            db.engine.dispose()

    def test_existing_portfolio_data_is_adopted_and_queue_tables_are_added(self):
        app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
            "SECRET_KEY": "migration-test-secret",
            "JWT_SECRET_KEY": "migration-test-jwt-secret-longer-than-32",
            "RATELIMIT_ENABLED": False,
            "RATELIMIT_STORAGE_URI": "memory://",
        })

        with app.app_context():
            for model in (AdminUser, Profile, Skill, Education, Project, Experience):
                model.__table__.create(db.engine, checkfirst=True)
            admin = AdminUser(
                username="existing-admin",
                email="existing@example.test",
                password_hash="already-hashed",
            )
            skill = Skill(name="Python", category="Programming")
            db.session.add_all([admin, Profile(id=1, full_name="Existing Candidate"), skill])
            db.session.commit()
            admin_id = admin.id
            skill_id = skill.id

        migrate_database(app)
        migrate_database(app)

        with app.app_context():
            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names())
            self.assertIn("reindex_jobs", tables)
            self.assertIn("reindex_job_items", tables)
            self.assertEqual(db.session.get(AdminUser, admin_id).email, "existing@example.test")
            self.assertEqual(db.session.get(Skill, skill_id).name, "Python")
            self.assertEqual(
                db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one(),
                "55e086f63d97",
            )
            db.session.remove()
            db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
