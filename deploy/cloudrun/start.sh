#!/usr/bin/env bash
set -Eeuo pipefail

external_port="${PORT:-8080}"
sed "s/__PORT__/${external_port}/g" /app/nginx.conf.template > /tmp/nginx.conf

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  kill "${api_pid:-}" "${frontend_pid:-}" "${nginx_pid:-}" 2>/dev/null || true
  wait 2>/dev/null || true
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

cd /app
python -m uvicorn resistsense.api:app \
  --host 127.0.0.1 --port 8000 --no-access-log &
api_pid=$!

cd /app/frontend
npm run start -- --host 127.0.0.1 --port 3000 &
frontend_pid=$!

ready=false
for _ in $(seq 1 120); do
  if ! kill -0 "${api_pid}" 2>/dev/null; then
    echo "FastAPI exited before becoming ready" >&2
    wait "${api_pid}"
    exit $?
  fi
  if ! kill -0 "${frontend_pid}" 2>/dev/null; then
    echo "Frontend exited before becoming ready" >&2
    wait "${frontend_pid}"
    exit $?
  fi
  if curl --fail --silent "http://127.0.0.1:8000/health" >/dev/null \
    && curl --fail --silent "http://127.0.0.1:3000/" >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done

if [[ "${ready}" != "true" ]]; then
  echo "ResistSense processes did not become ready within 120 seconds" >&2
  exit 1
fi

nginx -c /tmp/nginx.conf -g "daemon off;" &
nginx_pid=$!

wait -n "${api_pid}" "${frontend_pid}" "${nginx_pid}"
