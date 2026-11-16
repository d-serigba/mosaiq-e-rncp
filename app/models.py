from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- tables N,N
likes = db.Table(
    "likes",
    db.Column("id_user", db.Integer, db.ForeignKey("utilisateur.id_user", ondelete="CASCADE"), primary_key=True),
    db.Column("id_post", db.Integer, db.ForeignKey("billet.id_post", ondelete="CASCADE"), primary_key=True),
    db.Column("date_like", db.DateTime(timezone=True), default=utcnow, nullable=False),
)

post_tags = db.Table(
    "post_tags",
    db.Column("id_post", db.Integer, db.ForeignKey("billet.id_post", ondelete="CASCADE"), primary_key=True),
    db.Column("id_tag", db.Integer, db.ForeignKey("tag.id_tag", ondelete="CASCADE"), primary_key=True),
)

abonnements = db.Table(
    "abonnements",
    db.Column("id_follower", db.Integer, db.ForeignKey("utilisateur.id_user", ondelete="CASCADE"), primary_key=True),
    db.Column("id_followed", db.Integer, db.ForeignKey("utilisateur.id_user", ondelete="CASCADE"), primary_key=True),
    db.Column("date_suivi", db.DateTime(timezone=True), default=utcnow, nullable=False),
)


# ------------------------------------------------------------------ entités
class User(UserMixin, db.Model):
    __tablename__ = "utilisateur"

    id_user = db.Column(db.Integer, primary_key=True)
    pseudo = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    mot_de_passe_hash = db.Column(db.String(256), nullable=False)
    avatar_url = db.Column(db.String(255))
    bio = db.Column(db.String(300))
    role = db.Column(db.String(10), nullable=False, default="user")
    # Champ ajouté au MCD pour permettre à l'admin de suspendre un compte
    actif = db.Column(db.Boolean, nullable=False, default=True)
    date_inscription = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (db.CheckConstraint("role IN ('user', 'admin')", name="ck_utilisateur_role"),)

    posts = db.relationship("Post", back_populates="auteur", lazy="dynamic")
    followed = db.relationship(
        "User",
        secondary=abonnements,
        primaryjoin=lambda: User.id_user == abonnements.c.id_follower,
        secondaryjoin=lambda: User.id_user == abonnements.c.id_followed,
        backref=db.backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )

    # Flask-Login utilise get_id(); la PK ne s'appelle pas "id"
    def get_id(self):
        return str(self.id_user)

    @property
    def is_active(self):
        return bool(self.actif)

    @property
    def is_admin(self):
        return self.role == "admin"

    def set_password(self, password):
        # Hachage + sel aléatoire gérés par Werkzeug
        self.mot_de_passe_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.mot_de_passe_hash, password)

    def is_following(self, user):
        return self.followed.filter(abonnements.c.id_followed == user.id_user).count() > 0

    def follow(self, user):
        if user.id_user != self.id_user and not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)


class Post(db.Model):
    __tablename__ = "billet"

    id_post = db.Column(db.Integer, primary_key=True)
    type_post = db.Column(db.String(10), nullable=False)
    titre = db.Column(db.String(150))
    contenu_texte = db.Column(db.Text)
    # image : chemin relatif à /static ; lien : URL http(s) externe
    media_url = db.Column(db.String(500))
    date_creation = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    id_user = db.Column(db.Integer, db.ForeignKey("utilisateur.id_user", ondelete="CASCADE"), nullable=False, index=True)
    # Relation réflexive : billet source lors d'un reblog
    id_post_parent = db.Column(db.Integer, db.ForeignKey("billet.id_post", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        db.CheckConstraint("type_post IN ('texte', 'image', 'citation', 'lien')", name="ck_billet_type"),
    )

    auteur = db.relationship("User", back_populates="posts")
    parent = db.relationship("Post", remote_side=[id_post], backref="reblogs")
    tags = db.relationship("Tag", secondary=post_tags, back_populates="posts")
    commentaires = db.relationship(
        "Comment", back_populates="billet", cascade="all, delete-orphan", order_by="Comment.date_creation"
    )
    likers = db.relationship("User", secondary=likes, backref=db.backref("liked_posts", lazy="dynamic"), lazy="dynamic")

    def is_liked_by(self, user):
        return self.likers.filter(User.id_user == user.id_user).count() > 0

    @property
    def source(self):
        """Billet d'origine (le billet lui-même s'il n'est pas un reblog)."""
        return self.parent or self


class Tag(db.Model):
    __tablename__ = "tag"

    id_tag = db.Column(db.Integer, primary_key=True)
    nom_tag = db.Column(db.String(30), unique=True, nullable=False, index=True)

    posts = db.relationship("Post", secondary=post_tags, back_populates="tags")


class Comment(db.Model):
    __tablename__ = "commentaire"

    id_commentaire = db.Column(db.Integer, primary_key=True)
    contenu = db.Column(db.String(1000), nullable=False)
    date_creation = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    id_user = db.Column(db.Integer, db.ForeignKey("utilisateur.id_user", ondelete="CASCADE"), nullable=False)
    id_post = db.Column(db.Integer, db.ForeignKey("billet.id_post", ondelete="CASCADE"), nullable=False, index=True)

    auteur = db.relationship("User")
    billet = db.relationship("Post", back_populates="commentaires")


@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    # Un compte suspendu perd immédiatement sa session
    return user if user and user.actif else None
