#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQUIRED_VERSION="$(tr -d '[:space:]' < "${PROJECT_DIR}/.python-version")"
MAEUMCALL_PYTHON="${MAEUMCALL_PYTHON:-python${REQUIRED_VERSION}}"
VENV_DIR="${PROJECT_DIR}/.venv"

cd "${PROJECT_DIR}"

if ! command -v "${MAEUMCALL_PYTHON}" >/dev/null 2>&1; then
  echo "Python ${REQUIRED_VERSION}을 찾을 수 없습니다: ${MAEUMCALL_PYTHON}" >&2
  echo "Python ${REQUIRED_VERSION} 설치 후 다시 실행해 주세요." >&2
  exit 1
fi

if [[ -d "${VENV_DIR}" ]]; then
  if ! "${VENV_DIR}/bin/python" -m scripts.check_python_version; then
    echo "기존 .venv의 Python 버전이 프로젝트 기준과 다릅니다." >&2
    echo ".venv를 제거한 뒤 이 스크립트를 다시 실행해 주세요." >&2
    exit 1
  fi
else
  "${MAEUMCALL_PYTHON}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m scripts.check_python_version
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${PROJECT_DIR}/requirements-dev.txt"

echo "Python ${REQUIRED_VERSION} 개발 환경 구성이 완료됐습니다."
