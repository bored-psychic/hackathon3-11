# Rural Symptom Triage Bot
Flask app: symptoms in EN/KN/HI -> Red/Amber/Green + next step. Red-flag check runs before the LLM.

## Run
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # add GEMINI_API_KEY
    python app.py          # http://localhost:5001

## Test
    python -m unittest tests.test_backend -v   # offline, LLM is mocked (no key needed)
    python tests/run_demo.py                   # live, needs GEMINI_API_KEY
