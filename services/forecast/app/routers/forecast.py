from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app import cache
from app.db import SessionDep
from app.openmeteo import OpenMeteoClient
from app.service import ForecastUnavailable, cached_fetch

router = APIRouter(tags=["forecast"])

Lat = Annotated[float, Query(ge=-90, le=90, description="Latitude, decimal degrees")]
Lon = Annotated[float, Query(ge=-180, le=180, description="Longitude, decimal degrees")]


def _client(request: Request) -> OpenMeteoClient:
    return OpenMeteoClient(request.app.state.http, request.app.state.settings)


def _meta(lat: float, lon: float, status: str, age: float) -> dict:
    return {
        "latitude": round(lat, 2),
        "longitude": round(lon, 2),
        "source": "open-meteo",
        "cache": status,
        "age_s": round(age),
        "stale": status == "stale",
    }


@router.get("/forecast")
def forecast(
    request: Request,
    session: SessionDep,
    lat: Lat,
    lon: Lon,
    days: Annotated[int, Query(ge=1, le=7)] = 3,
):
    """Hourly wind (kn), gusts (kn) and significant wave height (m), UTC."""
    lat, lon = round(lat, 2), round(lon, 2)
    settings = request.app.state.settings
    key = cache.cache_key("forecast", lat, lon, days)
    try:
        hours, status, age = cached_fetch(
            session, key, settings.forecast_ttl_s, lambda: _client(request).hourly(lat, lon, days)
        )
    except ForecastUnavailable as exc:
        raise HTTPException(503, f"Forecast unavailable: {exc}") from exc
    return {**_meta(lat, lon, status, age), "hours": hours}


@router.get("/current")
def current(request: Request, session: SessionDep, lat: Lat, lon: Lon):
    """Current wind and sea state at a point."""
    lat, lon = round(lat, 2), round(lon, 2)
    settings = request.app.state.settings
    key = cache.cache_key("current", lat, lon)
    try:
        now, status, age = cached_fetch(
            session, key, settings.current_ttl_s, lambda: _client(request).current(lat, lon)
        )
    except ForecastUnavailable as exc:
        raise HTTPException(503, f"Current conditions unavailable: {exc}") from exc
    return {**_meta(lat, lon, status, age), "current": now}
