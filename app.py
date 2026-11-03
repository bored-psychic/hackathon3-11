import json, os, re, time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from redflags import find_red_flag

load_dotenv()
app = Flask(__name__)

# Comma-separated list, tried in order. Free-tier quotas are per model, so when one model is
# rate-limited (HTTP 429) we fall through to the next instead of failing the user.
MODELS = [m.strip() for m in os.getenv(
    "GEMINI_MODEL", "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite").split(",") if m.strip()]
QUOTA_COOLDOWN_S = 15 * 60
EXHAUSTED = {}  # model -> time until which we skip it after a 429
LANG_NAMES = {"en": "English", "kn": "Kannada", "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "ml": "Malayalam"}

RED_MSG = {
    "en": "This may be an emergency. Call 108 now or go to the nearest hospital immediately.",
    "kn": "ಇದು ತುರ್ತು ಪರಿಸ್ಥಿತಿ ಆಗಿರಬಹುದು. ಈಗಲೇ 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ.",
    "hi": "यह आपातकाल हो सकता है। अभी 108 पर कॉल करें या नज़दीकी अस्पताल जाएँ।",
    "ta": "இது அவசரநிலையாக இருக்கலாம். உடனே 108 ஐ அழைக்கவும் அல்லது அருகிலுள்ள மருத்துவமனைக்குச் செல்லவும்.",
    "te": "ఇది అత్యవసర పరిస్థితి కావచ్చు. వెంటనే 108 కి కాల్ చేయండి లేదా సమీప ఆసుపత్రికి వెళ్లండి.",
    "ml": "ഇത് അടിയന്തര സാഹചര്യമാകാം. ഉടൻ 108 ൽ വിളിക്കുക അല്ലെങ്കിൽ അടുത്തുള്ള ആശുപത്രിയിലേക്ക് പോകുക.",
}
ERR_MSG = {
    "en": "Sorry, something went wrong. If this is urgent, call 108.",
    "kn": "ಕ್ಷಮಿಸಿ, ಏನೋ ತಪ್ಪಾಗಿದೆ. ತುರ್ತು ಇದ್ದರೆ 108 ಗೆ ಕರೆ ಮಾಡಿ.",
    "hi": "माफ़ कीजिए, कुछ गड़बड़ हुई। अगर जरूरी है तो 108 पर कॉल करें।",
    "ta": "மன்னிக்கவும், ஏதோ தவறு நடந்துவிட்டது. அவசரம் என்றால் 108 ஐ அழைக்கவும்.",
    "te": "క్షమించండి, ఏదో తప్పు జరిగింది. అత్యవసరమైతే 108 కి కాల్ చేయండి.",
    "ml": "ക്ഷമിക്കണം, എന്തോ പിശക് സംഭവിച്ചു. അടിയന്തരമാണെങ്കിൽ 108 ൽ വിളിക്കുക.",
}

SYSTEM_PROMPT = """You are a symptom triage assistant for people in rural Karnataka, India. You are NOT a doctor.
Assume the user is in Karnataka. Next steps must use Karnataka's public system: ambulance 108, general emergency 112,
nearest Primary Health Centre (PHC), Community Health Centre (CHC), taluk or district government hospital.
Keep in mind illnesses common in Karnataka (dengue, malaria, chikungunya, diarrhoea/dehydration, heat illness, snakebite).
Never recommend specific medicines or doses.
Reply ONLY in {lang}. Use simple, short words.
Each turn do exactly ONE of:
1) Ask ONE short follow-up question (max 2 follow-ups in total), or
2) Give a final triage.
Triage levels: RED = go to hospital / call 108 now; AMBER = see a doctor/PHC within 24-48h;
GREEN = home care, watch for worsening.
When unsure between two levels, choose the more serious one.
Output STRICT JSON only:
{{"type":"question"|"final","reply":"<text in {lang}>","level":"RED"|"AMBER"|"GREEN"|null,
"reason":"<1 sentence in {lang}, final only>","advice":"<1-3 short steps in {lang}, final only>",
"symptoms_en":["<each symptom the user has, in English>"]}}"""


def profile_summary(p):
    """One-line patient summary from the optional `profile` the frontend sends (no names)."""
    if not isinstance(p, dict):
        return ""
    def txt(k, n=200):
        v = p.get(k)
        return v.strip()[:n] if isinstance(v, str) else ""
    bits = []
    age = p.get("age")
    if isinstance(age, (int, float)) and 0 <= age <= 120:
        bits.append(f"age {int(age)} years")
    if p.get("sex") in ("male", "female", "other"):
        bits.append(f"sex {p['sex']}")
    if p.get("pregnant") is True:
        bits.append("currently pregnant")
    conds = p.get("conditions")
    if isinstance(conds, list):
        conds = [c.strip()[:60] for c in conds if isinstance(c, str) and c.strip()][:12]
        if conds:
            bits.append("long-term conditions: " + ", ".join(conds))
    for key, label in (("allergies", "allergies"), ("medicines", "regular medicines")):
        if txt(key):
            bits.append(f"{label}: {txt(key)}")
    return "; ".join(bits)


def post_gemini(key, body):
    """POST to the first model that answers. 429 (quota) -> skip that model for a while and try the next;
    500/503 (overloaded) -> one short retry on the same model."""
    now, last = time.time(), None
    candidates = [m for m in MODELS if EXHAUSTED.get(m, 0) <= now] or MODELS  # all limited: try anyway
    for model in candidates:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(2):
            # key in a header (not the URL) so it never shows up in error logs
            r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=25)
            if r.status_code in (500, 503) and attempt == 0:
                time.sleep(1)
                continue
            break
        if r.status_code == 429:
            EXHAUSTED[model] = time.time() + QUOTA_COOLDOWN_S
            app.logger.warning("Gemini quota hit for %s, trying next model", model)
            last = r
            continue
        if r.status_code in (500, 503):
            last = r
            continue
        r.raise_for_status()
        return r
    last.raise_for_status()
    raise RuntimeError("no Gemini model available")


def call_llm(history, message, lang, force_final=False, profile=""):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    contents = []
    for h in history[-10:]:
        role = "user" if h.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h.get("text", "")}]})
    contents.append({"role": "user", "parts": [{"text": message}]})
    system = SYSTEM_PROMPT.format(lang=LANG_NAMES[lang])
    if profile:
        system += ("\nAbout the patient (from their saved family profile, may be incomplete): " + profile +
                   ".\nUse this when choosing the level: older age, young children, pregnancy, diabetes, heart, "
                   "lung or kidney disease raise the risk. Do not ask again for facts given here.")
    if force_final:
        system += "\nYou have already asked the maximum number of follow-up questions. You MUST give a final triage now."
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    r = post_gemini(key, body)
    parts = r.json()["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)  # some models wrap JSON in fences
    return json.loads(text)


MAX_MSG_LEN = 1000
MAX_HISTORY = 20
MAX_FOLLOWUPS = 2


def clean_history(raw):
    """Keep only well-formed {role, text} turns; drop anything else the client sent."""
    if not isinstance(raw, list):
        return []
    out = []
    for h in raw[-MAX_HISTORY:]:
        if isinstance(h, dict) and h.get("role") in ("user", "bot") and isinstance(h.get("text"), str):
            out.append({"role": h["role"], "text": h["text"][:MAX_MSG_LEN]})
    return out


def normalize(out, lang):
    """Force the LLM reply into one of the API.md shapes, or None if unusable."""
    if not isinstance(out, dict):
        return None
    symptoms = out.get("symptoms_en")
    symptoms = [str(x) for x in symptoms] if isinstance(symptoms, list) else []
    reply = str(out.get("reply") or "").strip()
    if out.get("type") == "question" and reply:
        return {"type": "question", "reply": reply, "level": None, "symptoms_en": symptoms}
    level = str(out.get("level") or "").upper()
    if out.get("type") == "final" or level in ("RED", "AMBER", "GREEN"):
        if level not in ("RED", "AMBER", "GREEN"):
            level = "AMBER"  # unsure -> the more serious non-emergency level
        reason = str(out.get("reason") or "").strip() or reply
        advice = str(out.get("advice") or "").strip() or reply
        if not (reply or reason or advice):
            return None
        return {"type": "final", "level": level, "reply": reply or reason,
                "reason": reason, "advice": advice, "symptoms_en": symptoms}
    return None


def red_response(lang, kw):
    return {"type": "final", "level": "RED", "reply": RED_MSG[lang],
            "reason": RED_MSG[lang], "advice": RED_MSG[lang], "matched": kw}


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/chat")
def chat():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    message = data.get("message")
    message = message.strip()[:MAX_MSG_LEN] if isinstance(message, str) else ""
    lang = data.get("language", "en")
    lang = lang if lang in LANG_NAMES else "en"
    history = clean_history(data.get("history"))
    if not message:
        return jsonify({"error": "empty"}), 400

    # Step 3: red-flag scan on this message + earlier user turns, no LLM
    user_text = " ".join([h.get("text", "") for h in history if h.get("role") == "user"] + [message])
    kw = find_red_flag(user_text)
    if kw:
        return jsonify(red_response(lang, kw))

    # Step 4: LLM
    try:
        asked = sum(1 for h in history if h["role"] == "bot")
        out = normalize(call_llm(history, message, lang, force_final=asked >= MAX_FOLLOWUPS,
                                 profile=profile_summary(data.get("profile"))), lang)
    except Exception as e:
        app.logger.error("LLM failed: %s", e)
        out = None
    if out is None:
        return jsonify({"type": "error", "reply": ERR_MSG[lang]})

    # Step 5: safety override on LLM's English symptom list
    kw = find_red_flag(" ".join(out.get("symptoms_en") or []))
    if kw and out.get("level") != "RED":
        return jsonify(red_response(lang, kw))
    return jsonify(out)


# ---------------- Nearby health facilities (OpenStreetMap) ----------------
OSM_HEADERS = {"User-Agent": "rural-triage-hackathon/0.1 (+https://github.com/bored-psychic/hackathon3-11)"}
OVERPASS_URLS = [  # public mirrors; queried in parallel, first good answer wins
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_BUDGET_S = 12  # then fall back to Nominatim
PLACES_CACHE = {}  # (lat2, lon2) -> (timestamp, payload)
CACHE_SECONDS = 6 * 3600

GOVT_RE = re.compile(r"\b(phc|chc|primary health|community health|taluk|taluka|district hospital|government|govt|"
                     r"general hospital|esi|esic|urban health|sub[ -]?cent(?:re|er)|health and wellness|"
                     r"ayushman arogya|arogya kendra|public health)\b", re.I)
NGO_HEALTH_RE = re.compile(r"health|medical|hospital|clinic|care|arogya|aarogya|seva|cancer|eye|blind|deaf|"
                           r"disab|hiv|\btb\b|mental|nutrition|mother|maternal|child", re.I)


def haversine_km(lat1, lon1, lat2, lon2):
    from math import asin, cos, radians, sin, sqrt
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def classify_place(tags):
    """Return (kind, sub) or None. kind: govt | hospital | clinic | ngo."""
    text = " ".join(tags.get(k, "") for k in ("name", "name:en", "operator", "description"))
    op_type = tags.get("operator:type", "")
    is_ngo_office = tags.get("office") == "ngo" or tags.get("amenity") == "social_facility"
    if is_ngo_office:
        return ("ngo", "ngo") if (tags.get("healthcare") or NGO_HEALTH_RE.search(text)) else None
    if op_type in ("ngo", "charitable", "community", "religious", "non_profit"):
        return ("ngo", "charity_hospital" if tags.get("amenity") == "hospital" else "ngo")
    if op_type in ("government", "public") or GOVT_RE.search(text):
        low = text.lower()
        if re.search(r"\bchc\b|community health", low):
            return ("govt", "chc")
        if re.search(r"\bphc\b|primary health", low):
            return ("govt", "phc")
        if re.search(r"sub[ -]?cent", low):
            return ("govt", "subcentre")
        if tags.get("amenity") == "hospital" or tags.get("healthcare") == "hospital" or "hospital" in low:
            return ("govt", "govt_hospital")
        return ("govt", "govt_centre")
    if tags.get("amenity") == "hospital" or tags.get("healthcare") == "hospital":
        return ("hospital", "hospital")
    return ("clinic", "clinic")


def overpass(lat, lon, radius_m):
    q = f"""[out:json][timeout:25];
(
  nwr(around:{radius_m},{lat},{lon})[amenity~"^(hospital|clinic|doctors)$"];
  nwr(around:{radius_m},{lat},{lon})[healthcare~"^(hospital|clinic|centre|doctor)$"];
  nwr(around:{radius_m},{lat},{lon})[office=ngo];
  nwr(around:{radius_m},{lat},{lon})[amenity=social_facility];
);
out center tags 400;"""
    def ask(url):
        r = requests.post(url, data={"data": q}, headers=OSM_HEADERS, timeout=35)
        r.raise_for_status()
        return r.json()["elements"]

    pool = ThreadPoolExecutor(max_workers=len(OVERPASS_URLS))
    futures = [pool.submit(ask, u) for u in OVERPASS_URLS]
    errors = []
    try:
        for f in as_completed(futures, timeout=OVERPASS_BUDGET_S):
            try:
                return f.result()
            except Exception as e:  # this mirror failed; wait for the others
                errors.append(str(e)[:120])
    except TimeoutError:
        errors.append("all mirrors timed out")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    raise RuntimeError("overpass failed: " + " | ".join(errors))


NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
NOMINATIM_QUERIES = ["hospital", "health centre", "clinic", "ngo"]


def nominatim_places(lat, lon, half_deg):
    """Fallback when Overpass is down: category searches inside a box. Nominatim allows max 1 request/second."""
    elements = []
    for i, q in enumerate(NOMINATIM_QUERIES):
        if i:
            time.sleep(1.1)
        r = requests.get(NOMINATIM_SEARCH, headers=OSM_HEADERS, timeout=15, params={
            "q": q, "format": "jsonv2", "limit": 40, "bounded": 1, "extratags": 1, "addressdetails": 1,
            "viewbox": f"{lon - half_deg},{lat + half_deg},{lon + half_deg},{lat - half_deg}"})
        r.raise_for_status()
        for x in r.json():
            tags = dict(x.get("extratags") or {})
            tags[x.get("category", "")] = x.get("type", "")
            if x.get("name"):
                tags.setdefault("name", x["name"])
            a = x.get("address") or {}
            parts = [a.get(k) for k in ("road", "village", "suburb", "town", "city", "county") if a.get(k)]
            tags.setdefault("addr:full", ", ".join(dict.fromkeys(parts)))
            if not (tags.get("amenity") in ("hospital", "clinic", "doctors") or tags.get("healthcare")
                    or tags.get("office") == "ngo" or tags.get("amenity") == "social_facility"):
                continue  # text match on something that isn't a health facility
            elements.append({"lat": float(x["lat"]), "lon": float(x["lon"]), "tags": tags})
    return elements


def find_places(lat, lon):
    """Run Overpass (complete data, often overloaded) and Nominatim (fast) side by side.
    Prefer Overpass if it answered by the time Nominatim is done; widen the area if few results."""
    for (radius_m, half_deg, km) in ((10000, 0.12, 13), (30000, 0.3, 33)):
        bg = ThreadPoolExecutor(max_workers=1)
        op = bg.submit(overpass, lat, lon, radius_m)
        try:
            nom = build_places(nominatim_places(lat, lon, half_deg), lat, lon)
        except Exception as e:
            app.logger.warning("nominatim failed: %s", str(e)[:200])
            nom = None
        try:
            # if Nominatim failed, give Overpass its full budget; otherwise only take it if already done
            found = build_places(op.result(timeout=OVERPASS_BUDGET_S if nom is None else 0.5), lat, lon)
        except Exception as e:
            app.logger.warning("overpass unavailable: %s", str(e)[:200])
            found = nom
        finally:
            bg.shutdown(wait=False, cancel_futures=True)
        if found is None:
            raise RuntimeError("no place source available")
        if len(found) >= 8:
            break
    return found, km


def build_places(elements, lat, lon):
    seen, out = set(), []
    for el in elements:
        tags = el.get("tags") or {}
        name = (tags.get("name:en") or tags.get("name") or "").strip()
        plat = el.get("lat", (el.get("center") or {}).get("lat"))
        plon = el.get("lon", (el.get("center") or {}).get("lon"))
        if not name or plat is None or plon is None:
            continue
        cls = classify_place(tags)
        key = (name.lower(), round(plat, 3), round(plon, 3))
        if not cls or key in seen:
            continue
        seen.add(key)
        addr = tags.get("addr:full") or ", ".join(
            tags[k] for k in ("addr:street", "addr:village", "addr:suburb", "addr:city", "addr:district") if tags.get(k))
        out.append({
            "name": name, "local_name": tags.get("name") if tags.get("name") != name else "",
            "kind": cls[0], "sub": cls[1], "lat": plat, "lon": plon,
            "distance_km": round(haversine_km(lat, lon, plat, plon), 1),
            "phone": tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile") or "",
            "address": addr, "emergency": tags.get("emergency") == "yes",
            "opening_hours": tags.get("opening_hours", ""),
        })
    out.sort(key=lambda p: p["distance_km"])
    # cap each kind separately so far-away PHCs aren't pushed out by many nearby clinics
    counts, capped = {}, []
    for p in out:
        counts[p["kind"]] = counts.get(p["kind"], 0) + 1
        if counts[p["kind"]] <= 25:
            capped.append(p)
    return capped


@app.get("/places")
def places():
    try:
        lat, lon = float(request.args["lat"]), float(request.args["lon"])
        assert -90 <= lat <= 90 and -180 <= lon <= 180
    except Exception:
        return jsonify({"error": "bad location"}), 400
    key = (round(lat, 2), round(lon, 2))
    hit = PLACES_CACHE.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return jsonify(hit[1])
    try:
        found, radius_km = find_places(lat, lon)
    except Exception as e:
        app.logger.error("places failed: %s", e)
        return jsonify({"error": "unavailable"}), 502
    payload = {"places": found, "radius_km": radius_km, "source": "OpenStreetMap"}
    PLACES_CACHE[key] = (time.time(), payload)
    return jsonify(payload)


@app.get("/geocode")
def geocode():
    q = (request.args.get("q") or "").strip()[:120]
    if not q:
        return jsonify({"error": "empty"}), 400
    lang = request.args.get("lang", "en")
    try:
        r = requests.get(NOMINATIM_SEARCH, headers=OSM_HEADERS, timeout=15, params={
            "q": q, "format": "jsonv2", "limit": 5, "countrycodes": "in",
            "viewbox": "74.0,18.5,78.6,11.5",  # prefer Karnataka, but don't exclude elsewhere
            "accept-language": lang if lang in LANG_NAMES else "en"})
        r.raise_for_status()
        res = [{"name": x.get("display_name", ""), "lat": float(x["lat"]), "lon": float(x["lon"])} for x in r.json()]
    except Exception as e:
        app.logger.error("geocode failed: %s", e)
        return jsonify({"error": "unavailable"}), 502
    return jsonify({"results": res})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
