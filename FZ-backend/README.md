# FZ-backend

FastAPI backend for 高翠网.

## Setup

```bash
cp .env.example .env
.venv/bin/python -m pip install -e '.[dev]'
```

## Run

```bash
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Checks

```bash
.venv/bin/ruff check .
.venv/bin/python -m pytest
```
