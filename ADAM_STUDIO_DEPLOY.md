# Adam Studio Render Deploy

Use this when deploying Adam Studio as its own separate Render website.

## Render settings

Create a new Render Web Service from this repository.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn adam_studio_app:app --log-file -
```

The Adam Studio page renders at `/` for this standalone service.

## Private help email

The help form sends problems from users to a private email address. Add these
Render environment variables:

```text
SUPPORT_EMAIL=<your private support email>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<your Gmail address>
SMTP_PASSWORD=<your Gmail app password>
SMTP_FROM=<your Gmail address>
```

The website never shows `SUPPORT_EMAIL` to visitors.

## Files needed

- `adam_studio_app.py`
- `templates/adam_studio.html`
- `static/adam-studio.css`
- `static/adam-studio-logo.jpg`
- `requirements.txt`

Optional blueprint/reference file:

- `render.yaml`
