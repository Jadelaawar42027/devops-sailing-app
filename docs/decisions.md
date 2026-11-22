# Decision records

Short records (context, decision, alternatives, consequences), as asked in brief §3b and §7.

## 1. Architecture: an API service and a forecast service

**Context.** The brief requires exactly two services, each with its own container and database,
talking over HTTP, and a static UI calling them from the browser. The product has two different
kinds of work: user data (boats, passages) and an external, slow, sometimes failing data source
(the marine forecast).

**Decision.** `api` owns boats, passages and the GO/NO-GO scoring. `forecast` owns everything about
Open-Meteo: the two upstream calls (wind from the weather API, waves from the Marine API), merging
them, caching them and failing cleanly. The API calls the forecast service with a 10 s timeout. The
UI calls the API for everything and the forecast service directly for the current-conditions panel.
Inside each service we use a simple layered structure: routers (HTTP), a pure domain module
(`scoring.py`, `openmeteo.py`), and data access (`db.py`, `models.py`, migrations).

**Alternatives.** Splitting boats and passages into two services: they are one aggregate and would
need a cross-service join for every windows request. Putting scoring in the forecast service: it
would then need the boats, which belong to the API.

**Consequences.** The external dependency is isolated: when Open-Meteo or the forecast service
fails, CRUD keeps working and only the windows flow degrades (see `docs/partial-failure.md`). The
cost is an extra network hop per windows request, which the cache keeps cheap.

## 2. Storage: Azure SQL serverless, SQLAlchemy and Alembic

**Context.** The stack is fixed: one serverless Azure SQL database per service, SQL Server in compose
locally, never the Azure database from CI, and a schema defined by versioned migrations applied on
startup.

**Decision.** SQLAlchemy 2 ORM with `pyodbc` (ODBC Driver 18) and Alembic migrations in
`services/*/migrations/versions`, run in each service's startup with retries (Azure SQL serverless
can take up to a minute to resume after auto-pause). The forecast service's database holds a
`forecast_cache` table keyed by rounded coordinates. Tests run the same migrations on SQLite.
Local compose runs one SQL Server container that hosts both services' databases.

**Alternatives.** Hand-written T-SQL migration files: simpler, but not runnable on SQLite, so tests
would need SQL Server in CI. An in-memory cache in the forecast service: lost on every scale to
zero, so the cache would almost never be warm.

**Consequences.** Migrations are tested on every PR. Migrations must stay additive so a new revision
can migrate while the old one serves (needed for blue-green). Deleting a boat that still has
passages returns 409 instead of cascading, so data is never removed by accident.

## 3. Deployment and pipeline: GHCR, Bicep applied by CD, OIDC

**Context.** Brief §4 and §5: images in GHCR, Container Apps scaling to zero, one Static Web App,
nothing changed by hand after setup, deploy only if CI passed, and a failing `/health` must fail
the run. IaC is credited.

**Decision.** `cd.yml` calls `ci.yml` as its first job, pushes images tagged with the commit SHA,
then applies `infra/main.bicep` with those tags on every merge. Bicep declares every resource,
including the dashboard queries, so the deployed state is always the repository's state. Azure login
uses OpenID Connect with the group's identity: no client secret or credentials JSON exists anywhere.
The only secrets are `SQL_ADMIN_PASSWORD` (and optionally `GHCR_PULL_TOKEN`) as GitHub secrets,
passed into Container Apps secrets. The UI gets the service URLs through a `config.js` written at
deploy time. After deploying, `scripts/smoke-health.sh` waits up to 5 minutes for `/health` (cold
start and database resume) and checks the deployed version, then `scripts/smoke-e2e.sh` runs an
end-to-end test against the live URL.

**Alternatives.** Imperative `az containerapp update` calls: faster but drifts from the declared
infrastructure. A publish profile or service-principal secret: a long-lived credential that can leak.

**Consequences.** The first deploy creates everything (~10 min); later ones are incremental.
Blue-green (credited extra) is available behind `DEPLOY_STRATEGY=bluegreen`: new revisions are
tested on a label URL at 0% traffic before switching. It is off by default so the simple path can
be proven first.

## 4. Monitoring: Log Analytics only, structured logs, one SLO

**Context.** Brief §4 and §6: use the Log Analytics workspace of the Container Apps environment, no
other Azure services, low log volume; a dashboard with request count, error rate and response time;
one SLO with its query.

**Decision.** Each service writes one JSON line per request (method, path, route template, status,
duration) and one per upstream call. KQL queries in `docs/monitoring/queries` parse them; Bicep
deploys them as saved searches; the dashboard pins them. The SLO is on the journey users care about
and that crosses everything: 99% of `GET /passages/{id}/windows` answer below 500 and under 1 s over
1 h. Degraded 503 answers count against it.

**Alternatives.** Application Insights with OpenTelemetry: richer traces, but an extra Azure service
the brief rules out.

**Consequences.** No distributed tracing; the `route` field and the upstream log lines are enough to
find which hop is slow. Scale to zero means cold starts count against the SLO; the team accepts that
for cost (see `docs/monitoring/slo.md`).

## 5. The feature beyond CRUD: GO/NO-GO scoring

**Context.** A sailor wants to know when to leave, not to read a forecast table.

**Decision.** `app/scoring.py` is a pure function (no I/O, no clock). Passage duration = great-circle
distance ÷ planned speed. For each hourly departure in the forecast, the passage is GO only if every
forecast hour from departure up to the first hour at or after arrival is within the boat's limits
for wind, gusts (if set) and significant wave height. The forecast is taken at the start and the end
point and the worst value of the two wins. Exactly at the limit is GO; a `SAFETY_MARGIN` constant can
make it stricter. Missing data is NO-GO. Every NO-GO lists each failed limit with the observed value,
the limit, the amount over and the time, worst first. Departures in the past and passages that end
beyond the forecast are left out.

**Alternatives.** Sampling the route at intermediate points: more accurate, but more upstream calls
for a small gain on short passages. A score from 0 to 100: harder to explain and to trust than
"which limit, by how much".

**Consequences.** Fully unit-tested with fixtures (`tests/test_scoring.py`). Conservative on long
passages, because the worst of start and end is applied to every hour.

## 6. Language, framework and frontend

**Context.** Allowed: Python (Flask or FastAPI) or Node (Express); a static frontend.

**Decision.** Python 3.12 and FastAPI for both services: request validation with Pydantic gives
clear 422 messages for free, and both services share the same tooling (ruff, pytest, pip-audit).
The UI is plain HTML, CSS and ES modules with no build step: three pages, a small `api.js` wrapper
with a 15 s timeout, and no HTML built from server data (XSS-safe by construction).

**Alternatives.** React or Vue built to static files: more tooling for three simple pages.

**Consequences.** No frontend build to break in CI; Prettier and `node --check` are the UI's gate.
Shared code between the services (logging, DB setup) is duplicated on purpose so each service builds
from its own folder.
