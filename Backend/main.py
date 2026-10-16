import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from groq import Groq
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).resolve().parent / ".env")

DATA_FILE = Path(os.getenv(
    "SPACES_JSON_PATH",
    r"C:\Users\DELL\Desktop\PROJECTS\DO_DATA_code\Rethinking_Vacancies_DO-DATA\Data\dortmund_synthetic_spaces.json"
))
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

app = FastAPI(
    title="SpaceMatch Dortmund API",
    description="Search synthetic Dortmund space listings by filters or natural-language prompt.",
    version="1.0.0",
)

# Development-friendly CORS. For deployment, replace "*" with your frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_listings() -> list[dict[str, Any]]:
    if not DATA_FILE.exists():
        raise RuntimeError(
            f"Data file not found: {DATA_FILE}. Put "
            "'dortmund_synthetic_spaces_300.json' beside main.py or set SPACES_JSON_PATH."
        )
    with DATA_FILE.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, dict):
        listings = payload.get("listings", [])
    elif isinstance(payload, list):
        listings = payload
    else:
        raise RuntimeError("JSON must contain a 'listings' array or be a JSON array.")
    if not isinstance(listings, list):
        raise RuntimeError("JSON must contain a 'listings' array or be a JSON array.")
    return listings


LISTINGS = load_listings()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class FilterSearchRequest(BaseModel):
    area: Optional[str] = Field(default=None, description="Dortmund district or postcode, e.g. Hörde or 44263")
    purpose: Optional[str] = Field(default=None, description="Purpose such as tutoring, music, office")
    min_area_sqm: Optional[float] = Field(default=None, ge=0)
    max_area_sqm: Optional[float] = Field(default=None, ge=0)
    min_capacity: Optional[int] = Field(default=None, ge=0)
    max_hourly_price: Optional[float] = Field(default=None, ge=0)
    max_daily_price: Optional[float] = Field(default=None, ge=0)
    max_weekly_price: Optional[float] = Field(default=None, ge=0)
    max_monthly_price: Optional[float] = Field(default=None, ge=0)
    duration_type: Optional[str] = Field(default=None, description="short_term, long_term, or flexible")
    days_of_week: list[str] = Field(default_factory=list)
    time_from: Optional[str] = Field(default=None, description="HH:MM")
    time_until: Optional[str] = Field(default=None, description="HH:MM")
    parking_required: Optional[bool] = None
    washroom_required: Optional[bool] = None
    kitchen_required: Optional[bool] = None
    wifi_required: Optional[bool] = None
    negotiable_only: Optional[bool] = None
    deposit_required: Optional[bool] = None
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    limit: Optional[int] = Field(default=None, ge=0)
    offset: int = Field(default=0, ge=0)


class PromptSearchRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    limit: Optional[int] = Field(default=None, ge=0)
    offset: int = Field(default=0, ge=0)


class ParsedCriteria(BaseModel):
    area: Optional[str] = None
    purpose: Optional[str] = None
    min_area_sqm: Optional[float] = None
    max_area_sqm: Optional[float] = None
    min_capacity: Optional[int] = None
    max_hourly_price: Optional[float] = None
    max_daily_price: Optional[float] = None
    max_weekly_price: Optional[float] = None
    max_monthly_price: Optional[float] = None
    duration_type: Optional[str] = None
    days_of_week: list[str] = Field(default_factory=list)
    time_from: Optional[str] = None
    time_until: Optional[str] = None
    parking_required: Optional[bool] = None
    washroom_required: Optional[bool] = None
    kitchen_required: Optional[bool] = None
    wifi_required: Optional[bool] = None
    negotiable_only: Optional[bool] = None
    deposit_required: Optional[bool] = None

class ReviewRequest(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
VALID_DAYS = {
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday"
}


def normalise_text(value: Any) -> str:
    return str(value or "").strip().casefold()


def price_rate(listing: dict, unit: str) -> Optional[float]:
    price = listing.get("price") or {}
    rates = price.get("rates") or {}
    value = rates.get(unit)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def listing_matches(listing: dict, f: FilterSearchRequest | ParsedCriteria) -> bool:
    address = listing.get("address") or {}
    availability = listing.get("availability") or {}
    facilities = listing.get("facilities") or {}
    price = listing.get("price") or {}
    deposit = price.get("deposit") or {}
    reviews = listing.get("reviews") or {}

    # Location search: match district, postcode, or address text.
    if f.area:
        needle = normalise_text(f.area)
        location_text = " ".join([
            str(address.get("district", "")),
            str(address.get("postcode", "")),
            str(address.get("exact_address", "")),
        ]).casefold()
        if needle not in location_text:
            return False

    if f.purpose:
        purpose_needle = normalise_text(f.purpose)
        purposes = [normalise_text(x) for x in listing.get("purposes_allowed_or_suggested", [])]
        # Accept partial matches such as "teach" matching "tutoring" is not assumed;
        # the AI can map synonyms to the canonical purpose, while filter UI should use values.
        if not any(purpose_needle in p or p in purpose_needle for p in purposes):
            return False

    area = listing.get("area_sqm")
    if f.min_area_sqm is not None and (area is None or float(area) < f.min_area_sqm):
        return False
    if f.max_area_sqm is not None and (area is None or float(area) > f.max_area_sqm):
        return False

    capacity = listing.get("capacity_people")
    if f.min_capacity is not None and (capacity is None or int(capacity) < f.min_capacity):
        return False

    # If a price cap is supplied, listings without that rate are excluded rather than
    # incorrectly assuming a different price unit is equivalent.
    for unit, attr in [
        ("hour", "max_hourly_price"),
        ("day", "max_daily_price"),
        ("week", "max_weekly_price"),
        ("month", "max_monthly_price"),
    ]:
        cap = getattr(f, attr, None)
        rate = price_rate(listing, unit)
        if cap is not None and (rate is None or rate > cap):
            return False

    if f.duration_type and normalise_text(availability.get("duration_type")) != normalise_text(f.duration_type):
        return False

    requested_days = {normalise_text(d) for d in (f.days_of_week or []) if normalise_text(d)}
    if requested_days:
        offered_days = {normalise_text(d) for d in availability.get("days_of_week", [])}
        if not requested_days.issubset(offered_days):
            return False

    # Time overlap: listing must cover the requested time interval.
    offered_from = availability.get("time_from")
    offered_until = availability.get("time_until")
    if f.time_from:
        if not offered_from or offered_from > f.time_from:
            return False
    if f.time_until:
        if not offered_until or offered_until < f.time_until:
            return False

    for attr, facility_key in [
        ("parking_required", "parking_available"),
        ("washroom_required", "washroom_available"),
        ("kitchen_required", "kitchen_available"),
        ("wifi_required", "wifi_available"),
    ]:
        required = getattr(f, attr, None)
        if required is True and facilities.get(facility_key) is not True:
            return False

    if f.negotiable_only is True and price.get("negotiable") is not True:
        return False
    if f.deposit_required is not None and deposit.get("required") is not f.deposit_required:
        return False

    if getattr(f, "min_rating", None) is not None:
        rating = reviews.get("average_stars")
        if rating is None or float(rating) < f.min_rating:
            return False

    return True


def public_listing(listing: dict) -> dict:
    # Include all listing fields in this prototype. In production, hide private owner data
    # until the user submits an inquiry and add appropriate access controls.
    return listing


def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured. Add it to your environment before using prompt search."
        )
    return Groq(api_key=api_key)


def parse_prompt_with_groq(prompt: str) -> ParsedCriteria:
    client = get_groq_client()

    schema_hint = {
        "area": "district or postcode in Dortmund, or null",
        "purpose": "canonical short purpose e.g. tutoring, music, office, workshops, or null",
        "min_area_sqm": "number or null",
        "max_area_sqm": "number or null",
        "min_capacity": "integer or null",
        "max_hourly_price": "number or null, only if user specifies an hourly budget",
        "max_daily_price": "number or null, only if user specifies a daily budget",
        "max_weekly_price": "number or null, only if user specifies a weekly budget",
        "max_monthly_price": "number or null, only if user specifies a monthly budget",
        "duration_type": "short_term, long_term, flexible, or null",
        "days_of_week": "array of English weekday names",
        "time_from": "24-hour HH:MM or null",
        "time_until": "24-hour HH:MM or null",
        "parking_required": "true only if explicitly requested, otherwise null",
        "washroom_required": "true only if explicitly requested, otherwise null",
        "kitchen_required": "true only if explicitly requested, otherwise null",
        "wifi_required": "true only if explicitly requested, otherwise null",
        "negotiable_only": "true only if user insists on negotiable price, otherwise null",
        "deposit_required": "true/false only if explicitly requested, otherwise null"
    }

    system_prompt = (
        "You extract search filters for a Dortmund workspace/commercial-space marketplace. "
        "Return only a JSON object matching the requested keys. Do not invent requirements. "
        "Use null for unspecified scalar fields and [] for unspecified days. "
        "Convert German weekday names to English weekday names. "
        "For 'city centre' or 'Innenstadt', use area='Innenstadt'. "
        "Price limits must retain their unit: never convert hourly prices to monthly or vice versa. "
        "If the user says 'under/up to/maximum €X per hour', set max_hourly_price=X. "
        "If a user asks for a purpose such as lessons, map it to 'tutoring'; classes/workshops to 'workshops'. "
        "Only extract filters; do not answer the user or recommend listings."
    )

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt + "\nFields: " + json.dumps(schema_hint)},
                {"role": "user", "content": prompt},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        raw = json.loads(content)
        # Discard unexpected keys before Pydantic validation.
        allowed = set(ParsedCriteria.model_fields.keys())
        cleaned = {k: v for k, v in raw.items() if k in allowed}
        criteria = ParsedCriteria.model_validate(cleaned)
        if criteria.duration_type and criteria.duration_type not in {"short_term", "long_term", "flexible"}:
            criteria.duration_type = None
        criteria.days_of_week = [
            d.title() for d in criteria.days_of_week if normalise_text(d) in VALID_DAYS
        ]
        return criteria
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not parse prompt with Groq: {exc}") from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "listing_count": len(LISTINGS), "data_file": DATA_FILE.name}


@app.get("/filters/options")
def filter_options():
    districts = sorted({(x.get("address") or {}).get("district") for x in LISTINGS if (x.get("address") or {}).get("district")})
    purposes = sorted({p for x in LISTINGS for p in x.get("purposes_allowed_or_suggested", [])})
    return {
        "districts": districts,
        "purposes": purposes,
        "duration_types": ["short_term", "long_term", "flexible"],
        "price_units": ["hour", "day", "week", "month"],
        "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    }


@app.post("/search/filters")
def search_by_filters(filters: FilterSearchRequest):
    matches = [x for x in LISTINGS if listing_matches(x, filters)]
    return {
        "mode": "filters",
        "total": len(matches),
        "results": [public_listing(x) for x in matches],
        "synthetic_data": True,
        "notice": "Listings are synthetic demo records; availability and property details are not verified."
    }


@app.post("/search/prompt")
def search_by_prompt(request: PromptSearchRequest):
    criteria = parse_prompt_with_groq(request.prompt)
    matches = [x for x in LISTINGS if listing_matches(x, criteria)]
    return {
        "mode": "prompt",
        "original_prompt": request.prompt,
        "parsed_criteria": criteria.model_dump(),
        "total": len(matches),
        "results": [public_listing(x) for x in matches],
        "synthetic_data": True,
        "notice": "AI extracts filters only. Results are matched against the JSON dataset; listings are synthetic and not verified."
    }


@app.get("/spaces/{space_id}")
def get_space(space_id: str):
    for listing in LISTINGS:
        if listing.get("id") == space_id:
            return public_listing(listing)
    raise HTTPException(status_code=404, detail="Space not found")

@app.post("/spaces/{space_id}/reviews")
def add_review(space_id: str, review: ReviewRequest):
    # Find the listing by ID
    listing = next(
        (space for space in LISTINGS if str(space.get("id")) == space_id),
        None
    )

    if listing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Space with ID '{space_id}' not found"
        )

    # Ensure the reviews structure exists
    if not isinstance(listing.get("reviews"), dict):
        listing["reviews"] = {
            "average_stars": 0,
            "review_count": 0,
            "items": [],
            "is_synthetic": True
        }

    reviews = listing["reviews"]
    reviews.setdefault("items", [])

    # Create the new review
    new_review = {
        "stars": review.stars,
        "comment": review.comment,
        "is_synthetic": True
    }

    # Append the review
    reviews["items"].append(new_review)

    # Update rating statistics
    all_reviews = reviews["items"]
    reviews["review_count"] = len(all_reviews)
    reviews["average_stars"] = round(
        sum(item["stars"] for item in all_reviews) / len(all_reviews),
        1
    )

    # Persist the updated listings to the JSON file
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(
                LISTINGS,
                file,
                indent=4,
                ensure_ascii=False
            )
    except OSError as exc:
        # Roll back the in-memory addition if saving fails
        reviews["items"].pop()
        reviews["review_count"] = len(reviews["items"])
        if reviews["items"]:
            reviews["average_stars"] = round(
                sum(item["stars"] for item in reviews["items"])
                / len(reviews["items"]),
                1
            )
        else:
            reviews["average_stars"] = 0

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save review to JSON: {exc}"
        )

    return {
        "message": "Review added successfully",
        "space_id": space_id,
        "review": new_review,
        "review_count": reviews["review_count"],
        "average_stars": reviews["average_stars"]
    }