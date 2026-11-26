import json
import time
from uuid import uuid4
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from .extensions import db, jwt, limiter, migrate


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    configured_origins = app.config.get("CORS_ORIGINS", [])
    if isinstance(configured_origins, str):
        origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    else:
        origins = [origin.strip() for origin in configured_origins if origin.strip()]
    app.config["CORS_ORIGINS"] = origins
    CORS(
        app,
        resources={r"/api/*": {"origins": origins}},
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-TOKEN"],
        expose_headers=["X-Request-ID", "X-Response-Time-ms", "Retry-After"],
        supports_credentials=True,
    )

    @app.before_request
    def start_request_monitoring():
        g.request_id = uuid4().hex
        g.request_started_at = time.perf_counter()

    @app.after_request
    def record_request_metrics(response):
        started_at = getattr(g, "request_started_at", time.perf_counter())
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        request_id = getattr(g, "request_id", uuid4().hex)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = str(duration_ms)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        app.logger.info(
            "api_request %s",
            json.dumps({
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }, separators=(",", ":")),
        )
        return response

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

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
            app.logger.exception("Health check could not reach the configured database.")
            result.update(status="unavailable", database="unavailable")
            return jsonify(result), 503
        return jsonify(result), 200

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"error": "File is too large. Maximum upload size is configured in MAX_CONTENT_LENGTH_MB."}), 413

    @app.errorhandler(429)
    def rate_limited(_error):
        return jsonify({"error": "Too many requests. Please wait before trying again."}), 429

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Route not found."}), 404

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        app.logger.exception("Unhandled server error")
        return jsonify({"error": "An unexpected server error occurred."}), 500

    return app
