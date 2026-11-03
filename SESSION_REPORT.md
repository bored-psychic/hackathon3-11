# Session report – Rural symptom triage app

**Date:** 3 Nov 2026  **Repo:** `bored-psychic/hackathon3-11` (branch `main`)

## 1. Summary

A plain chat placeholder grew into a mobile-first web app for rural Karnataka, in 6 languages (EN, ಕನ್ನಡ, हिन्दी, தமிழ், తెలుగు, മലയാളം). It has:

- **Home dashboard:** follow-up alerts, family cards, recent checks, helplines.
- **Check:** a symptom chatbot that typed or spoken input can use. It knows which family member the check is for and offers a 108 call or an SMS/WhatsApp alert on RED/AMBER.
- **Nearby:** hospitals, PHC/CHC/government centres, clinics and NGOs from OpenStreetMap, found by GPS or by village name.
- **Family:** per-person medical history and an emergency contact, stored only on the phone.

The backend got safer input/output handling, more red flags, profile-aware prompts, facility-search endpoints and a fix for an API-key leak in the logs.

| | State |
|---|---|
| Chat UI v1 (`templates/index.html`) | **Committed and pushed:** `619f19c frontend: chat UI` |
| Everything after that | **Not committed** (user asked not to commit or push yet) |

## 2. Work done, in order

### 2.1 Frontend chat UI (committed `619f19c`)
- One page, plain JS/CSS, no frameworks or CDN. Laid out for 360 px screens, with tap targets ≥ 44 px and a 16 px input font.
- Handles all 3 `/chat` response types from API.md:
  - **question:** shown as a bubble.
  - **final:** a coloured RED/AMBER/GREEN card with a big level word, reason and advice. RED and AMBER add a `tel:108` button. A "Start new check" button follows.
  - **error:** shown as a bubble, plus a friendly offline message ("…call 108 if urgent").
- A typing indicator, and Send stays disabled while a request is running so messages can't be sent twice.
- **Mic:** uses Web Speech with en-IN / kn-IN / hi-IN / ta-IN / te-IN / ml-IN, and hides itself if the browser has no support.
- **Listen button:** uses `speechSynthesis` and only appears when the device has a voice for that language.
- Server text is always inserted as plain text (`textContent`), never HTML.
- Followed API.md (all 6 languages, Kannada default) rather than the original brief (3 languages).

### 2.2 Testing and mic permission
- All the brief's checks passed: English/Hindi/Kannada RED cards, Hindi and Kannada page text, backend-down message, and only frontend files changed.
- **Mic popup couldn't be clicked:** the tab was under browser automation. Fix: open the page in a normal tab, or allow the mic in `chrome://settings/content/siteDetails?site=http%3A%2F%2Flocalhost%3A5001`. After that, voice input worked for the user.

### 2.3 Backend hardening (uncommitted)
- `/chat` accepts bad input without crashing: non-JSON bodies, broken `history`, unknown languages, and oversized messages (capped at 1000 chars and 20 history turns).
- **LLM output is cleaned up** before it reaches the page:
  - markdown fences around the JSON are removed;
  - an invalid level becomes AMBER;
  - unusable output becomes the normal `type:"error"` reply.
- The 2-follow-up limit is enforced: after 2 bot questions, the prompt says a final result is required.
- **New red flags:** blood in urine or stool, black stools and bleeding gums, in English, Hindi and Kannada.
  - A word-order-tolerant pattern catches phrasing like "bloody colour urine".
  - It ignores "blood test", "blood pressure" and "blood sugar", and doesn't match across commas.
- Added `tests/test_backend.py`: offline tests with the LLM faked.

### 2.4 Gemini setup
- The user supplied a key, saved to `.env` (gitignored).
- `gemini-2.5-flash` returned **404** for this key, so the model was switched to **`gemini-3.5-flash`** in `.env`, `.env.example` and the `app.py` default.
- Added up to 2 retries on 429/500/503, and the reply parser now skips "thought" parts.
- **Live demo script:** 15/16 passed. The one failure was a temporary 503 from Google; that sentence passed on a re-run.

### 2.5 Web app expansion (uncommitted)
**Frontend** (`templates/index.html` + `static/`):
| File | Purpose |
|---|---|
| `static/app.js` | App logic: tab switching, dashboard, chat, nearby search, family profiles, saving to the phone |
| `static/i18n.js` | All UI text in 6 languages (132 keys each, checked for consistency) |
| `static/app.css` | Mobile-first styles, wider screens capped at 760 px |
| `static/manifest.json`, `static/icon.svg` | "Add to Home Screen" support |

**Features:**
- **Dashboard:**
  - RED/AMBER alerts from the last 3 days, with a next step ("Go to hospital now" / "See a doctor by <date>") and a Done button.
  - Family cards showing conditions and last result.
  - Recent checks.
  - Helplines: 108, 112, 104, 14416.
- **Check:**
  - "Checking for" picker, which sends only medical facts (age, sex, pregnancy, conditions, allergies, medicines), never names or phone numbers.
  - Results are saved to that person's record.
  - RED/AMBER cards add "Find nearest hospital" and SMS/WhatsApp links to the emergency contact with a location link when known. The person still presses send.
- **Nearby:**
  - Searches by GPS or village name; when several places match, the user picks one.
  - Filters by Government / Hospitals / Clinics / NGOs, with distance, Call and Directions buttons.
  - The last list is kept for offline use.
- **Family:**
  - Emergency contact.
  - Member form: relation, age, sex, pregnancy (shown only for female), 7 common long-term conditions, other illnesses, allergies, medicines, notes.
  - Name is required, deleting needs a second tap, and there's a "delete all data" option.

**Backend** (`app.py`):
- `profile_summary()`: puts a cleaned one-line patient summary into the LLM prompt.
- `GET /places`:
  - Asks several Overpass servers at the same time, with **Nominatim as a fallback** (requests spaced 1 second apart, as its usage policy requires).
  - Labels each place as govt (PHC/CHC/sub-centre/government hospital), hospital, clinic or ngo.
  - Removes duplicates, sorts by distance and keeps at most 25 per type.
  - Widens the search from about 10–13 km to 30–33 km when results are sparse, and caches results for 6 hours per ~1 km area.
- `GET /geocode`: Nominatim search, India only, Karnataka preferred.
- **Security fix:** the Gemini key moved from the URL to the `x-goog-api-key` header. Before this, error logs contained the key.
- API.md updated with `profile`, `/places`, `/geocode` and the storage model.

## 3. Test results

| Test | Result |
|---|---|
| Backend unit tests (`python -m unittest tests.test_backend`) | **21/21 pass** |
| Live demo script (`tests/run_demo.py`) | 15/16 (1 temporary Google 503, passed on re-run) |
| Full headless Chrome run, 360 × 740 | No JS errors, no sideways scrolling, no buttons under 40 px |
| Family form: add, validate, edit (Tamil) | Pass |
| RED check for a family member, SMS/WhatsApp alert links, saved record, dashboard alert | Pass |
| Nearby by GPS (Mandya) | 60 places in 10 s; nearest govt: Government Hospital 0.4 km, ESI Hospital 0.5 km |
| Nearby, rural point near Pandavapura | 67 places (widened to 33 km), ~30 s |
| Village search "Pandavapura" | 5 matches to choose from |
| UI in kn / hi / ta | Rendered correctly, no layout overflow |
| Mic (real Chrome) | Works after allowing the mic (user confirmed) |
| Live Gemini reply using a family profile | **Not confirmed:** key hit Google's free-tier limit (429). Unit test confirms the profile reaches the prompt. |

## 4. Problems found and fixed
| Problem | Fix |
|---|---|
| API key written to server logs inside error URLs | Key sent in `x-goog-api-key` header |
| `gemini-2.5-flash` → 404 for new key | Switched to `gemini-3.5-flash` |
| Gemini overloaded (503) / rate-limited (429) | 2 retries; friendly error message after that |
| All public Overpass servers timing out | Ask them in parallel; Nominatim fallback |
| Far-away PHCs dropped by the overall 80-place limit | Limit per type (25) instead |
| "bloody colour urine" not flagged | Word-order-tolerant pattern + new keywords |
| "I gave blood yesterday, urine is fine" falsely flagged | Pattern doesn't cross punctuation; skips blood test/pressure/sugar |
| Kannada title cut off at 360 px | Title wraps to 2 lines |
| Chrome mic permission popup not clickable | It was in an automation-controlled tab; use a normal tab / site settings |

## 5. Open items and risks
1. **Commit the work:** everything after `619f19c` is uncommitted.
2. **Rotate the Gemini key:** it was pasted into the chat. The free tier also rate-limits quickly; plan a paid key or quota for demos.
3. **Clinical review of red flags:** the new bleeding keywords trigger an instant RED (e.g. black stools may be iron tablets). The existing keyword `fits` also matches "he fits in his shirt"; kept deliberately, since missing a real seizure is worse than a rare false RED.
4. **Native-speaker review** of all non-English text (`static/i18n.js`, the red-flag keyword lists).
5. **Facility data is incomplete:** OpenStreetMap coverage varies and almost no health NGOs are mapped near Mandya (0 found). The app says so and points to 104. A real launch needs official data (e.g. state PHC lists) and its own lookup service. Public Overpass/Nominatim aren't meant for heavy use.
6. **Privacy:** health data lives only in the browser on the phone. Clearing browser data or switching phones loses it. Location goes to OpenStreetMap services only when the user asks for nearby places.
7. **Phones on Wi-Fi:** the mic needs HTTPS or localhost, so on `http://<LAN-IP>:5001` voice input won't work.
8. **SMS links:** use the Android `sms:<n>?body=` format; iPhones may ignore the message body.

## 6. How to run and test
```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env                          # add GEMINI_API_KEY
python app.py                                   # http://localhost:5001
python -m unittest tests.test_backend -v        # offline, no key needed
python tests/run_demo.py                        # live, needs key
```

## 7. Environment changes on this PC
- Created `venv/` (gitignored), with backend dependencies and `websocket-client` for headless browser tests.
- Created `.env` (gitignored) with the Gemini key and model.
- Set a repo-local git author (`git config user.name/user.email`, this repo only).
- The Flask dev server is still running in the background on port 5001.
