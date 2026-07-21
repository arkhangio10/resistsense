FROM ncbi/amr@sha256:5dbf95e3c571c4964c1eaf2f8fd50884ac2a996c4b1a6e4af5a09e381b71d01f AS amrfinder

FROM node:22-bookworm-slim AS frontend-build

WORKDIR /build/frontend
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build && npm prune --omit=dev

FROM node:22-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:/opt/amr/bin:${PATH}" \
    AMRFINDER_BIN="/opt/amr/bin/amrfinder" \
    AMRFINDER_THREADS=2 \
    RESISTSENSE_CONFIG="configs/resistsense.yaml" \
    RESISTSENSE_TARGET_ANNOTATOR="resistsense-target-annotator" \
    TMPDIR="/tmp"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libbz2-1.0 \
        libgomp1 \
        nginx \
        python3 \
        python3-venv \
        tini \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY --from=amrfinder /usr/local/bin /opt/amr/bin

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/python -m pip install --no-cache-dir .

COPY configs ./configs
COPY artifacts/runtime/models ./artifacts/runtime/models
COPY artifacts/phase2 ./artifacts/phase2
COPY artifacts/evaluation/prediction_autopsy.json ./artifacts/evaluation/prediction_autopsy.json
COPY artifacts/evaluation/class_aware_safety_report.json ./artifacts/evaluation/class_aware_safety_report.json

COPY --from=frontend-build --chown=node:node /build/frontend /app/frontend
COPY --chown=node:node deploy/cloudrun/nginx.conf.template /app/nginx.conf.template
COPY --chown=node:node deploy/cloudrun/start.sh /app/start.sh

RUN sed -i 's/\r$//' /app/start.sh \
    && chmod 755 /app/start.sh \
    && mkdir -p /tmp/nginx/client /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi \
    && chown -R node:node /tmp/nginx /app/artifacts

USER node

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=8s --start-period=60s --retries=4 \
  CMD curl --fail "http://127.0.0.1:${PORT:-8080}/health" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/start.sh"]
