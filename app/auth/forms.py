from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp, ValidationError

from app.models import User


class RegisterForm(FlaskForm):
    pseudo = StringField(
        "Pseudo",
        validators=[DataRequired(), Regexp(r"^[A-Za-z0-9_]{3,30}$", message="3 à 30 caractères : lettres, chiffres et _.")],
    )
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=254)])
    password = PasswordField("Mot de passe", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField(
        "Confirmation", validators=[DataRequired(), EqualTo("password", message="Les mots de passe diffèrent.")]
    )
    submit = SubmitField("Créer mon compte")

    def validate_pseudo(self, field):
        if User.query.filter(func.lower(User.pseudo) == field.data.lower()).first():
            raise ValidationError("Ce pseudo est déjà pris.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("Cette adresse est déjà utilisée.")


class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Length(max=254)])
    password = PasswordField("Mot de passe", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Rester connecté")
    submit = SubmitField("Se connecter")
