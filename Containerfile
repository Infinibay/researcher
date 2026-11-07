# Installed native backend and compiled owner web application.
# Run/setup contract: docs/architecture/container-operation.md
FROM docker.io/library/node:24.22.2-bookworm-slim@sha256:c0a93797ee78814ae6d32fcca2561fdbbe423149c3f5389aad32d86e9fd85bd4 AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM docker.io/library/python:3.13.17-slim-bookworm@sha256:4cea12ab7d78a3312c85f8cab19b6971d4fe9704da25443986c0bc20a6678850 AS python-build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN python -m venv /opt/venv
COPY requirements.txt ./
RUN /opt/venv/bin/pip install --no-cache-dir --require-hashes -r requirements.txt
COPY requirements-ken.txt ./
RUN python -m venv /opt/ken \
    && /opt/ken/bin/pip install --no-cache-dir --require-hashes -r requirements-ken.txt
COPY pyproject.toml README.md ./
COPY backend/ ./backend/
RUN /opt/venv/bin/pip wheel --no-cache-dir --no-deps --wheel-dir /wheels . \
    && /opt/venv/bin/pip install --no-cache-dir --no-deps /wheels/researcher-*.whl

FROM docker.io/library/python:3.13.17-slim-bookworm@sha256:4cea12ab7d78a3312c85f8cab19b6971d4fe9704da25443986c0bc20a6678850
RUN apt-get update && apt-get install -y --no-install-recommends git libgomp1 bubblewrap=0.8.0-2+deb12u1 \
    && bwrap --help | grep -q -- --ro-bind-fd \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 researcher \
    && useradd -u 1000 -g researcher -m researcher \
    && install -d -o researcher -g researcher -m 0700 /data /run/researcher
COPY --from=python-build /opt/venv /opt/venv
COPY --from=python-build /opt/ken /opt/ken
COPY --from=web /web/dist /app/frontend/dist
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INFINIBAY_DATA=/data \
    INFINIBAY_DB=/data/infinibay.db \
    INFINIBAY_UPLOAD_BASE_DIR=/data/uploads \
    INFINIBAY_AUTH_DIR=/run/researcher/auth \
    INFINIBAY_STATIC_DIR=/app/frontend/dist
WORKDIR /app
USER researcher
EXPOSE 8000
CMD ["researcher-start", "--api-only"]
