#!/usr/bin/env bash
set -Eeuo pipefail

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  kill "${api_pid:-}" "${frontend_pid:-}" "${nginx_pid:-}" 2>/dev/null || true
  wait 2>/dev/null || true
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

cd /app
python -m uvicorn resistsense.api:app --host 127.0.0.1 --port 8000 &
api_pid=$!

cd /app/frontend
npm run start -- --host 127.0.0.1 --port 3000 &
frontend_pid=$!

nginx -c /app/nginx.conf -g "daemon off;" &
nginx_pid=$!

wait -n "${api_pid}" "${frontend_pid}" "${nginx_pid}"
