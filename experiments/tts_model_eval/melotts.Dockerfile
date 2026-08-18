FROM python:3.11.13-slim-bookworm@sha256:86adf8dbadc3d6e82ee5dd2c74bec2e1c2467cdad47886280501df722372d2e1

ENV DEBIAN_FRONTEND=noninteractive \
    NLTK_DATA=/opt/nltk_data \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg git libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements-tts-eval-melotts.lock.txt /tmp/requirements-tts-eval-melotts.lock.txt

RUN python -m pip install --no-cache-dir -r /tmp/requirements-tts-eval-melotts.lock.txt \
    && python -m unidic download \
    && python -c "import nltk; nltk.download('averaged_perceptron_tagger'); nltk.download('cmudict')"

RUN mkdir -p /opt/nltk_data \
    && cp -R /root/nltk_data/. /opt/nltk_data/ \
    && chmod -R a+rX /opt/nltk_data \
    && python -m pip check

ENTRYPOINT ["python", "-m", "scripts.generate_melotts_audition"]
