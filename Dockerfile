FROM python:3.11-slim-bookworm AS base

# Runtime configuration comes from the environment (see docs/configuration.md).
# Only non-secret defaults are baked in; never put SMTP credentials in the image.
ENV TZ="America/Denver" \
    ADMIN_PORT="8080" \
    PYTHONUNBUFFERED="1"

WORKDIR /app

# tzdata only; no dist-upgrade so layers stay reproducible between builds.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY monitor.py admin_app.py runner_state.py settings_store.py settings_validation.py ./
COPY static/ ./static/

# Non-root runtime user. /data is the conventional mount for SETTINGS_FILE.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data
USER appuser

EXPOSE 8080

# Fails when the monitor loop stops iterating, not just when the web thread is up.
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.getenv('ADMIN_PORT','8080'), timeout=4); sys.exit(0)" || exit 1

ENTRYPOINT ["python", "monitor.py"]
