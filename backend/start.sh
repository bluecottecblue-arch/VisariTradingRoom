#!/usr/bin/env sh
set -eu

PORT="${PORT:-8000}"
UVICORN_BIN="uvicorn"

if [ -x "./.venv/bin/uvicorn" ]; then
  UVICORN_BIN="./.venv/bin/uvicorn"
fi

exec "$UVICORN_BIN" api.main:app --host 0.0.0.0 --port "$PORT"
