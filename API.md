# API contract (backend -> frontend)

Frontend lives in `templates/index.html` (+ optional `static/`). Backend owner: do not edit these. Frontend owner: do not edit `app.py` / `redflags.py`.

## POST /chat
Request JSON:
    {"message": "text", "language": "en" | "kn" | "hi" | "ta" | "te" | "ml", "history": [{"role": "user"|"bot", "text": "..."}]}

`history` = all earlier turns, oldest first. Frontend appends the user message AND the bot question reply to it after each turn.

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
- do not add type error replies to history
- clear history after a final result
