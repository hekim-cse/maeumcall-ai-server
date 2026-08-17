#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"

cd "${PROJECT_DIR}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo ".venv가 없습니다. ./scripts/bootstrap_python.sh를 먼저 실행해 주세요." >&2
  exit 1
fi

"${PYTHON_BIN}" -m scripts.check_python_version

SERVER_HOST="${SERVER_HOST:-127.0.0.1}"
SERVER_PORT="${SERVER_PORT:-8000}"

exec "${PYTHON_BIN}" -m uvicorn main:app --host "${SERVER_HOST}" --port "${SERVER_PORT}" "$@"
