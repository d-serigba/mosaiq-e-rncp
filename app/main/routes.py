from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select

from app import db
from app.main import bp
from app.main.forms import CommentForm, PostForm, ProfileForm
from app.models import Comment, Post, Tag, User, abonnements
from app.utils import parse_tags, remove_upload, save_image


# ------------------------------------------------------------------ helpers
def visible_post_or_404(post_id):
    post = db.get_or_404(Post, post_id)
    if not post.auteur.actif and not (current_user.is_authenticated and current_user.is_admin):
        abort(404)
    return post


def feed_query(feed=None, tag=None, pseudo=None):
    query = Post.query.join(Post.auteur).filter(User.actif.is_(True))
    if tag:
        query = query.filter(Post.tags.any(Tag.nom_tag == tag))
    if pseudo:
        query = query.filter(User.pseudo == pseudo)
    if feed == "following" and current_user.is_authenticated:
        suivis = select(abonnements.c.id_followed).where(abonnements.c.id_follower == current_user.id_user)
        query = query.filter(or_(Post.id_user.in_(suivis), Post.id_user == current_user.id_user))
    return query.order_by(Post.date_creation.desc(), Post.id_post.desc())


def serialize_post(post):
    source = post.source
    liked = current_user.is_authenticated and post.is_liked_by(current_user)
    parent = post.parent
    return {
        "id": post.id_post,
        "type": post.type_post,
        "titre": post.titre or "",
        "contenu": post.contenu_texte or "",
        "image": url_for("static", filename=post.media_url) if post.type_post == "image" and post.media_url else None,
        "lien": post.media_url if post.type_post == "lien" else None,
        "auteur": post.auteur.pseudo,
        "auteur_url": url_for("main.profile", pseudo=post.auteur.pseudo),
        "url": url_for("main.post_detail", post_id=post.id_post),
        "date": post.date_creation.strftime("%d/%m/%Y %H:%M"),
        "tags": [{"nom": t.nom_tag, "url": url_for("main.tag_page", nom=t.nom_tag)} for t in post.tags],
        "likes": post.likers.count(),
        "liked": bool(liked),
        "reblogs": Post.query.filter_by(id_post_parent=source.id_post).count(),
        "commentaires": len(post.commentaires),
        "reblog_de": (
            {
                "auteur": parent.auteur.pseudo,
                "auteur_url": url_for("main.profile", pseudo=parent.auteur.pseudo),
                "url": url_for("main.post_detail", post_id=parent.id_post),
            }
            if parent
            else None
        ),
    }


# -------------------------------------------------------------------- pages
@bp.route("/")
def index():
    feed = request.args.get("feed", "all")
    if feed == "following" and not current_user.is_authenticated:
        feed = "all"
    return render_template("index.html", feed=feed)


@bp.route("/tag/<nom>")
def tag_page(nom):
    return render_template("tag.html", nom=nom.lower())


@bp.route("/u/<pseudo>")
def profile(pseudo):
    user = User.query.filter_by(pseudo=pseudo).first_or_404()
    if not user.actif and not (current_user.is_authenticated and current_user.is_admin):
        abort(404)
    return render_template(
        "main/profile.html",
        user=user,
        nb_posts=user.posts.count(),
        nb_followers=user.followers.count(),
        nb_followed=user.followed.count(),
        following=current_user.is_authenticated and current_user.is_following(user),
    )


@bp.route("/post/new", methods=["GET", "POST"])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        kind = form.type_post.data
        media = None
        if kind == "image":
            try:
                media = save_image(form.image.data)
            except ValueError as exc:
                form.image.errors.append(str(exc))
                return render_template("main/new_post.html", form=form)
        elif kind == "lien":
            media = form.media_url.data.strip()

        post = Post(
            type_post=kind,
            titre=(form.titre.data or "").strip() or None,
            contenu_texte=(form.contenu_texte.data or "").strip() or None,
            media_url=media,
            id_user=current_user.id_user,
        )
        with db.session.no_autoflush:
            for name in parse_tags(form.tags.data):
                tag = Tag.query.filter_by(nom_tag=name).first() or Tag(nom_tag=name)
                post.tags.append(tag)
        db.session.add(post)
        db.session.commit()
        flash("Billet publié.", "success")
        return redirect(url_for("main.post_detail", post_id=post.id_post))
    return render_template("main/new_post.html", form=form)


@bp.route("/post/<int:post_id>", methods=["GET", "POST"])
def post_detail(post_id):
    post = visible_post_or_404(post_id)
    form = CommentForm()
    if form.is_submitted():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        if form.validate():
            db.session.add(Comment(contenu=form.contenu.data.strip(), id_user=current_user.id_user, id_post=post.id_post))
            db.session.commit()
            flash("Commentaire ajouté.", "success")
            return redirect(url_for("main.post_detail", post_id=post.id_post))
    data = serialize_post(post)
    return render_template("main/post_detail.html", post=post, data=data, form=form)


@bp.post("/post/<int:post_id>/delete")
@login_required
def delete_post(post_id):
    post = db.get_or_404(Post, post_id)
    if post.id_user != current_user.id_user and not current_user.is_admin:
        abort(403)
    media = post.media_url if post.type_post == "image" else None
    db.session.delete(post)
    db.session.commit()
    # Le fichier n'est supprimé que si aucun autre billet (reblog) ne l'utilise
    if media and Post.query.filter_by(media_url=media).count() == 0:
        remove_upload(media)
    flash("Billet supprimé.", "success")
    return redirect(url_for("main.index"))


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    form = ProfileForm(bio=current_user.bio)
    if form.validate_on_submit():
        current_user.bio = (form.bio.data or "").strip() or None
        if form.avatar.data and getattr(form.avatar.data, "filename", ""):
            try:
                new_avatar = save_image(form.avatar.data)
            except ValueError as exc:
                form.avatar.errors.append(str(exc))
                return render_template("main/settings.html", form=form)
            remove_upload(current_user.avatar_url)
            current_user.avatar_url = new_avatar
        db.session.commit()
        flash("Profil mis à jour.", "success")
        return redirect(url_for("main.profile", pseudo=current_user.pseudo))
    return render_template("main/settings.html", form=form)


# ---------------------------------------------------------------------- API
@bp.get("/api/posts")
def api_posts():
    page = max(request.args.get("page", 1, type=int), 1)
    query = feed_query(
        feed=request.args.get("feed"),
        tag=(request.args.get("tag") or "").lower() or None,
        pseudo=request.args.get("user") or None,
    )
    pagination = query.paginate(page=page, per_page=current_app.config["POSTS_PER_PAGE"], error_out=False)
    return jsonify(posts=[serialize_post(p) for p in pagination.items], has_next=pagination.has_next, page=page)


@bp.post("/api/post/<int:post_id>/like")
@login_required
def api_like(post_id):
    post = visible_post_or_404(post_id)
    if post.is_liked_by(current_user):
        post.likers.remove(current_user)
        liked = False
    else:
        post.likers.append(current_user)
        liked = True
    db.session.commit()
    return jsonify(liked=liked, likes=post.likers.count())


@bp.post("/api/post/<int:post_id>/reblog")
@login_required
def api_reblog(post_id):
    original = visible_post_or_404(post_id)
    # On remonte toujours au billet d'origine : la filiation reste la source réelle
    source = original.source
    if source.id_user == current_user.id_user or original.id_user == current_user.id_user:
        return jsonify(error="Vous ne pouvez pas reblogger votre propre billet."), 400
    if Post.query.filter_by(id_user=current_user.id_user, id_post_parent=source.id_post).first():
        return jsonify(error="Vous avez déjà reblogué ce billet."), 409

    reblog = Post(
        type_post=original.type_post,
        titre=original.titre,
        contenu_texte=original.contenu_texte,
        media_url=original.media_url,
        id_user=current_user.id_user,
        id_post_parent=source.id_post,
    )
    reblog.tags = list(original.tags)
    db.session.add(reblog)
    db.session.commit()
    count = Post.query.filter_by(id_post_parent=source.id_post).count()
    return jsonify(ok=True, id_post=reblog.id_post, reblogs=count, message="Billet reblogué sur votre blog."), 201


@bp.post("/api/user/<pseudo>/follow")
@login_required
def api_follow(pseudo):
    target = User.query.filter_by(pseudo=pseudo, actif=True).first_or_404()
    if target.id_user == current_user.id_user:
        return jsonify(error="Vous ne pouvez pas vous suivre vous-même."), 400
    if current_user.is_following(target):
        current_user.unfollow(target)
        following = False
    else:
        current_user.follow(target)
        following = True
    db.session.commit()
    return jsonify(following=following, followers=target.followers.count())
