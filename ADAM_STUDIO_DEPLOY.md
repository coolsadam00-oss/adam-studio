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

## Shop and Gexora login

The shop keeps the Adam Studio game library on this service. Users create
accounts and log in on Gexora. Add these Render environment variables when the
Gexora login flow is ready:

```text
SECRET_KEY=<random long secret for Flask sessions>
GEXORA_LOGIN_URL=https://gexora.onrender.com/adam-studio-login
GEXORA_REGISTER_URL=https://gexora.onrender.com/login?next=/adam-studio-login
GEXORA_SHARED_SECRET=<same private secret used by Gexora return links>
ADAM_STUDIO_OWNER_EMAILS=coolsadam00@gmail.com
ADAM_STUDIO_OWNER_USERNAMES=adminadam2155,coolsadam00
```

Set this on the Gexora service too:

```text
ADAM_STUDIO_RETURN_URL=https://<your-adam-studio-site>/shop/gexora-return
GEXORA_SHARED_SECRET=<same private secret>
```

Gexora sends `username`, `email`, `admin`, and `token` back to Adam Studio.
The `token` is an HMAC-SHA256 of `username|email|admin` using
`GEXORA_SHARED_SECRET`.

## Files needed

- `adam_studio_app.py`
- `templates/adam_studio.html`
- `templates/help.html`
- `templates/shop.html`
- `static/adam-studio.css`
- `static/adam-studio-logo.jpg`
- `requirements.txt`

Optional blueprint/reference file:

- `render.yaml`
