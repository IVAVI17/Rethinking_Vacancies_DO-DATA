"""Serve the map and teammates' existing AI API without editing their backend.

Run from repository root:
    python -m uvicorn Backend.web_app:app --reload
"""
import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("SPACES_JSON_PATH", str(ROOT / "Data" / "dortmund_synthetic_spaces.json"))
os.environ.setdefault("EVENTS_JSON_PATH", str(ROOT / "Data" / "dortmund_public_events.json"))

# Import the team's existing FastAPI app and Groq-powered /search/prompt.
from Backend.main import LISTINGS, app, load_events_payload  # noqa: E402


@app.get("/", include_in_schema=False)
@app.get("/frontend/map.html", include_in_schema=False)
def frontend():
    path = ROOT / "frontend" / "map.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="frontend/map.html is missing")
    return FileResponse(path, media_type="text/html")



@app.get("/submit.html", include_in_schema=False)
def submission_frontend():
    path = ROOT / "frontend" / "submit.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="frontend/submit.html is missing")
    return FileResponse(path, media_type="text/html")

@app.get("/api/spaces")
def all_spaces():
    """Return the same 300 records used by /search/prompt."""
    return {
        "listings": LISTINGS,
        "total": len(LISTINGS),
        "synthetic_data": True,
        "notice": "All records are fictional hackathon demonstration listings.",
    }

@app.get("/space.html", include_in_schema=False)
def space_detail_frontend():
    path = ROOT / "frontend" / "space.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="frontend/space.html is missing")
    return FileResponse(path, media_type="text/html")



@app.get("/api/events")
def public_events():
    """Current approved/city-sourced and synthetic demo events from the team's JSON.

    User submissions pending review must not be advertised as scheduled public events.
    Read each time so refreshed JSON data is reflected without restarting the server.
    """
    payload = load_events_payload()
    visible = [
        event for event in payload["events"]
        if event.get("submission_status") != "pending_review"
    ]
    return {
        "events": visible,
        "total": len(visible),
        "city_sourced": sum(event.get("is_synthetic") is False for event in visible),
        "synthetic_demo": sum(event.get("is_synthetic") is True for event in visible),
        "notice": "City-sourced dates and venues require verification; ReVive hosted events are fictional demos.",
    }


@app.get("/frontend/events-map.js", include_in_schema=False)
def events_map_script():
    return FileResponse(ROOT / "frontend" / "events-map.js", media_type="text/javascript")


@app.get("/frontend/events-detail.js", include_in_schema=False)
def events_detail_script():
    return FileResponse(ROOT / "frontend" / "events-detail.js", media_type="text/javascript")
