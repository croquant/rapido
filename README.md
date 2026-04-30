# rapido

A scalable, Django-powered POS and ERP system designed to streamline complex orders, granular inventory, and operations for quick-service restaurants.

## Stack

- Python 3.14, Django 6, DRF, HTMX
- SQLite (dev + prod for now)
- WhiteNoise + Gunicorn for serving
- Ruff (lint + format), Pyright (types), pytest

## Setup

```bash
uv sync
cp .env.example .env  # then edit DJANGO_SECRET_KEY
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Admin: http://127.0.0.1:8000/admin/

## Common commands

```bash
uv run pytest
uv run ruff check . && uv run ruff format .
uv run pyright
uv run python manage.py check --deploy --settings=config.settings.prod
```

## Layout

- `config/` - settings (split into `base/dev/prod`), urls, wsgi/asgi
- `core/` - single domain app (custom `User` lives here)
- `templates/`, `static/` - project-level
