# Production image for the API, the worker and the migration step (the same image, a different command).
#
# Two stages. The first builds a virtual environment with every package installed as a normal
# (non-editable) wheel and no development tools. The second is a clean runtime that holds only that
# environment, the PDF engine's native libraries and a non-root user. No source tree, no build tools
# and no package manager reach the final image, and no secret is baked in: every value arrives as an
# environment variable at run time.
#
# Build:  docker build -f infra/docker/api.prod.Dockerfile -t provenance-api:<git sha> .

FROM python:3.12-slim-bookworm AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN pip install --no-cache-dir "uv>=0.5,<1"

WORKDIR /src
COPY .python-version pyproject.toml uv.lock ./
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY packages ./packages
RUN uv sync --frozen --no-dev --all-packages --no-editable


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/tmp/cache \
    PATH="/opt/venv/bin:$PATH"

# Native libraries for WeasyPrint, which makes the resume PDFs (ADR-0025).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && mkdir -p /app /data/files /tmp/cache \
 && chown -R app:app /data/files /app \
 && chmod 1777 /tmp/cache

COPY --from=build /opt/venv /opt/venv
# The migration step needs a config that finds the migrations inside the installed package.
COPY infra/docker/alembic.prod.ini /app/alembic.ini

WORKDIR /app
USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"]

# No --reload, no bind mounts. The proxy that sits in front sets X-Forwarded-For, and the API is
# never published on a host port, so trusting it from the internal network is safe.
CMD ["uvicorn", "pv_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
