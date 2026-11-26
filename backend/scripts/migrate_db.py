from pathlib import Path

from flask_migrate import upgrade

from app import create_app
from app.extensions import db
from app.models import Profile


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def migrate_database(app):
    with app.app_context():
        upgrade(directory=str(MIGRATIONS_DIR))
        if db.session.get(Profile, 1) is None:
            db.session.add(
                Profile(
                    id=1,
                    full_name="Your Name",
                    headline="Developer & Problem Solver",
                )
            )
            db.session.commit()


def main():
    app = create_app()
    migrate_database(app)
    print("Database migrations are up to date.")


if __name__ == "__main__":
    main()
