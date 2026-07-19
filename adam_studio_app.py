import hashlib
import hmac
import os
import sqlite3
import smtplib
import urllib.parse
from datetime import datetime
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_file, send_from_directory, session, url_for
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-adam-studio-secret")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"
BASE_DIR = Path(__file__).resolve().parent
SHOP_DB = Path(os.environ.get("SHOP_DB", BASE_DIR / "shop.db"))
UPLOAD_DIR = BASE_DIR / "static" / "shop_uploads"
UPLOADS_DIR = BASE_DIR / "uploads"
INSTALLERS_DIR = UPLOADS_DIR / "installers"
ICONS_DIR = UPLOADS_DIR / "icons"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
INSTALLERS_DIR.mkdir(parents=True, exist_ok=True)
ICONS_DIR.mkdir(parents=True, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

INSTALLER_EXTENSIONS = {".exe", ".msi"}
BROWSER_EXTENSIONS = {".zip"}
ICON_EXTENSIONS = {".ico", ".png"}
THUMBNAIL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
TEAM_MEMBERS_FILE = BASE_DIR / "team_members.txt"


def load_team_members():
    members = [
        {
            "name": "Adam Cools",
            "role": "CEO",
            "description": "Leading the vision, strategy, and future of Adam Studio.",
        },
        {
            "name": "Emir Yilmaz",
            "role": "Model",
            "description": "Representing the brand with style, quality, and presence.",
        },
        {
            "name": "Nura Akar",
            "role": "Tester",
            "description": (
                "Testing the experience and helping the studio find problems "
                "before players do."
            ),
        },
    ]
    for line in TEAM_MEMBERS_FILE.read_text(encoding="utf-8").splitlines():
        if " — " not in line:
            continue
        name, role = line.split(" — ", 1)
        members.append(
            {"name": name.strip(), "role": role.strip(), "description": ""}
        )
    return members


TEAM_MEMBERS = load_team_members()


def canonical_site_url():
    return (
        os.environ.get("CANONICAL_SITE_URL")
        or os.environ.get("SITE_URL")
        or ""
    ).rstrip("/")


def should_redirect_to_canonical_host(current_host, canonical_host):
    if not canonical_host or not current_host:
        return False
    current_host = current_host.split(":", 1)[0].lower()
    canonical_host = canonical_host.split(":", 1)[0].lower()
    if current_host == canonical_host:
        return False
    if current_host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return False
    if current_host.endswith(".onrender.com"):
        return True
    return os.environ.get("FORCE_CANONICAL_DOMAIN", "0") == "1"


@app.before_request
def redirect_to_custom_domain():
    target = canonical_site_url()
    if not target:
        return None
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if not should_redirect_to_canonical_host(request.host, parsed.netloc):
        return None
    path = request.full_path if request.query_string else request.path
    return redirect(urllib.parse.urljoin(target + "/", path.lstrip("/")), code=308)


@app.route("/")
def home():
    return render_template(
        "adam_studio.html",
        adam_studio_home_url="/",
        team_members=TEAM_MEMBERS,
    )


@app.route("/sitemap.xml")
def sitemap():
    site_url = canonical_site_url() or request.url_root.rstrip("/")
    public_paths = ("/", "/shop", "/help")
    urls = [urllib.parse.urljoin(site_url + "/", path.lstrip("/")) for path in public_paths]
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for page_url in urls:
        xml.extend(("  <url>", f"    <loc>{page_url}</loc>", "  </url>"))
    xml.append("</urlset>")
    return "\n".join(xml), 200, {"Content-Type": "application/xml"}


@app.route("/robots.txt")
def robots_txt():
    site_url = canonical_site_url() or request.url_root.rstrip("/")
    body = "\n".join(
        (
            "User-agent: *",
            "Allow: /",
            f"Sitemap: {site_url}/sitemap.xml",
        )
    )
    return body, 200, {"Content-Type": "text/plain"}


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def get_shop_db():
    db = sqlite3.connect(SHOP_DB)
    db.row_factory = sqlite3.Row
    return db


def init_shop_db():
    with get_shop_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS shop_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                price_cents INTEGER NOT NULL DEFAULT 0,
                download_url TEXT NOT NULL DEFAULT '',
                file_name TEXT NOT NULL DEFAULT '',
                cover_color TEXT NOT NULL DEFAULT '#1b2838',
                created_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row["name"] for row in db.execute("PRAGMA table_info(shop_games)").fetchall()
        }
        if "thumbnail" not in columns:
            db.execute("ALTER TABLE shop_games ADD COLUMN thumbnail TEXT NOT NULL DEFAULT ''")
        if "game_type" not in columns:
            db.execute("ALTER TABLE shop_games ADD COLUMN game_type TEXT NOT NULL DEFAULT 'browser'")
        if "icon_path" not in columns:
            db.execute("ALTER TABLE shop_games ADD COLUMN icon_path TEXT NOT NULL DEFAULT ''")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, game_id)
            )
            """
        )
        db.execute(
            """
            DELETE FROM shop_games
            WHERE title IN (
                'Gexora Starter Pack',
                'Adam Studio Prototype',
                'Community Test Build'
            )
            """
        )


def upload_extension(file):
    return Path(file.filename or "").suffix.lower()


def saved_upload(form_name, allowed_extensions=None, target_dir=UPLOAD_DIR, required=False, label="Upload"):
    file = request.files.get(form_name)
    if not file or not file.filename:
        if required:
            raise ValueError(f"{label} is required.")
        return ""
    if allowed_extensions and upload_extension(file) not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValueError(f"{label} must be one of: {allowed}.")
    file_name = f"{int(datetime.utcnow().timestamp())}-{secure_filename(file.filename)}"
    target_dir.mkdir(parents=True, exist_ok=True)
    file.save(target_dir / file_name)
    return file_name


def cleanup_upload(file_name):
    if not file_name:
        return
    for directory in (UPLOAD_DIR, INSTALLERS_DIR, ICONS_DIR):
        try:
            (directory / file_name).unlink()
        except FileNotFoundError:
            pass


def installer_file_path(file_name):
    if not file_name:
        return None
    for directory in (INSTALLERS_DIR, UPLOAD_DIR):
        path = directory / file_name
        if path.exists():
            return path
    return None


def validate_game_type(value):
    value = (value or "browser").strip()
    if value not in {"browser", "installer"}:
        raise ValueError("Choose Browser Game (ZIP) or Desktop Game (Installer).")
    return value


def current_shop_user():
    username = session.get("gexora_username")
    if not username:
        return None
    return {
        "id": username,
        "username": username,
        "email": session.get("gexora_email", ""),
        "is_admin": bool(session.get("gexora_is_admin")),
    }


def shop_owner_emails():
    values = os.environ.get("ADAM_STUDIO_OWNER_EMAILS", "coolsadam00@gmail.com")
    return {value.strip().lower() for value in values.split(",") if value.strip()}


def shop_owner_usernames():
    values = os.environ.get("ADAM_STUDIO_OWNER_USERNAMES", "adminadam2155,coolsadam00")
    return {value.strip().lower() for value in values.split(",") if value.strip()}


def is_shop_admin(user=None):
    user = user or current_shop_user()
    if not user:
        return False
    return bool(
        user.get("is_admin")
        or user.get("email", "").lower() in shop_owner_emails()
        or user.get("username", "").lower() in shop_owner_usernames()
    )


def gexora_login_url(force=False):
    url = os.environ.get(
        "GEXORA_LOGIN_URL",
        "https://gexora.onrender.com/adam-studio-login",
    )
    if not force:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}force=1"


def gexora_register_url():
    return os.environ.get(
        "GEXORA_REGISTER_URL",
        "https://gexora.onrender.com/login?next=/adam-studio-login",
    )


def gexora_shared_secret():
    return os.environ.get("GEXORA_SHARED_SECRET", "change-this-gexora-shared-secret")


def price_label(price_cents):
    if price_cents <= 0:
        return "Free"
    return f"EUR {price_cents / 100:.2f}"


@app.context_processor
def shop_template_helpers():
    return {"price_label": price_label}


@app.route("/shop")
def shop():
    init_shop_db()
    user = current_shop_user()
    with get_shop_db() as db:
        games = db.execute("SELECT * FROM shop_games ORDER BY id DESC").fetchall()
        owned_ids = set()
        if user:
            owned_ids = {
                row["game_id"]
                for row in db.execute(
                    "SELECT game_id FROM library WHERE user_id = ?", (user["id"],)
                ).fetchall()
            }
    return render_template(
        "shop.html",
        adam_studio_home_url="/",
        games=games,
        gexora_login_url=gexora_login_url(),
        gexora_register_url=gexora_register_url(),
        is_admin=is_shop_admin(user),
        message=request.args.get("message", ""),
        owned_ids=owned_ids,
        user=user,
    )


@app.route("/admin")
def admin():
    init_shop_db()
    if not is_shop_admin():
        return redirect(gexora_login_url())
    with get_shop_db() as db:
        games = db.execute("SELECT * FROM shop_games ORDER BY id DESC").fetchall()
    return render_template(
        "shop_admin.html",
        adam_studio_home_url="/",
        games=games,
        message=request.args.get("message", ""),
        user=current_shop_user(),
    )


@app.route("/libery")
def libery():
    init_shop_db()
    user = current_shop_user()
    games = []
    if user:
        with get_shop_db() as db:
            games = db.execute(
                """
                SELECT shop_games.*
                FROM shop_games
                JOIN library ON library.game_id = shop_games.id
                WHERE library.user_id = ?
                ORDER BY library.id DESC
                """,
                (user["id"],),
            ).fetchall()
    return render_template(
        "libery.html",
        adam_studio_home_url="/",
        games=games,
        gexora_login_url=gexora_login_url(),
        message=request.args.get("message", ""),
        user=user,
    )


@app.route("/shop/gexora-return")
def shop_gexora_return():
    username = clean_field(request.args.get("username"), 40).lower()
    email = clean_field(request.args.get("email"), 254).lower()
    is_admin_value = "1" if request.args.get("admin") == "1" else "0"
    token = request.args.get("token") or ""
    shared_secret = gexora_shared_secret()
    expected = ""
    if username and shared_secret:
        payload = "|".join([username, email, is_admin_value])
        expected = hmac.new(
            shared_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    if username and expected and hmac.compare_digest(token, expected):
        session["gexora_username"] = username
        session["gexora_email"] = email
        session["gexora_is_admin"] = is_admin_value == "1"
        return redirect(url_for("shop", message="Gexora login connected."))
    return redirect(url_for("shop", message="Gexora login return is not configured yet."))


@app.post("/shop/logout")
def shop_logout():
    session.pop("gexora_username", None)
    session.pop("gexora_email", None)
    session.pop("gexora_is_admin", None)
    return redirect(url_for("shop_logout_choice"))


@app.route("/shop/logout-choice")
def shop_logout_choice():
    return render_template(
        "shop_logout_choice.html",
        adam_studio_home_url="/",
        continue_url=gexora_login_url(),
        manual_login_url=gexora_login_url(force=True),
    )


@app.post("/shop/claim/<int:game_id>")
def claim_game(game_id):
    init_shop_db()
    user = current_shop_user()
    if not user:
        return redirect(gexora_login_url())
    with get_shop_db() as db:
        game = db.execute("SELECT * FROM shop_games WHERE id = ?", (game_id,)).fetchone()
        if not game:
            return redirect(url_for("shop", message="Game not found."))
        if game["price_cents"] > 0:
            return redirect(url_for("shop", message="Paid checkout is coming soon."))
        db.execute(
            "INSERT OR IGNORE INTO library (user_id, game_id, created_at) VALUES (?, ?, ?)",
            (user["id"], game_id, now_iso()),
        )
    return redirect(url_for("libery", message=f"{game['title']} added to your library."))


@app.post("/shop/install/<int:game_id>")
def install_game(game_id):
    init_shop_db()
    user = current_shop_user()
    if not user:
        return redirect(gexora_login_url())
    with get_shop_db() as db:
        row = db.execute(
            """
            SELECT shop_games.*
            FROM shop_games
            JOIN library ON library.game_id = shop_games.id
            WHERE shop_games.id = ? AND library.user_id = ?
            """,
            (game_id, user["id"]),
        ).fetchone()
    if not row:
        return redirect(url_for("shop", message="Claim the game before installing."))
    if row["game_type"] == "installer" and row["file_name"]:
        return redirect(url_for("download_game", game_id=game_id))
    if row["file_name"]:
        return send_from_directory(UPLOAD_DIR, row["file_name"], as_attachment=True)
    if row["download_url"]:
        return redirect(row["download_url"])
    return redirect(url_for("shop", message="No installer is uploaded yet."))


@app.get("/download/<int:game_id>")
def download_game(game_id):
    init_shop_db()
    with get_shop_db() as db:
        row = db.execute("SELECT * FROM shop_games WHERE id = ?", (game_id,)).fetchone()
    if not row or row["game_type"] != "installer" or not row["file_name"]:
        abort(404)
    path = installer_file_path(row["file_name"])
    if not path:
        abort(404)
    return send_file(path, as_attachment=True, download_name=row["file_name"])


@app.get("/uploads/icons/<path:file_name>")
def uploaded_icon(file_name):
    return send_from_directory(ICONS_DIR, file_name)


@app.post("/shop/admin")
def shop_admin():
    init_shop_db()
    if not is_shop_admin():
        return redirect(url_for("shop", message="Admin login required."))
    action = request.form.get("action")
    with get_shop_db() as db:
        if action == "create":
            try:
                game_type = validate_game_type(request.form.get("game_type"))
                if game_type == "installer":
                    file_name = saved_upload(
                        "installer_file",
                        INSTALLER_EXTENSIONS,
                        INSTALLERS_DIR,
                        required=True,
                        label="Installer",
                    )
                else:
                    file_name = saved_upload(
                        "game_file",
                        BROWSER_EXTENSIONS,
                        UPLOAD_DIR,
                        required=True,
                        label="Browser game ZIP",
                    )
                icon_file = saved_upload("icon_file", ICON_EXTENSIONS, ICONS_DIR, label="Icon")
                thumbnail_file = saved_upload("thumbnail_file", THUMBNAIL_EXTENSIONS, UPLOAD_DIR, label="Thumbnail")
            except ValueError as error:
                return redirect(url_for("admin", message=str(error)))
            price = max(0, int(float(request.form.get("price", "0") or 0) * 100))
            db.execute(
                """
                INSERT INTO shop_games
                    (title, description, price_cents, download_url, file_name, cover_color,
                     thumbnail, game_type, icon_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_field(request.form.get("title"), 120) or "Untitled Game",
                    clean_message(request.form.get("description"), 800)
                    or "New Adam Studio game.",
                    price,
                    clean_field(request.form.get("download_url"), 500),
                    file_name,
                    clean_field(request.form.get("cover_color"), 16) or "#1b2838",
                    thumbnail_file or clean_field(request.form.get("thumbnail_url"), 500),
                    game_type,
                    icon_file,
                    now_iso(),
                ),
            )
        elif action == "update":
            game_id = int(request.form.get("game_id", "0") or 0)
            price = max(0, int(float(request.form.get("price", "0") or 0) * 100))
            game = db.execute("SELECT * FROM shop_games WHERE id = ?", (game_id,)).fetchone()
            if not game:
                return redirect(url_for("shop", message="Game not found."))
            try:
                game_type = validate_game_type(request.form.get("game_type") or game["game_type"])
                if game_type == "installer":
                    file_name = saved_upload("installer_file", INSTALLER_EXTENSIONS, INSTALLERS_DIR, label="Installer")
                else:
                    file_name = saved_upload("game_file", BROWSER_EXTENSIONS, UPLOAD_DIR, label="Browser game ZIP")
                icon_file = saved_upload("icon_file", ICON_EXTENSIONS, ICONS_DIR, label="Icon")
                thumbnail_file = saved_upload("thumbnail_file", THUMBNAIL_EXTENSIONS, UPLOAD_DIR, label="Thumbnail")
            except ValueError as error:
                return redirect(url_for("admin", message=str(error)))
            if file_name and game["file_name"]:
                cleanup_upload(game["file_name"])
            if icon_file and game["icon_path"]:
                cleanup_upload(game["icon_path"])
            if thumbnail_file and game["thumbnail"] and not game["thumbnail"].startswith(("http://", "https://")):
                cleanup_upload(game["thumbnail"])
            db.execute(
                """
                UPDATE shop_games
                SET title = ?,
                    description = ?,
                    price_cents = ?,
                    download_url = ?,
                    file_name = CASE WHEN ? != '' THEN ? ELSE file_name END,
                    cover_color = ?,
                    thumbnail = CASE WHEN ? != '' THEN ? ELSE thumbnail END,
                    game_type = ?,
                    icon_path = CASE WHEN ? != '' THEN ? ELSE icon_path END
                WHERE id = ?
                """,
                (
                    clean_field(request.form.get("title"), 120) or game["title"],
                    clean_message(request.form.get("description"), 800) or game["description"],
                    price,
                    clean_field(request.form.get("download_url"), 500),
                    file_name,
                    file_name,
                    clean_field(request.form.get("cover_color"), 16) or game["cover_color"],
                    thumbnail_file or clean_field(request.form.get("thumbnail_url"), 500),
                    thumbnail_file or clean_field(request.form.get("thumbnail_url"), 500),
                    game_type,
                    icon_file,
                    icon_file,
                    game_id,
                ),
            )
        elif action == "delete":
            game_id = int(request.form.get("game_id", "0") or 0)
            game = db.execute("SELECT file_name, thumbnail, icon_path FROM shop_games WHERE id = ?", (game_id,)).fetchone()
            if game:
                cleanup_upload(game["file_name"])
                cleanup_upload(game["icon_path"])
                if game["thumbnail"] and not game["thumbnail"].startswith(("http://", "https://")):
                    cleanup_upload(game["thumbnail"])
            db.execute("DELETE FROM library WHERE game_id = ?", (game_id,))
            db.execute("DELETE FROM shop_games WHERE id = ?", (game_id,))
    return redirect(url_for("admin", message="Shop updated."))


def clean_field(value, limit):
    return " ".join((value or "").split())[:limit]


def clean_message(value, limit=4000):
    return (value or "").strip()[:limit]


def safe_reply_to(email):
    parsed = parseaddr(email or "")[1]
    if "@" not in parsed or "\n" in parsed or "\r" in parsed:
        return ""
    return parsed[:254]


def send_help_request(form):
    support_email = os.environ.get("SUPPORT_EMAIL")
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_from = os.environ.get("SMTP_FROM") or smtp_username

    if not all([support_email, smtp_host, smtp_username, smtp_password, smtp_from]):
        app.logger.error(
            "Help request email is not configured. Set SUPPORT_EMAIL, "
            "SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM."
        )
        return False

    name = clean_field(form.get("name"), 120)
    user_email = safe_reply_to(form.get("email"))
    account = clean_field(form.get("account"), 120)
    problem_type = clean_field(form.get("problem_type"), 80)
    message = clean_message(form.get("message"))

    email = EmailMessage()
    email["Subject"] = f"Adam Studio help request: {problem_type or 'General problem'}"
    email["From"] = smtp_from
    email["To"] = support_email
    if user_email:
        email["Reply-To"] = user_email
    email.set_content(
        "\n".join(
            [
                "New Adam Studio help request",
                "",
                f"Name: {name or 'Not provided'}",
                f"User email: {user_email or 'Not provided'}",
                f"Account / username: {account or 'Not provided'}",
                f"Problem type: {problem_type or 'Not provided'}",
                "",
                "Problem:",
                message or "No message provided.",
            ]
        )
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(email)
    return True


@app.route("/help", methods=["GET", "POST"])
def help_request():
    if request.method == "GET":
        return render_template("help.html", adam_studio_home_url="/")

    if request.form.get("website"):
        return redirect(url_for("thank_you"))

    if not safe_reply_to(request.form.get("email")):
        return render_template(
            "help.html",
            adam_studio_home_url="/",
            help_error="Please enter your email address so the team can reply.",
        ), 400

    if not clean_message(request.form.get("message"), 20):
        return render_template(
            "help.html",
            adam_studio_home_url="/",
            help_error="Please tell us what problem you need help with.",
        ), 400

    try:
        sent = send_help_request(request.form)
    except Exception:
        app.logger.exception("Could not send Adam Studio help request.")
        sent = False
    return redirect(url_for("thank_you", sent="1" if sent else "0"))


@app.route("/thank-you")
def thank_you():
    return render_template("thank_you.html", sent=request.args.get("sent") == "1")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
