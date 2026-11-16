# mosaïq(e) — microblogging visuel en grille Masonry

Projet RNCP niveau 5 : plateforme inspirée de Tumblr (billets texte / image / citation / lien, tags, likes, reblogs, abonnements) avec un affichage en grille Masonry façon Pinterest.

**Stack** : Flask (Blueprints `auth`, `main`, `admin`) · SQLAlchemy · PostgreSQL (SQLite en repli) · HTML5 / CSS3 Flexbox mobile-first · JavaScript vanilla (`fetch()`).

## Installation

```bash
python -m venv venv && source venv/bin/activate     # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # puis éditer SECRET_KEY et DATABASE_URL
```

### PostgreSQL

```sql
CREATE USER microblog_user WITH PASSWORD 'motdepasse';
CREATE DATABASE microblog OWNER microblog_user;
```

Sans `DATABASE_URL`, l'application utilise SQLite (`dev.db`) : pratique pour un premier test.

### Lancement

```bash
flask init-db                         # crée les tables
flask create-admin admin admin@example.com   # compte administrateur (mot de passe demandé)
flask seed-demo                       # (optionnel) 30 billets de démonstration
flask run --debug                     # http://127.0.0.1:5000
```

En développement HTTP local, mettre `SESSION_COOKIE_SECURE=0` dans `.env` (à laisser à `1` en production HTTPS).

### Tests

```bash
pytest -v
```

### Production (serveur WSGI)

```bash
gunicorn -w 3 -b 127.0.0.1:8000 wsgi:app    # derrière Nginx avec HTTPS
```

## Architecture

```
app/
  __init__.py      application factory, extensions, en-têtes de sécurité, gestion d'erreurs
  models.py        User, Post (réflexif), Tag, Comment + tables likes / post_tags / abonnements
  utils.py         @admin_required, is_safe_url, save_image (Pillow + UUID), parse_tags
  cli.py           flask init-db | create-admin | seed-demo
  auth/            inscription, connexion, déconnexion (Flask-Login)
  main/            pages, billets, commentaires, API JSON (like, reblog, follow, posts)
  admin/           modération des comptes et des billets
  templates/ static/ (css, js : app.js, masonry.js, post_form.js)
tests/             25 tests pytest
config.py wsgi.py  configuration (.env) et point d'entrée WSGI
```

## Routes principales

| Méthode | URL | Rôle |
|---|---|---|
| GET | `/` , `/tag/<nom>` , `/u/<pseudo>` | grille Masonry (global, tag, profil) |
| GET | `/api/posts?page=&feed=&tag=&user=` | billets paginés (JSON) |
| POST | `/api/post/<id>/like` | bascule le « J'aime » |
| POST | `/api/post/<id>/reblog` | reblog avec filiation vers la source originale |
| POST | `/api/user/<pseudo>/follow` | s'abonner / se désabonner |
| GET/POST | `/post/new`, `/post/<id>`, `/settings` | création, détail + commentaires, profil |
| GET/POST | `/admin/` … | modération (`@admin_required`) |

## Sécurité (pour le jury)

| Risque | Mesure |
|---|---|
| Mots de passe | `generate_password_hash` (Werkzeug, sel automatique) ; hash factice vérifié si l'e-mail est inconnu |
| Sessions | cookies `HttpOnly`, `SameSite=Lax`, `Secure` ; compte suspendu = session invalidée |
| Énumération de comptes | message de connexion générique |
| Open Redirect | `is_safe_url()` sur le paramètre `next` |
| Upload | 5 Mo max (`MAX_CONTENT_LENGTH`), extension autorisée, `Image.open().verify()`, format réel détecté, nom `UUID` |
| Injection SQL | ORM SQLAlchemy, requêtes paramétrées |
| XSS | échappement Jinja2 ; JS : `textContent` uniquement ; liens `lien` limités à http(s) ; CSP `script-src 'self'` |
| CSRF | `CSRFProtect` + jeton dans les formulaires et en-tête `X-CSRFToken` dans les `fetch()` |
| Contrôle d'accès | `@admin_required`, suppression réservée à l'auteur ou à l'admin |

## Écarts par rapport au MCD initial

- `UTILISATEUR.actif` (booléen) ajouté pour que l'administrateur puisse suspendre un compte.
- Contraintes `CHECK` sur `role` et `type_post`.

## Pistes d'amélioration (à mentionner dans le bilan)

Flask-Migrate (migrations), limitation du débit de connexion (Flask-Limiter), redimensionnement/ré-encodage des images, recherche, notifications.
