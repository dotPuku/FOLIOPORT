import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
from config import Config
from .extensions import db, jwt


def _ensure_current_schema(app):
    """Add columns introduced after the initial database bootstrap."""
    column_definitions = {
        "skills": {"category": "VARCHAR(100) NULL"},
        "education": {
            "stream": "VARCHAR(180) NULL",
            "grade_type": "VARCHAR(40) NULL",
            "grade_value": "VARCHAR(100) NULL",
        },
    }
    inspector = inspect(db.engine)
    with db.engine.begin() as connection:
        profile_columns = {column["name"] for column in inspector.get_columns("profile")}
        if "about" in profile_columns:
            try:
                connection.execute(text("ALTER TABLE profile DROP COLUMN about"))
            except OperationalError as exc:
                if "1091" not in str(exc) and "doesn't exist" not in str(exc).lower():
                    raise
        for table, columns in column_definitions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        if "type" in {column["name"] for column in inspector.get_columns("skills")}:
            connection.execute(text(
                "UPDATE skills SET category = type "
                "WHERE (category IS NULL OR category = '') AND type IS NOT NULL"
            ))
        connection.execute(text("UPDATE skills SET category = 'Other' WHERE category IS NULL OR category = ''"))
        education_columns = {column["name"] for column in inspector.get_columns("education")}
        if "field_of_study" in education_columns:
            connection.execute(text(
                "UPDATE education SET stream = field_of_study "
                "WHERE (stream IS NULL OR stream = '') AND field_of_study IS NOT NULL"
            ))
        if "grade" in education_columns:
            connection.execute(text(
                "UPDATE education SET grade_value = grade "
                "WHERE (grade_value IS NULL OR grade_value = '') AND grade IS NOT NULL"
            ))
        connection.execute(text(
            "UPDATE profile SET public_fields = JSON_REMOVE("
            "public_fields, JSON_UNQUOTE(JSON_SEARCH(public_fields, 'one', 'about'))"
            ") WHERE JSON_SEARCH(public_fields, 'one', 'about') IS NOT NULL"
        ))
        removable_columns = {
            "skills": ("description", "keywords", "is_public"),
            "education": ("field_of_study", "grade", "is_public"),
            "projects": ("tagline", "status", "start_date", "end_date", "highlights", "is_public"),
            "experience": ("is_public",),
        }
        for table, columns in removable_columns.items():
            for name in columns:
                existing = {column["name"] for column in inspect(db.engine).get_columns(table)}
                if name in existing:
                    connection.execute(text(f"ALTER TABLE {table} DROP COLUMN {name}"))
        app.logger.info("Database schema compatibility check completed.")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
    CORS(
        app,
        resources={r"/api/*": {"origins": origins}},
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        supports_credentials=False,
    )

    @app.after_request
    def ensure_api_cors(response):
        origin = request.headers.get("Origin")
        if request.path.startswith("/api/") and origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers.add("Vary", "Origin")
            if request.method == "OPTIONS":
                requested_headers = {
                    header.strip().lower()
                    for header in request.headers.get("Access-Control-Request-Headers", "").split(",")
                    if header.strip()
                }
                allowed_headers = {"content-type", "authorization"}
                response.headers["Access-Control-Allow-Headers"] = ", ".join(
                    sorted(requested_headers & allowed_headers)
                )
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        return response

    db.init_app(app)
    jwt.init_app(app)

    from .routes.auth import auth_bp
    from .routes.admin import admin_bp
    from .routes.public import public_bp
    from .routes.chat import chat_bp
    from .routes.job_matcher import matcher_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(public_bp, url_prefix="/api/public")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(matcher_bp, url_prefix="/api/job-match")

    @app.get("/api/health")
    def health():
        result = {"status": "ok", "service": "Folioport API"}
        try:
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            result["database"] = "connected"
        except Exception:
            result["database"] = "unavailable"
        return jsonify(result), 200

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"error": "File is too large. Maximum upload size is configured in MAX_CONTENT_LENGTH_MB."}), 413

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Route not found."}), 404

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        app.logger.exception("Unhandled server error")
        return jsonify({"error": "An unexpected server error occurred."}), 500

    with app.app_context():
        # Models must be imported before create_all.
        from . import models  # noqa: F401
        db.create_all()
        _ensure_current_schema(app)
        # Seed the singleton profile so the public page always has a predictable shape.
        from .models import Profile
        if db.session.get(Profile, 1) is None:
            db.session.add(Profile(id=1, full_name="Your Name", headline="Developer & Problem Solver"))
            db.session.commit()

    return app
