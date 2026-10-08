# Development-oriented image: editable installs, source bind-mounted by compose.
# A minimal multi-stage production image is added in checkpoint 3.7 (ADR-0018).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir "uv>=0.5,<1" \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY .python-version pyproject.toml uv.lock ./
COPY apps/api ./apps/api
COPY packages ./packages
RUN uv sync --frozen --no-dev --all-packages

USER app
EXPOSE 8000
CMD ["uvicorn", "pv_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
