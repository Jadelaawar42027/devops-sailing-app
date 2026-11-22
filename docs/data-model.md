# Data model

Two databases, one per service (brief §3a). The schema is owned by the Alembic migrations, which
run on each service's startup:
`services/api/migrations/versions/0001_boats_and_passages.py` and
`services/forecast/migrations/versions/0001_forecast_cache.py`.

## API database (`sdd-3a-g<N>-api-db`)

```mermaid
erDiagram
  BOATS ||--o{ PASSAGES : "sails"
  BOATS {
    int id PK
    nvarchar(100) name
    float max_wind_kn "sustained wind limit, knots"
    float max_gust_kn "nullable: gusts not checked"
    float max_wave_m "significant wave height limit, metres"
    datetime created_at
    datetime updated_at
  }
  PASSAGES {
    int id PK
    int boat_id FK "indexed"
    nvarchar(100) name
    float start_lat
    float start_lon
    float end_lat
    float end_lon
    float speed_kn "planned average speed"
    datetime created_at
    datetime updated_at
  }
```

- A boat has many passages; a passage belongs to exactly one boat.
- Deleting a boat that still has passages is refused with `409 Conflict`.
- Validation (Pydantic, `app/schemas.py`): names 1–100 characters; wind 0–80 kn; gust 0–100 kn and not
  below the wind limit; waves 0–15 m; latitude ±90; longitude ±180; speed 0–40 kn.
- Times are stored in UTC.

## Forecast database (`sdd-3a-g<N>-forecast-db`)

```mermaid
erDiagram
  FORECAST_CACHE {
    int id PK
    varchar(100) cache_key UK "kind:lat:lon[:days], coordinates rounded to 0.01 degree"
    nvarchar(max) payload "JSON: merged hourly series or current conditions"
    datetime fetched_at "UTC; fresh for 30 min (forecast) or 10 min (current)"
  }
```

- No relationship to the API database: the services share data only over HTTP.
- Rows older than 7 days are deleted on write. Expired rows are still used as a stale fallback when
  Open-Meteo is down.

## Computed, not stored

The departure windows (`GET /passages/{id}/windows`) are calculated on every request from a passage,
its boat and the forecast. They are not persisted, so they are never out of date.
