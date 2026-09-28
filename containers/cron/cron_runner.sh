#!/bin/bash
set -u

[ -z "${1:-}" ] && exit 1

ENDPOINT="$1"
case "$ENDPOINT" in
    *[!a-zA-Z0-9_-]*)
        echo "Invalid cron endpoint: $ENDPOINT" >&2
        exit 1
        ;;
esac

CRON_KEY_FILE="${CRON_KEY_FILE:-/app_secrets/cron_key}"
CRON_CONNECT_TIMEOUT="${CRON_CONNECT_TIMEOUT:-5}"
CRON_MAX_TIME="${CRON_MAX_TIME:-25}"
CRON_LOCK_DIR="${CRON_LOCK_DIR:-/tmp}"
CURL_BIN="${CURL_BIN:-/usr/bin/curl}"
FLOCK_BIN="${FLOCK_BIN:-/usr/bin/flock}"

mkdir -p "$CRON_LOCK_DIR"
exec 9>"${CRON_LOCK_DIR}/wireguard-webadmin-${ENDPOINT}.lock"
if ! "$FLOCK_BIN" -n 9; then
    echo "[$(date -Is)] ${ENDPOINT} -> skipped (already running)"
    exit 0
fi

CRON_KEY="$(cat "$CRON_KEY_FILE")"
URL="http://wireguard-webadmin:8000/api/cron/${ENDPOINT}/?cron_key=${CRON_KEY}"

if BODY="$("$CURL_BIN" --fail --silent --show-error \
    --connect-timeout "$CRON_CONNECT_TIMEOUT" \
    --max-time "$CRON_MAX_TIME" \
    "$URL" 2>&1)"; then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi
echo "[$(date -Is)] ${ENDPOINT} -> ${BODY}"
exit "$EXIT_CODE"
