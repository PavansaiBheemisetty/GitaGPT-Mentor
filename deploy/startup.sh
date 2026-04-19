#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_ROOT/backend"

# Azure may run from an extracted temp path; prefer local packaged deps first.
export PYTHONPATH="$APP_ROOT/python_packages:/home/site/wwwroot/python_packages:${PYTHONPATH:-}"

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
