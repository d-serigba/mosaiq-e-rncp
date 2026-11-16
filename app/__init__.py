import os

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Connectez-vous pour accéder à cette page."
login_manager.login_message_category = "error"


@login_manager.unauthorized_handler
def unauthorized():
    # Les appels fetch() vers /api/ reçoivent du JSON 401 plutôt qu'une redirection HTML
    if request.path.startswith("/api/"):
        return jsonify(error="Authentification requise."), 401
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app import models  # noqa: F401  (enregistre les modèles)
    from app.admin import bp as admin_bp
    from app.auth import bp as auth_bp
    from app.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from app.cli import register_cli

    register_cli(app)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        return resp

    def error_page(code, message):
        if request.path.startswith("/api/"):
            return jsonify(error=message), code
        return render_template("error.html", code=code, message=message), code

    @app.errorhandler(400)
    def bad_request(e):
        return error_page(400, "Requête invalide ou jeton CSRF manquant/expiré.")

    @app.errorhandler(403)
    def forbidden(e):
        return error_page(403, "Accès interdit.")

    @app.errorhandler(404)
    def not_found(e):
        return error_page(404, "Page introuvable.")

    @app.errorhandler(413)
    def too_large(e):
        return error_page(413, "Fichier trop volumineux (5 Mo maximum).")

    return app
