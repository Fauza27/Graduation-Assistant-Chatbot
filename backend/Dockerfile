# syntax=docker/dockerfile:1.7
ARG PYTHON_IMAGE=python:3.11.16-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84

FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --requirement requirements.txt

FROM builder AS development
COPY requirements-dev.txt .
RUN pip install --requirement requirements-dev.txt

FROM ${PYTHON_IMAGE} AS production

ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/Fauza27/Graduation-Assistant-Chatbot" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production \
    PORT=8000

COPY --from=builder /opt/venv /opt/venv

RUN groupadd --system appuser \
    && useradd --system --gid appuser --home-dir /app appuser

WORKDIR /app
COPY --chown=appuser:appuser application.py main.py ./
COPY --chown=appuser:appuser config ./config
COPY --chown=appuser:appuser src ./src
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/liveness', timeout=3)"]

EXPOSE 8000
CMD ["uvicorn", "application:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
