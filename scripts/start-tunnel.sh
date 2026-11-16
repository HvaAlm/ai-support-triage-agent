#!/usr/bin/env bash
# Testing only: expose local n8n through a Cloudflare quick tunnel and publish the intake
# workflow so Telegram delivers every message. The quick-tunnel address changes on every
# start, so run this again after a reboot. On a server, set N8N_PUBLIC_HOST to its domain instead.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
WORKFLOW_ID="SWWlrw3ihBa33qg9"  # Datami — Support Intake & Triage
ENV_FILE="$PROJECT_DIR/.env"
STATE_DIR="$PROJECT_DIR/data"  # gitignored
LOG="$STATE_DIR/cloudflared.log"
PID_FILE="$STATE_DIR/cloudflared.pid"
compose() { docker compose --project-directory "$PROJECT_DIR" -f "$PROJECT_DIR/docker-compose.yaml" "$@"; }

[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE" >&2; exit 1; }
command -v cloudflared >/dev/null || { echo "cloudflared is not installed" >&2; exit 1; }
mkdir -p "$STATE_DIR"

# 1. Replace any tunnel this script started before.
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  kill "$(cat "$PID_FILE")"
  sleep 2
fi

# 2. Start the tunnel and read its address.
: > "$LOG"
# setsid: keep the tunnel running after this shell exits.
setsid nohup cloudflared tunnel --no-autoupdate --url http://127.0.0.1:5678 >"$LOG" 2>&1 < /dev/null &
echo $! > "$PID_FILE"
HOST=""
for _ in $(seq 1 30); do
  HOST=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1 | sed 's#https://##' || true)
  [ -n "$HOST" ] && break
  sleep 1
done
[ -n "$HOST" ] || { echo "Tunnel did not start; see $LOG" >&2; exit 1; }
echo "Tunnel: https://$HOST"

# 3. Point n8n at the new address.
if grep -q '^N8N_PUBLIC_HOST=' "$ENV_FILE"; then
  sed -i "s#^N8N_PUBLIC_HOST=.*#N8N_PUBLIC_HOST=$HOST#" "$ENV_FILE"
else
  echo "N8N_PUBLIC_HOST=$HOST" >> "$ENV_FILE"
fi

# 4. Wait until the address answers publicly (new quick-tunnel DNS takes a moment).
for i in $(seq 1 60); do
  curl -s -m 5 -o /dev/null "https://$HOST/healthz" && break
  [ "$i" = 60 ] && { echo "https://$HOST is not reachable yet; try again" >&2; exit 1; }
  sleep 2
done

# 5. Publish the workflow and recreate n8n with the new address; on start it registers
#    the Telegram webhook at https://$HOST/.
docker exec n8n n8n publish:workflow --id="$WORKFLOW_ID" >/dev/null 2>&1
compose up -d --force-recreate n8n >/dev/null
for i in $(seq 1 60); do
  curl -s -m 2 http://127.0.0.1:5678/healthz/readiness | grep -q ok && break
  [ "$i" = 60 ] && { echo "n8n did not become ready; check: docker logs n8n" >&2; exit 1; }
  sleep 2
done

echo "n8n is live at https://$HOST and the intake workflow is published."
echo "Stop the tunnel with: kill \$(cat $PID_FILE)"
