import getpass
import re
import sys
from app import create_app
from app.extensions import db
from app.models import AdminUser
from scripts.migrate_db import migrate_database
from werkzeug.security import generate_password_hash


def main():
    app = create_app()
    migrate_database(app)
    with app.app_context():
        print("Create or update a Folioport admin account")
        username = input("Admin username: ").strip()
        email = input("Admin email: ").strip().lower()
        if not username or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            print("A username and valid email are required.")
            sys.exit(1)
        password = getpass.getpass("Password (minimum 12 characters): ")
        confirm = getpass.getpass("Confirm password: ")
        if len(password) < 12 or password != confirm:
            print("Passwords must match and be at least 12 characters long.")
            sys.exit(1)
        user = AdminUser.query.filter(
            (AdminUser.username == username) | (AdminUser.email == email)
        ).first()
        if user:
            user.username = username
            user.email = email
            user.password_hash = generate_password_hash(password, method="scrypt")
            user.is_active = True
            print("Existing admin updated.")
        else:
            db.session.add(
                AdminUser(
                    username=username,
                    email=email,
                    password_hash=generate_password_hash(password, method="scrypt"),
                )
            )
            print("Admin created.")
        db.session.commit()
        print("Done. Sign in at http://localhost:5173/admin/login")


if __name__ == "__main__":
    main()
