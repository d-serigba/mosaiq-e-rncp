from flask import flash, redirect, render_template, url_for
from flask_login import current_user

from app import db
from app.admin import bp
from app.models import Post, User
from app.utils import admin_required, remove_upload


@bp.route("/")
@admin_required
def dashboard():
    users = User.query.order_by(User.date_inscription.desc()).all()
    posts = Post.query.order_by(Post.date_creation.desc()).limit(50).all()
    return render_template("admin/dashboard.html", users=users, posts=posts)


@bp.post("/user/<int:user_id>/toggle")
@admin_required
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id_user == current_user.id_user or user.is_admin:
        flash("Impossible de suspendre un administrateur.", "error")
    else:
        user.actif = not user.actif
        db.session.commit()
        flash(f"Compte {user.pseudo} {'réactivé' if user.actif else 'suspendu'}.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/post/<int:post_id>/delete")
@admin_required
def delete_post(post_id):
    post = db.get_or_404(Post, post_id)
    media = post.media_url if post.type_post == "image" else None
    db.session.delete(post)
    db.session.commit()
    if media and Post.query.filter_by(media_url=media).count() == 0:
        remove_upload(media)
    flash("Billet supprimé par la modération.", "success")
    return redirect(url_for("admin.dashboard"))
