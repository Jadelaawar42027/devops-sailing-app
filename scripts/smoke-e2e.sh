#!/usr/bin/env bash
# End-to-end smoke test against a deployed system (credited extra, brief §5).
# Creates a boat and a passage, asks for its windows, checks CORS for the UI origin, then
# deletes what it created. Fails (exit 1) on the first broken step.
#
#   API_URL=https://... UI_URL=https://... scripts/smoke-e2e.sh
set -euo pipefail

API_URL="${API_URL:?set API_URL}"
UI_URL="${UI_URL:-}"
TMP=$(mktemp -d)
BOAT_ID=""
PASSAGE_ID=""

cleanup() {
  [[ -n "$PASSAGE_ID" ]] && curl -s -o /dev/null -m 30 -X DELETE "$API_URL/passages/$PASSAGE_ID" || true
  [[ -n "$BOAT_ID" ]] && curl -s -o /dev/null -m 30 -X DELETE "$API_URL/boats/$BOAT_ID" || true
  rm -rf "$TMP"
}
trap cleanup EXIT

step() { # name expected_code method path [json]
  local name=$1 want=$2 method=$3 path=$4 code
  if [[ $# -ge 5 ]]; then
    code=$(curl -s -o "$TMP/body" -w '%{http_code}' -m 60 -X "$method" -H 'Content-Type: application/json' -d "$5" "$API_URL$path")
  else
    code=$(curl -s -o "$TMP/body" -w '%{http_code}' -m 60 -X "$method" "$API_URL$path")
  fi
  if [[ "$code" != "$want" ]]; then
    echo "FAIL $name: $method $path -> $code (want $want): $(head -c 300 "$TMP/body")"
    exit 1
  fi
  echo "OK   $name ($code)"
}
field() { python3 -c "import json,sys; print(json.load(open('$TMP/body'))$1)"; }

step "create boat" 201 POST /boats '{"name":"Smoke test boat","max_wind_kn":20,"max_gust_kn":28,"max_wave_m":2}'
BOAT_ID=$(field '["id"]')
step "create passage" 201 POST /passages "{\"name\":\"Smoke test passage\",\"boat_id\":$BOAT_ID,\"start_lat\":41.37,\"start_lon\":2.19,\"end_lat\":41.23,\"end_lon\":1.81,\"speed_kn\":6}"
PASSAGE_ID=$(field '["id"]')
step "read passage" 200 GET "/passages/$PASSAGE_ID"
step "departure windows" 200 GET "/passages/$PASSAGE_ID/windows"
echo "     $(field '["summary"]["go"]') of $(field '["summary"]["windows"]') windows GO"
step "validation rejects bad input" 422 POST /boats '{"name":"","max_wind_kn":-1,"max_wave_m":2}'

if [[ -n "$UI_URL" ]]; then
  allowed=$(curl -s -D - -o /dev/null -m 30 -X OPTIONS "$API_URL/boats" \
    -H "Origin: $UI_URL" -H "Access-Control-Request-Method: GET" | tr -d '\r' \
    | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')
  if [[ "$allowed" == "$UI_URL" ]]; then echo "OK   CORS allows $UI_URL"; else echo "FAIL CORS: got '$allowed'"; exit 1; fi
fi

step "delete passage" 204 DELETE "/passages/$PASSAGE_ID"; PASSAGE_ID=""
step "delete boat" 204 DELETE "/boats/$BOAT_ID"; BOAT_ID=""
echo "End-to-end smoke test passed."
