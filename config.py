"""Configuration de l'application (chargée depuis .env, cf. joel-bentley/pinterest-clone)."""
import os
import tempfile

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


def _database_uri():
    uri = os.environ.get("DATABASE_URL")
    if not uri:
        # Repli SQLite pour un premier lancement sans PostgreSQL
        return "sqlite:///" + os.path.join(basedir, "dev.db")
    # Heroku/Render fournissent parfois "postgres://" (déprécié par SQLAlchemy)
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-me"
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload : 5 Mo maximum, Flask renvoie automatiquement une erreur 413 au-delà
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(basedir, "app", "static", "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # Cookies de session verrouillés
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    POSTS_PER_PAGE = 12


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    UPLOAD_FOLDER = tempfile.mkdtemp(prefix="microblog_uploads_")
    POSTS_PER_PAGE = 5


class CsrfTestConfig(TestConfig):
    WTF_CSRF_ENABLED = True
