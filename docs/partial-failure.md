# Partial-failure test

Brief §6: *"with one service down (or an external API failing), the other keeps working and the
affected flow fails with a timeout and a clear message, not a stack trace or a hung request."*

The test is a script, so anyone can repeat it: `scripts/partial-failure.sh`. It exits `0` when
every check passes and always restores the system, even if interrupted.

## What protects us

| Failure | Where it is handled | What the user gets |
| --- | --- | --- |
| Forecast service down or slow | `services/api/app/forecast_client.py` (10 s timeout) and `routers/windows.py` | `503 {"status": "degraded", "detail": "Forecast unavailable: … Boats and passages still work…"}`. Boats and passages keep working. The UI shows the message in a banner. |
| Open-Meteo down or slow | `services/forecast/app/openmeteo.py` (4 s timeout) and `service.py` | The last cached forecast, marked `"stale": true`, or a `503` with a clear reason when nothing is cached. |
| Azure SQL paused or unreachable | `app/db.py` (startup retries, `pool_pre_ping`) and the `OperationalError` handler in `app/main.py` | `503 "Database unavailable, please retry in a few seconds."` |

Automated tests cover each path without Docker:
`services/api/tests/test_windows.py::test_forecast_failure_gives_clear_degraded_response`,
`test_crud_keeps_working_while_forecast_is_down`, and `services/forecast/tests/test_forecast.py`
(`timeout`, `http500`, `stale` cases).

## Scenario A: the forecast service is stopped (local)

```bash
docker compose up -d --build
scripts/partial-failure.sh
```

Steps the script performs and checks:

1. Baseline: `GET /passages/{id}/windows` returns `200`.
2. `docker compose stop forecast`.
3. `GET /passages/{id}/windows` returns **503** with `status: degraded` in **well under 15 s**
   and no stack trace. `GET /boats` returns 200; `POST /boats` still creates a boat.
4. `docker compose start forecast` and wait for `/health`.
5. Windows return `200` again.

Expected output (recorded 2026-11-22 on a laptop):

```text
3. Checks while it is down
  windows answered HTTP 503 in 0.008383s: Forecast unavailable: forecast service is unreachable (ConnectError). Boats and passages still work; try the windows again in a minute.
  PASS  windows returns 503, not 500
  PASS  body says status=degraded
  PASS  answered in under 15s (no hung request)
  PASS  no stack trace in the response
  PASS  GET /boats still 200
  PASS  POST /boats still works (id 4)
...
RESULT: PASS
```

## Scenario B: Open-Meteo is unreachable (local)

```bash
scripts/partial-failure.sh upstream
```

The script restarts the forecast service with `OPEN_METEO_MARINE_URL` pointing at an unroutable
address, so every upstream call hits the 4 s timeout. A location that was never cached returns a
clear `503` (`"open-meteo-marine did not answer within 4s; no cached data for this location"`);
a cached passage still gets its windows from the cache (marked stale once the cache entry is older
than 30 minutes). Then it restores the normal URL.

## Scenario C: in Azure (for the Sprint Review)

Run it against the deployed system (needs `az login` with access to the resource group). It disables
ingress on the forecast Container App for about a minute and re-enables it on exit.

```bash
API_URL=https://<api-fqdn> FORECAST_URL=https://<forecast-fqdn> \
RESOURCE_GROUP=rg-sdd-3a-g<N> PREFIX=sdd-3a-g<N> \
scripts/partial-failure.sh azure
```

While it runs, open the UI: the planner shows the red "Forecast unavailable" banner while the
Boats and Passages pages keep working. Afterwards, `docs/monitoring/queries/error-rate.kql` and
`upstream-health.kql` show the spike. The next CD run puts the ingress back in its declared state
anyway (infra is re-applied from Bicep on every deploy).
