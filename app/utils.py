import os
import re
import uuid
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import abort, current_app, request
from flask_login import current_user, login_required
from PIL import Image

# Format réel détecté par Pillow -> extension écrite sur le disque
IMAGE_FORMATS = {"JPEG": "jpg", "PNG": "png", "GIF": "gif", "WEBP": "webp"}
Image.MAX_IMAGE_PIXELS = 40_000_000  # protection contre les "decompression bombs"


def admin_required(view):
    """Réserve une vue aux administrateurs (401/redirection si anonyme, 403 sinon)."""

    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapper


def is_safe_url(target):
    """Vrai si `target` reste sur notre domaine (protection Open Redirect)."""
    if not target or "\\" in target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc


def save_image(file_storage):
    """Valide et enregistre une image. Retourne le chemin relatif à /static.

    Lève ValueError si le fichier est refusé.
    """
    if not file_storage or not getattr(file_storage, "filename", ""):
        raise ValueError("Aucun fichier envoyé.")

    ext = os.path.splitext(file_storage.filename)[1].lower().lstrip(".")
    if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
        raise ValueError("Extension non autorisée (png, jpg, gif, webp).")

    try:
        img = Image.open(file_storage.stream)
        img.verify()  # lève une exception si ce n'est pas une vraie image
        real_format = img.format
    except Exception:
        raise ValueError("Le fichier n'est pas une image valide.")

    if real_format not in IMAGE_FORMATS:
        raise ValueError("Format d'image non pris en charge.")

    # Nom généré : jamais celui fourni par l'utilisateur (pas d'écrasement, pas de path traversal)
    filename = f"{uuid.uuid4().hex}.{IMAGE_FORMATS[real_format]}"
    file_storage.stream.seek(0)
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
    return f"uploads/{filename}"


def remove_upload(relative_path):
    if not relative_path or not relative_path.startswith("uploads/"):
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], os.path.basename(relative_path))
    try:
        os.remove(path)
    except OSError:
        pass


def parse_tags(raw):
    tags = []
    for part in re.split(r"[,\s]+", raw or ""):
        tag = part.strip().lstrip("#").lower()
        if tag and re.fullmatch(r"[\w-]{1,30}", tag) and tag not in tags:
            tags.append(tag)
    return tags[:10]
