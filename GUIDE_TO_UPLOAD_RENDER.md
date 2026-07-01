# Adam Studio Upload Guide

This folder is a separate website for Adam Studio.

## 1. Make a new GitHub repo

1. Go to https://github.com/new
2. Repository name: `adam-studio`
3. Choose Public or Private.
4. Click **Create repository**.

## 2. Upload this folder to GitHub

Upload everything inside `adam_studio_render_site`.

Important files:

- `adam_studio_app.py`
- `requirements.txt`
- `render.yaml`
- `templates/adam_studio.html`
- `static/adam-studio.css`
- `static/adam-studio-logo.jpg`

## 3. Create the Render website

1. Go to https://dashboard.render.com
2. Click **New +**
3. Click **Web Service**
4. Connect the new `adam-studio` GitHub repo.
5. Use these settings:

Name:

```text
adam-studio
```

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn adam_studio_app:app --log-file -
```

6. Click **Create Web Service**.

## 4. Add private email settings

In Render, open your Adam Studio service and go to **Environment**.
Add these variables:

```text
SUPPORT_EMAIL=<your private support email>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<your Gmail address>
SMTP_PASSWORD=<your Gmail app password>
SMTP_FROM=<your Gmail address>
```

Use a Gmail app password, not your normal Gmail password. Your private support
email is only used by the server and is not shown on the website.

Your site will be live at a Render URL like:

```text
https://adam-studio.onrender.com
```
