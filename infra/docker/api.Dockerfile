# Development-oriented image: editable installs, source bind-mounted by compose.
# The same image runs the API, the migrations and the worker (only the command differs).
# A minimal multi-stage production image is added in checkpoint 3.7 (ADR-0018).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    XDG_CACHE_HOME=/tmp/cache \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

# Native libraries for WeasyPrint, which makes the resume PDFs (ADR-0025).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
 && rm -rf /var/lib/apt/lists/*

# Fontconfig (used by the PDF engine) needs a cache folder it can write.
RUN mkdir -p /tmp/cache && chmod 1777 /tmp/cache

RUN pip install --no-cache-dir "uv>=0.5,<1" \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY .python-version pyproject.toml uv.lock ./
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY packages ./packages
RUN uv sync --frozen --no-dev --all-packages

# Private file storage. The named volume copies this ownership on first use.
RUN mkdir -p /data/files && chown -R app:app /data/files

USER app
EXPOSE 8000
CMD ["uvicorn", "pv_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
