# API contract (backend -> frontend)

Frontend lives in `templates/index.html` + `static/` (app.js, app.css, i18n.js, manifest.json, icon.svg). Backend owner: do not edit these. Frontend owner: do not edit `app.py` / `redflags.py`.
Family profiles, check history and the saved places list are stored only in the browser (localStorage); the backend keeps no user data.

## POST /chat
Request JSON:
    {"message": "text", "language": "en" | "kn" | "hi" | "ta" | "te" | "ml", "history": [{"role": "user"|"bot", "text": "..."}],
     "profile": {"age": 64, "sex": "male"|"female"|"other", "pregnant": true, "conditions": ["diabetes", ...],
                 "allergies": "text", "medicines": "text"}}

`history` = all earlier turns, oldest first. Frontend appends the user message AND the bot question reply to it after each turn.
`profile` is optional (the family member the check is for). Every field is optional; send medical facts only, never names or phone numbers.
The backend adds it to the LLM prompt only; the red-flag check still scans the user's own words.
After 2 bot questions in `history` the backend tells the LLM it must give a final triage.

Response JSON — 3 shapes, switch on `type`:

1. Follow-up question
       {"type": "question", "reply": "text in user's language", "level": null, "symptoms_en": [...]}
   -> show as a chat bubble, keep chatting.

2. Final triage
       {"type": "final", "level": "RED" | "AMBER" | "GREEN", "reply": "...", "reason": "...", "advice": "...", "symptoms_en": [...]}
   -> show coloured card (level), reason, advice. RED/AMBER: show "Call 108" button (tel:108). Conversation is over; clear history.
   RED from the hard-coded check also has `"matched": "<keyword>"` (ignore it in UI).

3. Error
       {"type": "error", "reply": "text in user's language"}
   -> show as bubble. Empty message returns HTTP 400 {"error": "empty"}.

## GET /places?lat=12.52&lon=76.89
Nearby health facilities from OpenStreetMap (Overpass, with Nominatim as fallback). Can take up to ~60 s; cached ~6 h per ~1 km cell.

    {"places": [{"name": "...", "local_name": "...", "kind": "govt"|"hospital"|"clinic"|"ngo",
                 "sub": "phc"|"chc"|"subcentre"|"govt_hospital"|"govt_centre"|"hospital"|"clinic"|"ngo"|"charity_hospital",
                 "lat": 12.5, "lon": 76.9, "distance_km": 1.2, "phone": "...", "address": "...",
                 "emergency": true, "opening_hours": "..."}],
     "radius_km": 13, "source": "OpenStreetMap"}

Sorted by distance, max 25 per kind. Bad lat/lon -> 400 {"error": "bad location"}; both sources down -> 502 {"error": "unavailable"}.

## GET /geocode?q=Pandavapura&lang=kn
Village / town name -> coordinates (Nominatim, India only, Karnataka preferred).

    {"results": [{"name": "Pandavapura, Mandya district, Karnataka, India", "lat": 12.49, "lon": 76.67}]}

Empty q -> 400 {"error": "empty"}; lookup failed -> 502 {"error": "unavailable"}.

## Notes
- Run locally: http://localhost:5001
- The mic (Web Speech API) is frontend-only: set recognition.lang to en-IN / kn-IN / hi-IN / ta-IN / te-IN / ml-IN, put the transcript in the message box, send it to /chat.

## Scope (Karnataka only)
The bot assumes the user is in Karnataka: advice points to 108 / 112, PHC, CHC, taluk or district government hospital.
Languages (picker order): English, ಕನ್ನಡ (kn, default for Karnataka), हिन्दी, தமிழ், తెలుగు, മലയാളം.
Frontend must translate its static UI text for all 6 languages and render all scripts correctly.
It's a mobile web app: design for 360px width first; optionally add a web app manifest + theme-color so it can be "Add to Home Screen".

## Frontend notes
- HTTP 400 {"error":"too_long"} for messages over 1000 characters
- HTTP 400 {"error":"bad_request"} for wrong JSON types, such as `history` as a string; a `history` item with `text` null counts as empty
- /chat answers within 35 s, also when a provider is down, so a client timeout should be longer than that
- do not add type error replies to history
- clear history after a final result
