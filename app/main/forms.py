import re

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

TYPES = [("texte", "Texte"), ("image", "Image"), ("citation", "Citation"), ("lien", "Lien")]


class PostForm(FlaskForm):
    type_post = SelectField("Type de billet", choices=TYPES, validators=[DataRequired()])
    titre = StringField("Titre", validators=[Optional(), Length(max=150)])
    contenu_texte = TextAreaField("Contenu", validators=[Optional(), Length(max=5000)])
    media_url = StringField("Adresse du lien (https://…)", validators=[Optional(), Length(max=500)])
    image = FileField("Image (5 Mo maximum)")
    tags = StringField("Tags (séparés par des espaces ou virgules)", validators=[Optional(), Length(max=300)])
    submit = SubmitField("Publier")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        if not ok:
            return False
        kind = self.type_post.data
        if kind in ("texte", "citation") and not (self.contenu_texte.data or "").strip():
            self.contenu_texte.errors.append("Le contenu est obligatoire pour ce type de billet.")
            ok = False
        if kind == "image" and not (self.image.data and getattr(self.image.data, "filename", "")):
            self.image.errors.append("Choisissez une image.")
            ok = False
        if kind == "lien":
            url = (self.media_url.data or "").strip()
            # Seuls http(s) sont acceptés : bloque les liens javascript:
            if not re.match(r"^https?://\S+$", url, re.I):
                self.media_url.errors.append("Saisissez une adresse commençant par http:// ou https://")
                ok = False
        return ok


class CommentForm(FlaskForm):
    contenu = TextAreaField("Votre commentaire", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Commenter")


class ProfileForm(FlaskForm):
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=300)])
    avatar = FileField("Avatar (optionnel)")
    submit = SubmitField("Enregistrer")
