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

## Motion and 3D (frontend only)
GSAP and Three.js are vendored in `static/vendor/` (versions and licences in its README), so the app needs no CDN. Google Fonts is the only external request.
- `static/motion.js` holds the choreography behind `window.Motion`. `static/app.js` works the same without it.
- `static/fx3d.js` is the 3D form. It loads only with width >= 1024px, no reduced motion, WebGL2 and memory >= 4 GB (or unknown). Otherwise a static blurred shape shows. Add `?fx=off` to the URL to force that.
- Three tiers: full (desktop), lite (phones and low-power: faster, transform and opacity only, no 3D), off (`prefers-reduced-motion`: nothing moves).
- Safety: the 108 button is never animated, and a RED card with its Call 108 link is fully visible from the first frame.

## Open it on a phone (same Wi-Fi)
    python app.py --wifi        # or: SHARE_ON_WIFI=1 python app.py
It prints the address to type on the phone, e.g. `http://192.168.1.5:5001`. The phone must be on the same Wi-Fi.
- macOS may ask "Allow incoming connections" for Python: click Allow.
- In this mode the debugger is always off, because anyone on the same Wi-Fi can reach the app.
- Phone browsers only allow the microphone on https or localhost, so voice input will not work over this address.
  For voice on a phone, use an https tunnel (e.g. ngrok) instead.
