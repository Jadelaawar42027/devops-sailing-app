# Monitoring

Brief §4 and §6: we use **only the Log Analytics workspace of the Container Apps environment**
(`sdd-3a-g<N>-logs`). No Application Insights, no extra Azure services.

## How the data gets there

1. Both services write **one JSON line per request** to stdout (`services/*/app/logging_setup.py`):
   `{"ts", "level", "service", "msg": "request", "method", "path", "route", "status", "duration_ms"}`.
   Calls to other systems log `{"msg": "upstream call", "upstream", "status", "duration_ms"}`.
2. Container Apps ships stdout to the environment's Log Analytics workspace
   (table `ContainerAppConsoleLogs_CL`, column `Log_s`).
3. The queries in [`queries/`](queries/) parse those lines with `parse_json(Log_s)`.
   They are also deployed as **saved searches** in the workspace by `infra/main.bicep`
   (category "Sailing planner"), so nothing is clicked together by hand.

Log volume stays low: INFO level, no request bodies, no headers.

## Dashboard

The dashboard is built from the saved searches. Required tiles (brief §6) are 1 to 3.

| Tile | Query | Shows |
| --- | --- | --- |
| 1 | [request-count.kql](queries/request-count.kql) | Requests per service, 5 min bins |
| 2 | [error-rate.kql](queries/error-rate.kql) | % of 5xx answers per service |
| 3 | [response-time.kql](queries/response-time.kql) | p50 / p95 / p99 latency per service |
| 4 | [slo-windows.kql](queries/slo-windows.kql) | The SLO: current SLI vs objective, error budget left |
| 5 | [slo-windows-trend.kql](queries/slo-windows-trend.kql) | SLI over time against the objective |
| 6 | [upstream-health.kql](queries/upstream-health.kql) | Forecast service and Open-Meteo calls, failures, p95 |
| – | [top-routes.kql](queries/top-routes.kql), [recent-errors.kql](queries/recent-errors.kql) | Troubleshooting |

<!-- TODO(team): decide the final dashboard layout (tile order and sizes) and add a screenshot here. -->

To pin the tiles (one time, about 5 minutes):

1. Portal → Log Analytics workspace `sdd-3a-g<N>-logs` → **Logs** → **Queries** → category
   *Sailing planner*. Open each saved search and run it.
2. **Pin to** → **Azure dashboard** → *Create new* `sdd-3a-g<N>-dashboard` (shared) for the first
   tile, then *Existing* for the others.
3. Set the dashboard time range to *Last 24 hours* and auto-refresh to 5 minutes.

Generate traffic first so the tiles are not empty: `scripts/traffic.sh` (see below).

## SLO

See [slo.md](slo.md).

## Generating demo traffic

```bash
# Local (docker compose up first)
scripts/traffic.sh

# Azure (URLs from the README)
API_URL=https://sdd-3a-g<N>-api.<env>.azurecontainerapps.io \
FORECAST_URL=https://sdd-3a-g<N>-forecast.<env>.azurecontainerapps.io \
scripts/traffic.sh 200
```

Logs reach Log Analytics after 2 to 5 minutes.

## Partial failure

See [../partial-failure.md](../partial-failure.md).
