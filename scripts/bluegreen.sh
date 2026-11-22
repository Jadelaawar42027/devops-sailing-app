#!/usr/bin/env bash
# Blue-green deploy with Container Apps revisions (credited extra, brief §5). Used by cd.yml
# only when the GitHub variable DEPLOY_STRATEGY is "bluegreen".
#
# For each service (forecast first, then api):
#   1. create a new revision "v<sha7>" with the new image; it gets 0% traffic (label "green")
#   2. smoke-test it on its own label URL: https://<app>---green.<environment domain>/health
#   3. if healthy: move 100% of traffic to it and make it "blue"; keep the old one at 0% for rollback
#      if not: deactivate it; the old revision never stopped serving
#
# Requires: az login, and the apps in Multiple revision mode (main.bicep revisionsMode=Multiple).
# Migrations must stay backwards compatible (additive), because the new revision migrates the
# database while the old one still serves traffic.
set -euo pipefail

: "${PREFIX:?}" "${RESOURCE_GROUP:?}" "${IMAGE_BASE:?}" "${VERSION:?}"
SUFFIX="v${VERSION:0:7}"
DOMAIN=$(az containerapp env show -n "$PREFIX-env" -g "$RESOURCE_GROUP" --query properties.defaultDomain -o tsv)

wait_healthy() { # url
  for _ in $(seq 1 30); do
    if curl -sf -m 30 "$1/health" | grep -q "\"version\":\"$VERSION\""; then return 0; fi
    sleep 10
  done
  return 1
}

deploy() { # service
  local app="$PREFIX-$1" new="$PREFIX-$1--$SUFFIX" old
  old=$(az containerapp ingress traffic show -n "$app" -g "$RESOURCE_GROUP" \
        --query "[?weight==\`100\`].revisionName | [0]" -o tsv)
  echo "== $app: blue=$old, green=$new"

  az containerapp update -n "$app" -g "$RESOURCE_GROUP" --image "$IMAGE_BASE/$1:$VERSION" \
    --revision-suffix "$SUFFIX" --set-env-vars "APP_VERSION=$VERSION" -o none
  az containerapp revision label add -n "$app" -g "$RESOURCE_GROUP" --label green \
    --revision "$new" --no-prompt -o none

  if wait_healthy "https://$app---green.$DOMAIN"; then
    echo "green is healthy: switching traffic"
    az containerapp ingress traffic set -n "$app" -g "$RESOURCE_GROUP" \
      --revision-weight "$new=100" "$old=0" -o none
    az containerapp revision label remove -n "$app" -g "$RESOURCE_GROUP" --label green -o none
    az containerapp revision label remove -n "$app" -g "$RESOURCE_GROUP" --label blue -o none 2>/dev/null || true
    az containerapp revision label add -n "$app" -g "$RESOURCE_GROUP" --label blue \
      --revision "$new" --no-prompt -o none
    echo "rollback if needed: az containerapp ingress traffic set -n $app -g $RESOURCE_GROUP --revision-weight $old=100 $new=0"
  else
    echo "::error::green revision $new failed its health check; blue ($old) keeps 100% of traffic"
    az containerapp revision label remove -n "$app" -g "$RESOURCE_GROUP" --label green -o none || true
    az containerapp revision deactivate -n "$app" -g "$RESOURCE_GROUP" --revision "$new" -o none || true
    exit 1
  fi
}

deploy forecast
deploy api
