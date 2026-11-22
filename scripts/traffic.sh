#!/usr/bin/env bash
# Generate demo traffic so the monitoring dashboard and SLO have data.
#
#   scripts/traffic.sh [ROUNDS]          default 50 rounds
#   API_URL=... FORECAST_URL=... scripts/traffic.sh 200
#
# Each round: health checks, list boats/passages, the windows of every passage, current
# conditions, and one request that is expected to 404 (so the error panels are not flat zero).
# Creates a demo boat + passage if there are none. Read-only otherwise.
set -euo pipefail

API_URL="${API_URL:-http://localhost:8010}"
FORECAST_URL="${FORECAST_URL:-http://localhost:8011}"
ROUNDS="${1:-50}"
PAUSE="${PAUSE:-0.5}"
CODES_FILE=$(mktemp)
trap 'rm -f "$CODES_FILE"' EXIT

call() { # method url [json]
  local code
  if [[ $# -ge 3 ]]; then
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 -X "$1" -H 'Content-Type: application/json' -d "$3" "$2" || true)
  else
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 -X "$1" "$2" || true)
  fi
  echo "$code" >>"$CODES_FILE"
}

json_ids() { python3 -c 'import json,sys; print(" ".join(str(x["id"]) for x in json.load(sys.stdin)))'; }

echo "API:      $API_URL"
echo "Forecast: $FORECAST_URL"
curl -sf -m 60 "$API_URL/health" >/dev/null || { echo "API is not answering /health"; exit 1; }

passages=$(curl -sf -m 20 "$API_URL/passages" | json_ids)
if [[ -z "$passages" ]]; then
  echo "No passages yet: creating a demo boat and passage."
  boat=$(curl -sf -m 20 -X POST -H 'Content-Type: application/json' \
    -d '{"name":"Demo yacht","max_wind_kn":20,"max_gust_kn":28,"max_wave_m":2}' "$API_URL/boats" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
  curl -sf -m 20 -X POST -H 'Content-Type: application/json' \
    -d "{\"name\":\"Demo: Barcelona to Sitges\",\"boat_id\":$boat,\"start_lat\":41.37,\"start_lon\":2.19,\"end_lat\":41.23,\"end_lon\":1.81,\"speed_kn\":6}" \
    "$API_URL/passages" >/dev/null
  passages=$(curl -sf -m 20 "$API_URL/passages" | json_ids)
fi

for ((i = 1; i <= ROUNDS; i++)); do
  call GET "$API_URL/health"
  call GET "$FORECAST_URL/health"
  call GET "$API_URL/boats"
  call GET "$API_URL/passages"
  for id in $passages; do call GET "$API_URL/passages/$id/windows"; done
  call GET "$FORECAST_URL/current?lat=41.37&lon=2.19"
  call GET "$API_URL/passages/999999"   # expected 404
  printf '\rround %d/%d' "$i" "$ROUNDS"
  sleep "$PAUSE"
done
echo
echo "Status codes (count, code):"
sort "$CODES_FILE" | uniq -c
