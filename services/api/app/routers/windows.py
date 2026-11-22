"""GET /passages/{id}/windows: hourly departure windows, each GO or NO-GO with a reason."""

from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import SessionDep
from app.forecast_client import ForecastClient, ForecastServiceError
from app.geo import distance_nm
from app.models import Boat
from app.routers.passages import get_passage_or_404
from app.scoring import Limits, passage_duration_h, score_windows, worst_of

router = APIRouter(tags=["windows"])


def utcnow() -> datetime:
    """Separate function so tests can freeze the clock."""
    return datetime.now(UTC)


@router.get("/passages/{passage_id}/windows")
def passage_windows(passage_id: int, request: Request, session: SessionDep):
    settings = request.app.state.settings
    passage = get_passage_or_404(session, passage_id)
    boat = session.get(Boat, passage.boat_id)
    limits = Limits(boat.max_wind_kn, boat.max_wave_m, boat.max_gust_kn)

    distance = distance_nm(passage.start_lat, passage.start_lon, passage.end_lat, passage.end_lon)
    duration = passage_duration_h(distance, passage.speed_kn)

    points = {(round(passage.start_lat, 2), round(passage.start_lon, 2))}
    points.add((round(passage.end_lat, 2), round(passage.end_lon, 2)))
    client = ForecastClient(
        request.app.state.http, settings.forecast_url, settings.forecast_timeout_s
    )
    try:
        fetched = [client.hourly(lat, lon, settings.forecast_days) for lat, lon in sorted(points)]
    except ForecastServiceError as exc:
        # Partial failure (brief §6): CRUD keeps working; this flow fails fast and clearly.
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "detail": f"Forecast unavailable: {exc}. Boats and passages still work; "
                "try the windows again in a minute.",
                "passage_id": passage_id,
                "windows": [],
            },
        )

    hours = worst_of(*(series for series, _ in fetched))
    this_hour = utcnow().replace(minute=0, second=0, microsecond=0)
    windows = score_windows(limits, hours, duration, not_before=this_hour)
    go = [w for w in windows if w.go]
    return {
        "status": "ok",
        "passage_id": passage.id,
        "boat_id": boat.id,
        "distance_nm": round(distance, 1),
        "duration_h": round(duration, 1),
        "speed_kn": passage.speed_kn,
        "limits": asdict(limits),
        "forecast": {
            "source": "open-meteo",
            "points": len(points),
            "horizon_hours": len(hours),
            "stale": any(stale for _, stale in fetched),
        },
        "summary": {
            "windows": len(windows),
            "go": len(go),
            "no_go": len(windows) - len(go),
            "first_go": go[0].departure if go else None,
            "note": None if windows else "Passage is longer than the forecast horizon.",
        },
        "windows": [asdict(w) for w in windows],
    }
