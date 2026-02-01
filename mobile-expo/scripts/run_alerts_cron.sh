#!/usr/bin/env bash
set -euo pipefail

: "${ALERTS_BASE_URL:?Missing ALERTS_BASE_URL}"
: "${ALERTS_CRON_KEY:?Missing ALERTS_CRON_KEY}"

URL="${ALERTS_BASE_URL%/}/api/alerts/run?key=${ALERTS_CRON_KEY}"

# Optional: run for a specific email
if [[ "${ALERTS_EMAIL:-}" != "" ]]; then
  URL="${URL}&email=${ALERTS_EMAIL}"
fi

echo "[cron] POST ${URL}"

curl -fsS -X POST \
  --retry 3 \
  --retry-delay 2 \
  --connect-timeout 10 \
  --max-time 120 \
  "${URL}"

echo "[cron] done"
