# Rural Symptom Triage Bot (English, Kannada, Hindi, Tamil, Telugu, Malayalam)
Flask app: symptoms in EN/KN/HI/TA/TE/ML -> Red/Amber/Green + next step. Red-flag check runs before the LLM.

## Run
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # add LLM_API_KEY
    python app.py          # http://localhost:5001

Debug mode is off. Set `FLASK_DEBUG=1` to turn it on for local work only.

## LLM provider (free, no card or billing)
Set `LLM_PROVIDER` to `groq` (default), `openrouter` or `gemini`, and `LLM_API_KEY` to that provider's key.
`LLM_MODEL` is optional for Groq (default `openai/gpt-oss-120b`) and required for OpenRouter: choose a `:free` id.
List the ids a provider offers now with `python tests/list_models.py [provider]`. Model names change, so pick from that list.
Gemini also reads `GEMINI_API_KEY` and `GEMINI_MODEL` when `LLM_API_KEY` and `LLM_MODEL` are empty. A setup with only `GEMINI_API_KEY` stays on Gemini until `LLM_API_KEY` or `LLM_PROVIDER` is set.
On HTTP 429 the app waits 60 seconds and retries once, so that reply is slow.

Messages over 1000 characters return HTTP 400 `{"error":"too_long"}`, unless they contain a red flag, which still returns RED.
