import click

from app import db
from app.models import Post, Tag, User


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Crée les tables."""
        db.create_all()
        click.echo("Base initialisée.")

    @app.cli.command("create-admin")
    @click.argument("pseudo")
    @click.argument("email")
    @click.password_option()
    def create_admin(pseudo, email, password):
        """Crée un compte administrateur."""
        db.create_all()
        user = User(pseudo=pseudo, email=email.lower(), role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrateur {pseudo} créé.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Ajoute des billets de démonstration (pour visualiser la grille Masonry)."""
        db.create_all()
        users = []
        for pseudo in ("demo_alice", "demo_bob"):
            user = User.query.filter_by(pseudo=pseudo).first()
            if not user:
                user = User(pseudo=pseudo, email=f"{pseudo}@example.com", bio="Compte de démonstration")
                user.set_password("demo-password-123")
                db.session.add(user)
            users.append(user)
        db.session.commit()

        lorem = "Un billet de démonstration. " * 3
        samples = [
            ("texte", "Premier billet", lorem, None, ["demo", "texte"]),
            ("citation", "Citation", "La simplicité est la sophistication suprême. " * 2, None, ["citation"]),
            ("lien", "Documentation Flask", "Le micro-framework Python.", "https://flask.palletsprojects.com/", ["python", "flask"]),
            ("texte", "Billet long", lorem * 6, None, ["demo", "long"]),
            ("texte", "Court", "Salut !", None, ["demo"]),
        ]
        for i in range(30):
            type_post, titre, contenu, media, tags = samples[i % len(samples)]
            post = Post(
                type_post=type_post,
                titre=f"{titre} #{i + 1}",
                contenu_texte=contenu,
                media_url=media,
                id_user=users[i % 2].id_user,
            )
            with db.session.no_autoflush:
                for name in tags:
                    tag = Tag.query.filter_by(nom_tag=name).first() or Tag(nom_tag=name)
                    post.tags.append(tag)
            db.session.add(post)
            db.session.flush()  # rend les nouveaux tags visibles pour l'itération suivante
        db.session.commit()
        click.echo("30 billets de démonstration créés.")
