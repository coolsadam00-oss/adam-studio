import hashlib
import hmac
import os
import sqlite3
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-adam-studio-secret")
BASE_DIR = Path(__file__).resolve().parent
SHOP_DB = Path(os.environ.get("SHOP_DB", BASE_DIR / "shop.db"))
UPLOAD_DIR = BASE_DIR / "static" / "shop_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.route("/")
def home():
    return render_template("adam_studio.html", adam_studio_home_url="/")


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
        count = db.execute("SELECT COUNT(*) FROM shop_games").fetchone()[0]
        if count == 0:
            db.executemany(
                """
                INSERT INTO shop_games
                    (title, description, price_cents, download_url, file_name, cover_color, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "Gexora Starter Pack",
                        "A free starter drop for new Gexora players.",
                        0,
                        "https://gexora.onrender.com",
                        "",
                        "#0e7a9a",
                        now_iso(),
                    ),
                    (
                        "Adam Studio Prototype",
                        "Early access style slot for an upcoming Adam Studio game.",
                        499,
                        "",
                        "",
                        "#7346d3",
                        now_iso(),
                    ),
                    (
                        "Community Test Build",
                        "A free test build placeholder that players can claim.",
                        0,
                        "https://gexora.onrender.com",
                        "",
                        "#427a2f",
                        now_iso(),
                    ),
                ],
            )


def current_shop_user():
    username = session.get("gexora_username")
    if not username:
        return None
    return {"id": username, "username": username}


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
        gexora_login_url=os.environ.get("GEXORA_LOGIN_URL", "https://gexora.onrender.com/login"),
        gexora_register_url=os.environ.get("GEXORA_REGISTER_URL", "https://gexora.onrender.com/register"),
        is_admin=session.get("shop_admin") is True,
        message=request.args.get("message", ""),
        owned_ids=owned_ids,
        user=user,
    )


@app.route("/shop/gexora-return")
def shop_gexora_return():
    username = clean_field(request.args.get("username"), 40).lower()
    token = request.args.get("token") or ""
    shared_secret = os.environ.get("GEXORA_SHARED_SECRET", "")
    expected = ""
    if username and shared_secret:
        expected = hmac.new(
            shared_secret.encode("utf-8"),
            username.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    if username and expected and hmac.compare_digest(token, expected):
        session["gexora_username"] = username
        return redirect(url_for("shop", message="Gexora login connected."))
    return redirect(url_for("shop", message="Gexora login return is not configured yet."))


@app.post("/shop/logout")
def shop_logout():
    session.pop("gexora_username", None)
    return redirect(url_for("shop", message="Logged out."))


@app.post("/shop/claim/<int:game_id>")
def claim_game(game_id):
    init_shop_db()
    user = current_shop_user()
    if not user:
        return redirect(os.environ.get("GEXORA_LOGIN_URL", "https://gexora.onrender.com/login"))
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
    return redirect(url_for("shop", message=f"{game['title']} added to your library."))


@app.post("/shop/install/<int:game_id>")
def install_game(game_id):
    init_shop_db()
    user = current_shop_user()
    if not user:
        return redirect(os.environ.get("GEXORA_LOGIN_URL", "https://gexora.onrender.com/login"))
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
    if row["file_name"]:
        return redirect(url_for("static", filename=f"shop_uploads/{row['file_name']}"))
    if row["download_url"]:
        return redirect(row["download_url"])
    return redirect(url_for("shop", message="No installer is uploaded yet."))


@app.post("/shop/admin-login")
def shop_admin_login():
    admin_password = os.environ.get("ADMIN_PASSWORD", "2155")
    if request.form.get("password") == admin_password:
        session["shop_admin"] = True
        return redirect(url_for("shop", message="Admin mode enabled."))
    return redirect(url_for("shop", message="Wrong admin password."))


@app.post("/shop/admin")
def shop_admin():
    init_shop_db()
    if session.get("shop_admin") is not True:
        return redirect(url_for("shop", message="Admin login required."))
    action = request.form.get("action")
    with get_shop_db() as db:
        if action == "create":
            file = request.files.get("game_file")
            file_name = ""
            if file and file.filename:
                file_name = f"{int(datetime.utcnow().timestamp())}-{secure_filename(file.filename)}"
                file.save(UPLOAD_DIR / file_name)
            price = max(0, int(float(request.form.get("price", "0") or 0) * 100))
            db.execute(
                """
                INSERT INTO shop_games
                    (title, description, price_cents, download_url, file_name, cover_color, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_field(request.form.get("title"), 120) or "Untitled Game",
                    clean_message(request.form.get("description"), 800)
                    or "New Adam Studio game.",
                    price,
                    clean_field(request.form.get("download_url"), 500),
                    file_name,
                    clean_field(request.form.get("cover_color"), 16) or "#1b2838",
                    now_iso(),
                ),
            )
        elif action == "price":
            game_id = int(request.form.get("game_id", "0") or 0)
            price = max(0, int(float(request.form.get("price", "0") or 0) * 100))
            db.execute(
                "UPDATE shop_games SET price_cents = ? WHERE id = ?",
                (price, game_id),
            )
    return redirect(url_for("shop", message="Shop updated."))


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
