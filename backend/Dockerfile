# syntax=docker/dockerfile:1

# ---- Base: Python + locked dependencies -------------------------------------
FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH
WORKDIR /app
# Dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY . .

# ---- Runtime: the Django API ------------------------------------------------
FROM base AS runtime
ENV DJANGO_DEBUG=false \
    PORT=3000
RUN useradd --system --create-home app  # gunicorn writes runtime files under $HOME
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=2)"
# Apply migrations and ensure the cache table exists, then serve.
# I/O-bound workload (waiting on routing/weather APIs) -> threaded workers.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py createcachetable && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --worker-class gthread --workers 2 --threads 8 --timeout 90 --access-logfile -"]
