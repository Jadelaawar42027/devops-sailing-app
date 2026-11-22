# Service Level Objective

<!-- TODO(team): agree the target numbers below; keep queries/slo-windows*.kql in sync. -->

| | |
| --- | --- |
| **User journey** | "Show me when I can leave": `GET /passages/{id}/windows` on the API |
| **SLI** | Share of those requests that answer with a status below 500 **and** in under 1000 ms |
| **Objective** | **99%** over a rolling **1 hour** window |
| **Error budget** | 1% of requests per hour may be slow or fail |
| **Measured by** | [queries/slo-windows.kql](queries/slo-windows.kql) (current value) and [queries/slo-windows-trend.kql](queries/slo-windows-trend.kql) (trend) |

## Why this journey

It is the feature beyond CRUD and the only request that crosses both services and the external
API, so it is the first thing to break and the one users care about.

## Why 503 counts as bad

When the forecast service is down the API answers fast with a clear `503 degraded` message
(see [../partial-failure.md](../partial-failure.md)). That is the correct behaviour, but the user
still did not get their windows, so it burns error budget.

## Known risks to the objective

- **Scale to zero.** Both Container Apps scale to zero (brief §4). The first request after an idle
  period waits for a cold start, and Azure SQL serverless may also need up to a minute to resume.
  With little demo traffic this alone can break a 1-hour objective.
- **Cache misses.** A new location means two Open-Meteo calls per point. Repeat requests hit the
  forecast service's cache and are much faster.

## What we do when the budget is spent

Look at tile 6 (upstream health) and `recent-errors.kql` first; then check the Container Apps
revision and recent deploys. Feature work pauses until the SLI is back above the objective.
