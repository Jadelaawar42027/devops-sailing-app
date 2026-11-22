#!/usr/bin/env bash
# Repeatable partial-failure test (brief §6). See docs/partial-failure.md.
#
#   scripts/partial-failure.sh              forecast service stopped (local, docker compose)
#   scripts/partial-failure.sh upstream     Open-Meteo unreachable (local, docker compose)
#   scripts/partial-failure.sh azure        forecast service unreachable in Azure (needs az login)
#
# Exit code 0 = every check passed. The system is always restored at the end.
set -uo pipefail

MODE="${1:-forecast}"
API_URL="${API_URL:-http://localhost:8010}"
FORECAST_URL="${FORECAST_URL:-http://localhost:8011}"
MAX_SECONDS="${MAX_SECONDS:-15}"   # the degraded answer must come back faster than this
FAILURES=0

pass() { echo "  PASS  $*"; }
fail() { echo "  FAIL  $*"; FAILURES=$((FAILURES + 1)); }
need() { command -v "$1" >/dev/null || { echo "needs $1"; exit 2; }; }
need curl; need python3

field() { python3 -c "import json,sys; print(json.load(sys.stdin).get('$1',''))" 2>/dev/null; }

wait_for() { # url seconds
  for ((s = 0; s < $2; s += 2)); do curl -sf -m 5 "$1" >/dev/null && return 0; sleep 2; done
  return 1
}

demo_passage() {
  local id
  id=$(curl -sf -m 20 "$API_URL/passages" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
  if [[ -z "$id" ]]; then
    local boat
    boat=$(curl -sf -m 20 -X POST -H 'Content-Type: application/json' \
      -d '{"name":"Failure-test boat","max_wind_kn":20,"max_wave_m":2}' "$API_URL/boats" | field id)
    id=$(curl -sf -m 20 -X POST -H 'Content-Type: application/json' \
      -d "{\"name\":\"Failure-test passage\",\"boat_id\":$boat,\"start_lat\":41.37,\"start_lon\":2.19,\"end_lat\":41.23,\"end_lon\":1.81,\"speed_kn\":6}" \
      "$API_URL/passages" | field id)
  fi
  echo "$id"
}

check_degraded() { # passage_id
  local out code secs body
  out=$(curl -s -m 60 -w '\n%{http_code} %{time_total}' "$API_URL/passages/$1/windows")
  body=$(echo "$out" | sed '$d'); read -r code secs <<<"$(echo "$out" | tail -1)"
  echo "  windows answered HTTP $code in ${secs}s: $(echo "$body" | field detail)"
  [[ "$code" == "503" ]] && pass "windows returns 503, not 500" || fail "expected 503, got $code"
  [[ "$(echo "$body" | field status)" == "degraded" ]] && pass "body says status=degraded" || fail "no status=degraded in body"
  python3 -c "import sys; sys.exit(0 if float('$secs') < $MAX_SECONDS else 1)" \
    && pass "answered in under ${MAX_SECONDS}s (no hung request)" || fail "took ${secs}s"
  echo "$body" | grep -q 'Traceback' && fail "stack trace leaked" || pass "no stack trace in the response"
}

check_crud_still_works() {
  [[ "$(curl -s -o /dev/null -w '%{http_code}' -m 20 "$API_URL/boats")" == "200" ]] \
    && pass "GET /boats still 200" || fail "GET /boats broken"
  local id
  id=$(curl -s -m 20 -X POST -H 'Content-Type: application/json' \
    -d '{"name":"Created while degraded","max_wind_kn":15,"max_wave_m":1.5}' "$API_URL/boats" | field id)
  if [[ -n "$id" ]]; then
    pass "POST /boats still works (id $id)"
    curl -s -o /dev/null -m 20 -X DELETE "$API_URL/boats/$id"
  else
    fail "POST /boats broken"
  fi
}

echo "Partial-failure test: mode=$MODE"
wait_for "$API_URL/health" 60 || { echo "API not up at $API_URL"; exit 2; }
PID=$(demo_passage)
echo "Using passage $PID"

echo "1. Baseline"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 60 "$API_URL/passages/$PID/windows")
[[ "$code" == "200" ]] && pass "windows 200 before the failure" || fail "baseline windows answered $code"

case "$MODE" in
  forecast)
    echo "2. Stop the forecast service"
    trap 'docker compose start forecast >/dev/null 2>&1' EXIT
    docker compose stop forecast >/dev/null 2>&1
    echo "3. Checks while it is down"
    check_degraded "$PID"
    check_crud_still_works
    echo "4. Restore"
    docker compose start forecast >/dev/null 2>&1
    wait_for "$FORECAST_URL/health" 90 && pass "forecast service back" || fail "forecast did not come back"
    ;;
  upstream)
    echo "2. Point the forecast service at an unroutable Open-Meteo (requests time out)"
    trap 'docker compose up -d forecast >/dev/null 2>&1' EXIT
    OPEN_METEO_MARINE_URL="http://10.255.255.1/v1/marine" docker compose up -d forecast >/dev/null 2>&1
    wait_for "$FORECAST_URL/health" 90 || fail "forecast did not restart"
    echo "3. Checks while Open-Meteo is unreachable"
    # A location never seen before has no cache: expect a clear 503 from the forecast service.
    out=$(curl -s -m 60 -w '\n%{http_code}' "$FORECAST_URL/current?lat=12.34&lon=-45.67")
    [[ "$(echo "$out" | tail -1)" == "503" ]] && pass "uncached location: 503 '$(echo "$out" | sed '$d' | field detail)'" \
      || fail "uncached location did not return 503"
    # The demo passage was cached by the baseline call: the stale copy can be served.
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 60 "$API_URL/passages/$PID/windows")
    [[ "$code" == "200" || "$code" == "503" ]] && pass "windows answered $code (200 = from cache, 503 = degraded)" \
      || fail "windows answered $code"
    check_crud_still_works
    echo "4. Restore"
    docker compose up -d forecast >/dev/null 2>&1
    wait_for "$FORECAST_URL/health" 90 && pass "forecast service restored" || fail "forecast did not come back"
    ;;
  azure)
    need az
    : "${RESOURCE_GROUP:?set RESOURCE_GROUP, e.g. rg-sdd-3a-g3}" "${PREFIX:?set PREFIX, e.g. sdd-3a-g3}"
    APP="$PREFIX-forecast"
    echo "2. Disable ingress on $APP (temporary; restored on exit)"
    trap 'az containerapp ingress enable -n "$APP" -g "$RESOURCE_GROUP" --type external --target-port 8000 --transport auto >/dev/null' EXIT
    az containerapp ingress disable -n "$APP" -g "$RESOURCE_GROUP" >/dev/null
    sleep 20
    echo "3. Checks while it is unreachable"
    check_degraded "$PID"
    check_crud_still_works
    echo "4. Restore"
    az containerapp ingress enable -n "$APP" -g "$RESOURCE_GROUP" --type external --target-port 8000 --transport auto >/dev/null
    trap - EXIT
    pass "ingress re-enabled"
    ;;
  *) echo "unknown mode $MODE"; exit 2 ;;
esac

echo "5. After recovery"
sleep 2
code=$(curl -s -o /dev/null -w '%{http_code}' -m 60 "$API_URL/passages/$PID/windows")
[[ "$code" == "200" ]] && pass "windows 200 again" || fail "windows answered $code after recovery"

echo
if [[ $FAILURES -eq 0 ]]; then echo "RESULT: PASS"; else echo "RESULT: FAIL ($FAILURES checks)"; fi
exit $FAILURES
