# Rural Symptom Triage Bot
Flask app: symptoms in EN/KN/HI -> Red/Amber/Green + next step. Red-flag check runs before the LLM.

## Run
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # add GEMINI_API_KEY
    python app.py          # http://localhost:5001

Messages over 1000 characters return HTTP 400 `{"error":"too_long"}`, unless they contain a red flag, which still returns RED.
