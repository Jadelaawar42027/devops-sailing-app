"""HTTP client for the forecast service, with a hard timeout and clear error messages."""

import logging
import time
from datetime import datetime

import httpx

from app.scoring import HourConditions

log = logging.getLogger("upstream")


class ForecastServiceError(Exception):
    """The forecast service is down, slow, or could not get a forecast."""


class ForecastClient:
    def __init__(self, http: httpx.Client, base_url: str, timeout_s: float) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def hourly(self, lat: float, lon: float, days: int) -> tuple[list[HourConditions], bool]:
        """Return (hours, stale)."""
        start = time.perf_counter()
        status = None
        try:
            response = self.http.get(
                f"{self.base_url}/forecast",
                params={"lat": lat, "lon": lon, "days": days},
                timeout=self.timeout_s,
            )
            status = response.status_code
            if response.status_code != 200:
                raise ForecastServiceError(_detail(response))
            body = response.json()
            hours = [_hour(h) for h in body["hours"]]
            return hours, bool(body.get("stale"))
        except httpx.TimeoutException as exc:
            raise ForecastServiceError(
                f"forecast service did not answer within {self.timeout_s:g}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise ForecastServiceError(
                f"forecast service is unreachable ({type(exc).__name__})"
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ForecastServiceError("forecast service sent an unexpected response") from exc
        finally:
            log.info(
                "upstream call",
                extra={
                    "fields": {
                        "upstream": "forecast-service",
                        "status": status,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    }
                },
            )


def _detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    return detail or f"forecast service answered HTTP {response.status_code}"


def _hour(h: dict) -> HourConditions:
    return HourConditions(
        time=datetime.fromisoformat(h["time"].replace("Z", "+00:00")),
        wind_kn=h.get("wind_kn"),
        gust_kn=h.get("gust_kn"),
        wave_m=h.get("wave_m"),
    )
