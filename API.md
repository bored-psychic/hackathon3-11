# API contract (backend -> frontend)

Frontend lives in `templates/index.html` (+ optional `static/`). Backend owner: do not edit these. Frontend owner: do not edit `app.py` / `redflags.py`.

## POST /chat
Request JSON:
    {"message": "text", "language": "en" | "kn" | "hi", "history": [{"role": "user"|"bot", "text": "..."}]}

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
- The mic (Web Speech API) is frontend-only: set recognition.lang to en-IN / kn-IN / hi-IN, put the transcript in the message box, send it to /chat.
