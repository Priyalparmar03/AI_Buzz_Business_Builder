import os
from datetime import timedelta

# On Railway a persistent volume is mounted at /data.
# Locally everything lives next to this file.
_IS_PRODUCTION = os.environ.get("RAILWAY_ENVIRONMENT") is not None
_DATA_DIR = "/data" if _IS_PRODUCTION else os.path.join(os.path.dirname(__file__))


class Config:
    # ── Core ─────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    DEBUG = False
    TESTING = False

    # ── Database (SQLite — Railway persistent volume keeps it safe) ──────────
    _db_path = os.path.join(_DATA_DIR, "db.sqlite3")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{_db_path}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    # ── Groq ──────────────────────────────────────────────────────────────────
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    # ── Generated sites (persisted on Railway volume at /data) ────────────────
    GENERATED_SITES_DIR = os.path.join(_DATA_DIR, "generated_sites")
    SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://localhost:5000")

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000")


class DevelopmentConfig(Config):
    DEBUG = True
    CORS_ORIGINS = "*"


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")


# Auto-select config based on environment
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}

ActiveConfig = config_map.get(
    os.environ.get("FLASK_ENV", "development"), DevelopmentConfig
)