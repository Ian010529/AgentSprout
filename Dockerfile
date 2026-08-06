FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install --yes --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.lock backend/pyproject.toml ./
RUN python -m pip install --upgrade "pip==25.3" \
    && python -m pip install --requirement requirements.lock

COPY backend/ ./
RUN python -m pip install . --no-deps \
    && groupadd --system agentsprout \
    && useradd --system --gid agentsprout --home-dir /app --shell /usr/sbin/nologin agentsprout \
    && chmod 0755 /app/backend/docker-entrypoint.sh \
    && mkdir -p /app/data \
    && chown -R agentsprout:agentsprout /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/api/v1/health', timeout=4)"

ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
