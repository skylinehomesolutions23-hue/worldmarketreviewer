#!/usr/bin/env bash
set -euo pipefail

: "${ALERTS_BASE_URL:?Missing ALERTS_BASE_URL}"
: "${ALERTS_CRON_KEY:?Missing ALERTS_CRON_KEY}"

BASE="${ALERTS_BASE_URL%/}"
KEY="${ALERTS_CRON_KEY}"

echo "[cron] POST $BASE/api/alerts/run?key=$KEY"
curl -fsS -X POST "$BASE/api/alerts/run?key=$KEY" || true
echo ""

echo "[cron] POST $BASE/api/alerts/run_recap?key=$KEY"
curl -fsS -X POST "$BASE/api/alerts/run_recap?key=$KEY" || true
echo ""
