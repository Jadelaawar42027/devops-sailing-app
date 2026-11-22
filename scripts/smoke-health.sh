#!/usr/bin/env bash
# Post-deploy check (brief §5): /health must return 200 on every component in time,
# otherwise the CD run fails. Also checks that the services run the expected version.
#
#   API_URL=... FORECAST_URL=... UI_URL=... [EXPECTED_VERSION=<sha>] scripts/smoke-health.sh
set -uo pipefail

TIMEOUT_S="${TIMEOUT_S:-300}"   # scale-to-zero cold start + Azure SQL resume can take minutes
EXPECTED_VERSION="${EXPECTED_VERSION:-}"
status=0

check() { # name url check_version
  local name=$1 url=$2 want_version=$3 start body code version
  start=$(date +%s)
  while true; do
    body=$(curl -s -m 30 -w '\n%{http_code}' "$url/health" || true)
    code=$(echo "$body" | tail -1)
    body=$(echo "$body" | sed '$d')
    if [[ "$code" == "200" ]]; then
      version=$(echo "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("version",""))' 2>/dev/null)
      if [[ "$want_version" == "yes" && -n "$EXPECTED_VERSION" && "$version" != "$EXPECTED_VERSION" ]]; then
        echo "  ... $name is up but still runs version '$version' (want $EXPECTED_VERSION)"
      else
        echo "OK   $name $url/health -> 200 ${version:+(version $version)} after $(( $(date +%s) - start ))s"
        return 0
      fi
    else
      echo "  ... $name $url/health -> ${code:-no answer}, retrying"
    fi
    if (( $(date +%s) - start > TIMEOUT_S )); then
      echo "FAIL $name did not return 200 within ${TIMEOUT_S}s"
      return 1
    fi
    sleep 10
  done
}

check api "${API_URL:?set API_URL}" yes || status=1
check forecast "${FORECAST_URL:?set FORECAST_URL}" yes || status=1
check ui "${UI_URL:?set UI_URL}" no || status=1
exit $status
