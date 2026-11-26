import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

DATABASE_URI = os.getenv("TIDB_URL") or os.getenv("DATABASE_URL") or "sqlite:///folioport_dev.db"
ENGINE_OPTIONS = {"pool_pre_ping": True}
if not DATABASE_URI.startswith("sqlite:"):
    ENGINE_OPTIONS.update({
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 10,
    })


class Config:
    DEBUG = os.getenv("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-only-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_COOKIE_NAME = "folioport_access_token"
    JWT_ACCESS_COOKIE_PATH = "/api"
    JWT_COOKIE_SECURE = not DEBUG
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_IN_COOKIES = False
    JWT_ACCESS_CSRF_HEADER_NAME = "X-CSRF-TOKEN"
    JWT_CSRF_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_DEFAULT = []
    TRUST_PROXY = os.getenv("TRUST_PROXY", "0").strip().lower() in {"1", "true", "yes"}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = ENGINE_OPTIONS
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "8")) * 1024 * 1024
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    QDRANT_URL = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "folioport_portfolio")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    @staticmethod
    def init_app(app):
        # TiDB Cloud requires TLS. SQLAlchemy/PyMySQL accepts SSL settings via URL query options.
        # Keep caller's full DATABASE_URL intact because TiDB offers different endpoint formats.
        pass
