# Rural Symptom Triage Bot (English, Kannada, Hindi, Tamil, Telugu, Malayalam)
Flask app: symptoms in EN/KN/HI/TA/TE/ML -> Red/Amber/Green + next step. Red-flag check runs before the LLM.

## Run
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # add LLM_API_KEY
    python app.py          # http://localhost:5001

Debug mode is off. Set `FLASK_DEBUG=1` to turn it on for local work only.

## LLM provider (free, no card or billing)
Set `LLM_PROVIDER` to `groq` (default), `openrouter` or `gemini`. Groq and OpenRouter read `LLM_API_KEY`; Gemini reads only `GEMINI_API_KEY`, so one provider's key is never sent to another.
`LLM_MODEL` is optional for Groq (default `openai/gpt-oss-120b`) and required for OpenRouter: choose a `:free` id.
List the ids a provider offers now with `python tests/list_models.py [provider]`. Model names change, so pick from that list.
`GEMINI_MODEL` is a comma-separated list tried in order, because free-tier quotas are per model. A setup with only `GEMINI_API_KEY` stays on Gemini until `LLM_API_KEY` or `LLM_PROVIDER` is set.

When a provider fails, `/chat` still answers within 35 seconds, in the user's language:
- HTTP 401, 429 or 5xx, a timeout or a connection error: the same request goes straight to Gemini, if `GEMINI_API_KEY` is set.
- After a 429 only: if Gemini also fails or is not set, the app waits 3 seconds and tries the chosen provider once more.
- If all of that fails, or 35 seconds run out, the user gets the error reply. The log names the provider that answered and nothing else about it.

Messages over 1000 characters return HTTP 400 `{"error":"too_long"}`, and malformed requests return HTTP 400 `{"error":"bad_request"}`, unless the message contains a red flag, which still returns RED.
