import io

import pytest
from PIL import Image

from app import create_app, db
from app.models import User
from config import CsrfTestConfig, TestConfig

PASSWORD = "Motdepasse123"


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf_client():
    app = create_app(CsrfTestConfig)
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def make_user(app):
    def _make(pseudo="alice", role="user"):
        user = User(pseudo=pseudo, email=f"{pseudo}@example.com", role=role)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return user

    return _make


@pytest.fixture
def login():
    def _login(client, pseudo):
        return client.post("/auth/login", data={"email": f"{pseudo}@example.com", "password": PASSWORD})

    return _login


@pytest.fixture
def make_post(client):
    """Publie un billet texte avec le client donné (déjà connecté) et retourne son id."""
    from app.models import Post

    def _make(client, titre="Titre", contenu="Contenu", tags=""):
        client.post(
            "/post/new",
            data={"type_post": "texte", "titre": titre, "contenu_texte": contenu, "tags": tags},
        )
        return Post.query.order_by(Post.id_post.desc()).first().id_post

    return _make


def png_file(name="photo.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buffer, "PNG")
    buffer.seek(0)
    return buffer, name
