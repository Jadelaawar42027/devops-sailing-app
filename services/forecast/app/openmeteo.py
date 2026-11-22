"""Open-Meteo client: wind from the weather API, waves from the Marine API (no key needed).

Every call has a hard timeout. Any failure becomes UpstreamError with a short, clear reason.
"""

import logging
import time

import httpx

from app.config import Settings

log = logging.getLogger("upstream")

WIND_VARS = "wind_speed_10m,wind_gusts_10m,wind_direction_10m"
WAVE_VARS = "wave_height,wave_direction,wave_period"


class UpstreamError(Exception):
    """Open-Meteo is down, slow, or answered with an error."""


def _utc(t: str) -> str:
    """Open-Meteo returns '2026-11-22T13:00' in the requested timezone (UTC)."""
    return t if t.endswith("Z") else f"{t}Z"


class OpenMeteoClient:
    def __init__(self, http: httpx.Client, settings: Settings) -> None:
        self.http = http
        self.settings = settings

    def _get(self, name: str, url: str, params: dict) -> dict:
        start = time.perf_counter()
        status = None
        try:
            response = self.http.get(url, params=params, timeout=self.settings.upstream_timeout_s)
            status = response.status_code
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("error"):
                raise UpstreamError(f"{name} returned an error: {data.get('reason', 'unknown')}")
            return data
        except httpx.TimeoutException as exc:
            raise UpstreamError(
                f"{name} did not answer within {self.settings.upstream_timeout_s:g}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(f"{name} answered HTTP {status}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamError(f"{name} is unreachable ({type(exc).__name__})") from exc
        finally:
            log.info(
                "upstream call",
                extra={
                    "fields": {
                        "upstream": name,
                        "status": status,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    }
                },
            )

    def _params(self, lat: float, lon: float, **extra) -> dict:
        return {"latitude": lat, "longitude": lon, "timezone": "UTC", **extra}

    def hourly(self, lat: float, lon: float, days: int) -> list[dict]:
        weather = self._get(
            "open-meteo-weather",
            self.settings.weather_url,
            self._params(lat, lon, hourly=WIND_VARS, wind_speed_unit="kn", forecast_days=days),
        )
        marine = self._get(
            "open-meteo-marine",
            self.settings.marine_url,
            self._params(lat, lon, hourly=WAVE_VARS, forecast_days=days),
        )
        return merge_hourly(weather.get("hourly", {}), marine.get("hourly", {}))

    def current(self, lat: float, lon: float) -> dict:
        weather = self._get(
            "open-meteo-weather",
            self.settings.weather_url,
            self._params(lat, lon, current=WIND_VARS, wind_speed_unit="kn"),
        )
        marine = self._get(
            "open-meteo-marine",
            self.settings.marine_url,
            self._params(lat, lon, current=WAVE_VARS),
        )
        w, m = weather.get("current", {}), marine.get("current", {})
        return {
            "time": _utc(w.get("time") or m.get("time", "")),
            "wind_kn": w.get("wind_speed_10m"),
            "gust_kn": w.get("wind_gusts_10m"),
            "wind_dir_deg": w.get("wind_direction_10m"),
            "wave_m": m.get("wave_height"),
            "wave_dir_deg": m.get("wave_direction"),
            "wave_period_s": m.get("wave_period"),
        }


def merge_hourly(weather: dict, marine: dict) -> list[dict]:
    """Join the two hourly series on time. Missing values stay None (e.g. waves on land)."""
    waves = {
        t: (h, d, p)
        for t, h, d, p in zip(
            marine.get("time", []),
            marine.get("wave_height", []),
            marine.get("wave_direction", []),
            marine.get("wave_period", []),
            strict=False,
        )
    }
    hours = []
    for i, t in enumerate(weather.get("time", [])):
        wave_h, wave_d, wave_p = waves.get(t, (None, None, None))
        hours.append(
            {
                "time": _utc(t),
                "wind_kn": _at(weather.get("wind_speed_10m"), i),
                "gust_kn": _at(weather.get("wind_gusts_10m"), i),
                "wind_dir_deg": _at(weather.get("wind_direction_10m"), i),
                "wave_m": wave_h,
                "wave_dir_deg": wave_d,
                "wave_period_s": wave_p,
            }
        )
    return hours


def _at(values: list | None, i: int):
    return values[i] if values and i < len(values) else None
