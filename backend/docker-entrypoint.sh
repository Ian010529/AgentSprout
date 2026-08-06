#!/bin/sh
set -eu

runtime_data_dir="${DATA_DIR:-/app/data}"
runtime_port="${PORT:-8000}"

mkdir -p "$runtime_data_dir"
chown -R agentsprout:agentsprout "$runtime_data_dir"

gosu agentsprout alembic upgrade head

exec gosu agentsprout uvicorn app.main:create_app \
  --factory \
  --host 0.0.0.0 \
  --port "$runtime_port" \
  --proxy-headers \
  --forwarded-allow-ips="*"
