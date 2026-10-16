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

# Import the team's existing FastAPI app and Groq-powered /search/prompt.
from Backend.main import LISTINGS, app  # noqa: E402


@app.get("/", include_in_schema=False)
@app.get("/frontend/map.html", include_in_schema=False)
def frontend():
    path = ROOT / "frontend" / "map.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="frontend/map.html is missing")
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

