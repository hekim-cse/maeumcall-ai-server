# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.11.16-slim-trixie@sha256:d1e9ca7c4e78d1e8ecadb5d44bfc8e956e7a65b659a9950f569f243d72b326d0

FROM ${PYTHON_IMAGE} AS core-dependencies

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install --yes --no-install-recommends build-essential ninja-build \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/maeumcall-venv
ENV PATH="/opt/maeumcall-venv/bin:${PATH}"

WORKDIR /build
COPY requirements.txt ./
RUN python -m pip install --no-compile --requirement requirements.txt


FROM ${PYTHON_IMAGE} AS core-runtime

ENV PATH="/opt/maeumcall-venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    TMPDIR=/tmp/maeumcall

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 maeumcall \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin maeumcall \
    && mkdir --parents /app /tmp/maeumcall \
    && chown --recursive maeumcall:maeumcall /app /tmp/maeumcall

COPY --from=core-dependencies /opt/maeumcall-venv /opt/maeumcall-venv

WORKDIR /app
COPY --chown=maeumcall:maeumcall . .

USER 10001:10001

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=2).read()"]

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
