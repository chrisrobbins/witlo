# syntax=docker/dockerfile:1
#
# Two stages so the runtime image carries no build toolchain, and a non-root
# user because this container talks to a payment provider and a print service.

FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app

WORKDIR /app

COPY --from=build /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels

COPY --chown=app:app . .

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/v1/health" || exit 1

# Migrations run as a release step, not here — see docs/DEPLOYMENT.md. Running
# them in the entrypoint means every replica races to migrate on every deploy.
CMD ["sh", "-c", "gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers ${WEB_CONCURRENCY:-2} \
  --bind 0.0.0.0:${PORT} \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -"]
