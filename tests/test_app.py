import io
import os
import re

from app import db
from app.models import Post, Tag, User
from tests.conftest import PASSWORD, png_file


# ------------------------------------------------------------ authentification
def test_password_is_hashed_and_salted(make_user):
    a = make_user("alice")
    b = make_user("bob")
    assert a.mot_de_passe_hash != PASSWORD
    assert a.mot_de_passe_hash != b.mot_de_passe_hash  # sel différent pour le même mot de passe
    assert a.check_password(PASSWORD)


def test_register_then_login(client):
    resp = client.post(
        "/auth/register",
        data={"pseudo": "carol", "email": "carol@example.com", "password": PASSWORD, "confirm": PASSWORD},
    )
    assert resp.status_code == 302
    assert User.query.filter_by(pseudo="carol").one().role == "user"
    resp = client.post("/auth/login", data={"email": "carol@example.com", "password": PASSWORD})
    assert resp.status_code == 302


def test_register_rejects_weak_or_duplicate(client, make_user):
    make_user("alice")
    resp = client.post(
        "/auth/register",
        data={"pseudo": "Alice", "email": "x@example.com", "password": "short", "confirm": "short"},
    )
    assert resp.status_code == 200
    assert User.query.count() == 1


def test_login_error_message_is_generic(client, make_user):
    make_user("alice")
    wrong_password = client.post("/auth/login", data={"email": "alice@example.com", "password": "mauvais"})
    unknown_user = client.post("/auth/login", data={"email": "inconnu@example.com", "password": "mauvais"})
    for resp in (wrong_password, unknown_user):
        assert resp.status_code == 200
        assert "Identifiants invalides." in resp.get_data(as_text=True)


def test_open_redirect_is_blocked(client, make_user):
    make_user("alice")
    data = {"email": "alice@example.com", "password": PASSWORD}
    resp = client.post("/auth/login?next=https://evil.example.com/phish", data=data)
    assert resp.headers["Location"] == "/"
    client.post("/auth/logout")
    resp = client.post("/auth/login?next=//evil.example.com", data=data)
    assert resp.headers["Location"] == "/"
    client.post("/auth/logout")
    resp = client.post("/auth/login?next=/post/new", data=data)
    assert resp.headers["Location"] == "/post/new"


def test_session_cookie_flags(app):
    cfg = create_secure_app_config()
    assert cfg["SESSION_COOKIE_HTTPONLY"] is True
    assert cfg["SESSION_COOKIE_SAMESITE"] == "Lax"
    # Secure par défaut (désactivable uniquement via .env pour le développement HTTP local)
    assert cfg["SESSION_COOKIE_SECURE"] is (os.environ.get("SESSION_COOKIE_SECURE", "1") == "1")


def create_secure_app_config():
    from config import Config

    return {k: getattr(Config, k) for k in ("SESSION_COOKIE_HTTPONLY", "SESSION_COOKIE_SAMESITE", "SESSION_COOKIE_SECURE")}


# ---------------------------------------------------------------------- billets
def test_create_text_post_with_tags(client, make_user, login):
    make_user("alice")
    login(client, "alice")
    resp = client.post(
        "/post/new",
        data={"type_post": "texte", "titre": "Hello", "contenu_texte": "Mon premier billet", "tags": "#Python, flask python"},
    )
    assert resp.status_code == 302
    post = Post.query.one()
    assert sorted(t.nom_tag for t in post.tags) == ["flask", "python"]
    assert Tag.query.count() == 2


def test_post_requires_login(client):
    resp = client.get("/post/new")
    assert resp.status_code == 302 and "/auth/login" in resp.headers["Location"]


def test_link_post_rejects_javascript_scheme(client, make_user, login):
    make_user("alice")
    login(client, "alice")
    client.post("/post/new", data={"type_post": "lien", "media_url": "javascript:alert(1)"})
    assert Post.query.count() == 0
    client.post("/post/new", data={"type_post": "lien", "media_url": "https://example.com/page"})
    assert Post.query.count() == 1


def test_html_in_post_is_escaped(client, make_user, login, make_post):
    make_user("alice")
    login(client, "alice")
    post_id = make_post(client, titre="<script>alert(1)</script>", contenu="<img src=x onerror=alert(1)>")
    body = client.get(f"/post/{post_id}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "<img src=x onerror" not in body


# ---------------------------------------------------------------- upload image
def test_valid_image_upload_is_renamed_with_uuid(app, client, make_user, login):
    make_user("alice")
    login(client, "alice")
    resp = client.post(
        "/post/new",
        data={"type_post": "image", "titre": "Photo", "image": png_file("../../evil name.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    post = Post.query.one()
    assert re.fullmatch(r"uploads/[0-9a-f]{32}\.png", post.media_url)
    assert os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], os.path.basename(post.media_url)))


def test_fake_image_is_rejected(client, make_user, login):
    make_user("alice")
    login(client, "alice")
    fake = (io.BytesIO(b"<?php system($_GET['c']); ?>"), "shell.png")
    resp = client.post(
        "/post/new", data={"type_post": "image", "image": fake}, content_type="multipart/form-data"
    )
    assert resp.status_code == 200
    assert "pas une image valide" in resp.get_data(as_text=True)
    assert Post.query.count() == 0


def test_wrong_extension_is_rejected(client, make_user, login):
    make_user("alice")
    login(client, "alice")
    buffer, _ = png_file()
    resp = client.post(
        "/post/new", data={"type_post": "image", "image": (buffer, "script.php")}, content_type="multipart/form-data"
    )
    assert resp.status_code == 200
    assert Post.query.count() == 0


def test_oversized_upload_returns_413(client, make_user, login):
    make_user("alice")
    login(client, "alice")
    big = (io.BytesIO(b"0" * (5 * 1024 * 1024 + 10)), "big.png")
    resp = client.post("/post/new", data={"type_post": "image", "image": big}, content_type="multipart/form-data")
    assert resp.status_code == 413


# ------------------------------------------------------------ interactions API
def test_api_requires_login_and_returns_json_401(client, make_user, login, make_post):
    make_user("alice")
    login(client, "alice")
    post_id = make_post(client)
    client.post("/auth/logout")
    resp = client.post(f"/api/post/{post_id}/like")
    assert resp.status_code == 401
    assert resp.get_json()["error"]


def test_like_toggle(client, make_user, login, make_post):
    make_user("alice")
    make_user("bob")
    login(client, "alice")
    post_id = make_post(client)
    client.post("/auth/logout")
    login(client, "bob")
    first = client.post(f"/api/post/{post_id}/like").get_json()
    assert first == {"liked": True, "likes": 1}
    second = client.post(f"/api/post/{post_id}/like").get_json()
    assert second == {"liked": False, "likes": 0}


def test_reblog_keeps_original_source(client, make_user, login, make_post):
    make_user("alice")
    make_user("bob")
    make_user("carol")
    login(client, "alice")
    original_id = make_post(client, titre="Source", tags="art")
    client.post("/auth/logout")

    login(client, "bob")
    resp = client.post(f"/api/post/{original_id}/reblog")
    assert resp.status_code == 201
    bob_reblog = db.session.get(Post, resp.get_json()["id_post"])
    assert bob_reblog.id_post_parent == original_id
    assert [t.nom_tag for t in bob_reblog.tags] == ["art"]
    client.post("/auth/logout")

    # Carol reblogue le reblog de Bob : la filiation pointe toujours vers l'original d'Alice
    login(client, "carol")
    resp = client.post(f"/api/post/{bob_reblog.id_post}/reblog")
    assert resp.status_code == 201
    carol_reblog = db.session.get(Post, resp.get_json()["id_post"])
    assert carol_reblog.id_post_parent == original_id
    assert resp.get_json()["reblogs"] == 2


def test_cannot_reblog_own_post_or_twice(client, make_user, login, make_post):
    make_user("alice")
    make_user("bob")
    login(client, "alice")
    post_id = make_post(client)
    assert client.post(f"/api/post/{post_id}/reblog").status_code == 400
    client.post("/auth/logout")
    login(client, "bob")
    assert client.post(f"/api/post/{post_id}/reblog").status_code == 201
    assert client.post(f"/api/post/{post_id}/reblog").status_code == 409


def test_follow_and_following_feed(client, make_user, login, make_post):
    make_user("alice")
    make_user("bob")
    login(client, "alice")
    make_post(client, titre="Billet d'Alice")
    client.post("/auth/logout")

    login(client, "bob")
    make_post(client, titre="Billet de Bob")
    assert client.get("/api/posts?feed=following").get_json()["posts"][0]["titre"] == "Billet de Bob"
    assert len(client.get("/api/posts?feed=following").get_json()["posts"]) == 1

    resp = client.post("/api/user/alice/follow").get_json()
    assert resp == {"following": True, "followers": 1}
    titles = [p["titre"] for p in client.get("/api/posts?feed=following").get_json()["posts"]]
    assert set(titles) == {"Billet d'Alice", "Billet de Bob"}
    assert client.post("/api/user/bob/follow").status_code == 400  # pas d'auto-abonnement


def test_api_posts_pagination_and_tag_filter(client, make_user, login, make_post):
    make_user("alice")
    login(client, "alice")
    for i in range(7):
        make_post(client, titre=f"Billet {i}", tags="even" if i % 2 == 0 else "odd")
    page1 = client.get("/api/posts?page=1").get_json()
    page2 = client.get("/api/posts?page=2").get_json()
    assert len(page1["posts"]) == 5 and page1["has_next"] is True
    assert len(page2["posts"]) == 2 and page2["has_next"] is False
    assert page1["posts"][0]["titre"] == "Billet 6"  # ordre antéchronologique
    assert len(client.get("/api/posts?tag=even").get_json()["posts"]) == 4


def test_delete_post_only_by_owner_or_admin(client, make_user, login, make_post):
    make_user("alice")
    make_user("bob")
    login(client, "alice")
    post_id = make_post(client)
    client.post("/auth/logout")
    login(client, "bob")
    assert client.post(f"/post/{post_id}/delete").status_code == 403
    client.post("/auth/logout")
    login(client, "alice")
    assert client.post(f"/post/{post_id}/delete").status_code == 302
    assert Post.query.count() == 0


# ---------------------------------------------------------------- administration
def test_admin_required(client, make_user, login):
    make_user("alice")
    make_user("root", role="admin")
    assert client.get("/admin/").status_code == 302  # anonyme -> connexion
    login(client, "alice")
    assert client.get("/admin/").status_code == 403
    client.post("/auth/logout")
    login(client, "root")
    assert client.get("/admin/").status_code == 200


def test_admin_can_suspend_user_and_delete_post(client, make_user, login, make_post):
    alice = make_user("alice")
    make_user("root", role="admin")
    login(client, "alice")
    post_id = make_post(client)
    client.post("/auth/logout")

    login(client, "root")
    assert client.post(f"/admin/user/{alice.id_user}/toggle").status_code == 302
    assert db.session.get(User, alice.id_user).actif is False
    assert client.get("/api/posts").get_json()["posts"] == []  # billets masqués
    assert client.post(f"/admin/post/{post_id}/delete").status_code == 302
    assert Post.query.count() == 0
    client.post("/auth/logout")

    resp = client.post("/auth/login", data={"email": "alice@example.com", "password": PASSWORD})
    assert resp.status_code == 200  # compte suspendu : connexion refusée


# ------------------------------------------------------------------------ CSRF
def test_csrf_is_enforced_on_forms_and_api(csrf_client):
    resp = csrf_client.post("/auth/login", data={"email": "a@example.com", "password": "x"})
    assert resp.status_code == 400
    resp = csrf_client.post("/api/post/1/like")
    assert resp.status_code == 400


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
