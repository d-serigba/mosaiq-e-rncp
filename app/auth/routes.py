from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegisterForm
from app.models import User
from app.utils import is_safe_url

# Hash factice : on le vérifie même si l'e-mail n'existe pas (temps de réponse constant)
_DUMMY_HASH = generate_password_hash("mot-de-passe-factice")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(pseudo=form.pseudo.data.strip(), email=form.email.data.strip().lower())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Compte créé : vous pouvez vous connecter.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user is None:
            check_password_hash(_DUMMY_HASH, form.password.data)
            valid = False
        else:
            valid = user.check_password(form.password.data) and user.actif
        if not valid:
            # Message volontairement générique : pas d'énumération des comptes
            flash("Identifiants invalides.", "error")
            return render_template("auth/login.html", form=form)
        login_user(user, remember=form.remember.data)
        next_url = request.args.get("next")
        if not next_url or not is_safe_url(next_url):
            next_url = url_for("main.index")
        return redirect(next_url)
    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous êtes déconnecté.", "success")
    return redirect(url_for("main.index"))
