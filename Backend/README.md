# SpaceMatch Dortmund — FastAPI backend

This backend supports two search modes over `dortmund_synthetic_spaces_300.json`:

1. **Manual filters**: location/district, purpose, area, capacity, price caps by unit, duration, days/time, amenities, negotiable price, deposit and rating.
2. **Prompt search**: Groq extracts structured filters from a natural-language request, then the same deterministic filter engine searches the JSON.

> The current JSON records are synthetic demo data. The API returns that warning in every search response. Do not use this dataset for real bookings.

## 1. Setup

Use Python 3.10+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Place `dortmund_synthetic_spaces_300.json` in the same directory as `main.py`. The JSON file is supplied separately in the conversation. Or set `SPACES_JSON_PATH` to its full path.

Set your Groq key as an environment variable. Get it from the Groq Console; never commit it to Git.

Windows PowerShell:
```powershell
$env:GROQ_API_KEY="your-key"
$env:GROQ_MODEL="llama-3.3-70b-versatile"
```

macOS/Linux:
```bash
export GROQ_API_KEY="your-key"
export GROQ_MODEL="llama-3.3-70b-versatile"
```

If Groq says the model is unavailable, change `GROQ_MODEL` to a model currently supported by your Groq account.

## 2. Start the server

```bash
uvicorn main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## 3. Example: manual filters

POST `http://127.0.0.1:8000/search/filters`

```json
{
  "area": "Hörde",
  "purpose": "tutoring",
  "min_area_sqm": 25,
  "max_area_sqm": 100,
  "min_capacity": 4,
  "max_hourly_price": 50,
  "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  "time_from": "14:00",
  "time_until": "15:00",
  "wifi_required": true,
  "limit": 20,
  "offset": 0
}
```

Every filter is optional. Use `area` with a district name, postcode, or matching address text. Price caps are unit-specific: an hourly cap only matches records that include an hourly rate.

## 4. Example: natural-language prompt

POST `http://127.0.0.1:8000/search/prompt`

```json
{
  "prompt": "I need a tutoring room in Hörde for at least four people, Monday to Friday from 2 pm to 3 pm, with Wi-Fi, up to 50 euros per hour.",
  "limit": 20,
  "offset": 0
}
```

The response includes `parsed_criteria`, `total`, and `results`, so the frontend can show the extracted filters and matching listings.

## 5. Useful endpoints

- `GET /health`
- `GET /filters/options`
- `POST /search/filters`
- `POST /search/prompt`
- `GET /spaces/{space_id}`

## Notes before deployment

- CORS currently allows all origins for local development. Restrict it to your frontend domain before deploying.
- Add rate limiting and sensible Groq error handling before public launch.
- Never expose owner private data without permission. Current demo contact details use `example.com`.
- This prototype matches strings and synthetic attributes; it does not calculate real route times or verify availability.
- The `parking_required`, `washroom_required`, `kitchen_required`, and `wifi_required` fields only filter when the request is `true`. False means “no requirement”, not “must be absent”.
