import os
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

from flask import Flask, redirect, render_template, request, url_for


app = Flask(__name__)


@app.route("/")
def home():
    return render_template("adam_studio.html", adam_studio_home_url="/")


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
    app.run(host="0.0.0.0", port=5000, debug=True)
