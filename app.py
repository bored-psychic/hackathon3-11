import json, os, re
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from redflags import find_red_flag

load_dotenv(override=True)  # .env always wins over stale shell vars
app = Flask(__name__)

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
LANG_NAMES = {"en": "English", "kn": "Kannada", "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "ml": "Malayalam"}
LEVELS = ("RED", "AMBER", "GREEN")
MAX_FOLLOW_UPS = 2
MAX_MESSAGE_CHARS = 1000

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

FALLBACK_MSG = {
    "en": "I could not decide safely. Please visit your nearest PHC within 24 hours. If it gets worse, call 108.",
    "kn": "ಸುರಕ್ಷಿತವಾಗಿ ನಿರ್ಧರಿಸಲು ನನಗೆ ಆಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು 24 ಗಂಟೆಗಳ ಒಳಗೆ ಹತ್ತಿರದ ಪ್ರಾಥಮಿಕ ಆರೋಗ್ಯ ಕೇಂದ್ರಕ್ಕೆ (PHC) ಹೋಗಿ. ಹೆಚ್ಚಾದರೆ 108 ಗೆ ಕರೆ ಮಾಡಿ.",  # needs native-speaker review
    "hi": "सुरक्षित रूप से तय नहीं हो पाया। कृपया 24 घंटे के भीतर नज़दीकी प्राथमिक स्वास्थ्य केंद्र (PHC) जाएँ। हालत बिगड़े तो 108 पर कॉल करें।",  # needs native-speaker review
    "ta": "என்னால் பாதுகாப்பாக முடிவு செய்ய முடியவில்லை. தயவுசெய்து 24 மணி நேரத்திற்குள் அருகிலுள்ள ஆரம்ப சுகாதார நிலையத்திற்கு (PHC) செல்லவும். நிலை மோசமானால் 108 ஐ அழைக்கவும்.",  # needs native-speaker review
    "te": "నేను సురక్షితంగా నిర్ణయించలేకపోయాను. దయచేసి 24 గంటల్లోపు సమీప ప్రాథమిక ఆరోగ్య కేంద్రానికి (PHC) వెళ్లండి. పరిస్థితి తీవ్రమైతే 108 కి కాల్ చేయండి.",  # needs native-speaker review
    "ml": "എനിക്ക് സുരക്ഷിതമായി തീരുമാനിക്കാൻ കഴിഞ്ഞില്ല. ദയവായി 24 മണിക്കൂറിനുള്ളിൽ അടുത്തുള്ള പ്രാഥമികാരോഗ്യ കേന്ദ്രത്തിൽ (PHC) പോകുക. സ്ഥിതി മോശമായാൽ 108 ൽ വിളിക്കുക.",  # needs native-speaker review
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


def strip_fences(text):
    """Remove a ```json ... ``` wrapper, if the whole reply is wrapped in one."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def call_llm(history, message, lang, force_final=False):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    contents = []
    for h in history[-10:]:
        role = "user" if h.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h.get("text", "")}]})
    contents.append({"role": "user", "parts": [{"text": message}]})
    system = SYSTEM_PROMPT.format(lang=LANG_NAMES[lang])
    if force_final:
        system += "\nYou must now return type final."
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    r = requests.post(url, params={"key": key}, json=body, timeout=25)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(strip_fences(text))


def as_text(value):
    """Return a string, or "" for anything else. A list of strings is joined, because
    the prompt asks for "1-3 short steps" and models often send those as a list."""
    if isinstance(value, list):
        value = " ".join(v for v in value if isinstance(v, str))
    return value.strip() if isinstance(value, str) else ""


def normalize_llm(out, lang):
    """Force any LLM result into one of the 3 response shapes in API.md."""
    error = {"type": "error", "reply": ERR_MSG[lang]}
    if not isinstance(out, dict):
        return error

    reply = out.get("reply")
    reply = reply.strip() if isinstance(reply, str) else ""
    level = out.get("level")
    level = level.strip().upper() if isinstance(level, str) else ""
    symptoms = out.get("symptoms_en")
    if not (isinstance(symptoms, list) and all(isinstance(s, str) for s in symptoms)):
        symptoms = []

    kind = out.get("type")
    if kind not in ("question", "final"):
        kind = "final" if level in LEVELS else "question" if reply else "error"

    if kind == "final":
        return {"type": "final", "level": level if level in LEVELS else "AMBER", "reply": reply,
                "reason": as_text(out.get("reason")), "advice": as_text(out.get("advice")),
                "symptoms_en": symptoms}
    if kind == "question" and reply:
        return {"type": "question", "reply": reply, "level": None, "symptoms_en": symptoms}
    return error


def raw_symptom_text(out):
    """All symptom text in the raw LLM result, however malformed. The safety override reads
    this, not the normalised copy, so a broken reply can never hide a red-flag symptom."""
    if not isinstance(out, dict):
        return ""
    return as_text(out.get("symptoms_en"))


def red_response(lang, kw):
    return {"type": "final", "level": "RED", "reply": RED_MSG[lang],
            "reason": RED_MSG[lang], "advice": RED_MSG[lang], "matched": kw}


def fallback_response(lang, symptoms):
    # reason stays empty so the card, which shows reason and advice, shows the message once
    return {"type": "final", "level": "AMBER", "reply": FALLBACK_MSG[lang],
            "reason": "", "advice": FALLBACK_MSG[lang], "symptoms_en": symptoms}


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    lang = data.get("language", "en")
    lang = lang if lang in LANG_NAMES else "en"
    history = data.get("history") or []
    if not message:
        return jsonify({"error": "empty"}), 400

    # Step 3: red-flag scan on this message + earlier user turns, no LLM
    user_text = " ".join([h.get("text", "") for h in history if h.get("role") == "user"] + [message])
    kw = find_red_flag(user_text)
    if kw:
        return jsonify(red_response(lang, kw))

    # Checked after the red-flag scan on purpose: a long message about an emergency is still RED
    if len(message) > MAX_MESSAGE_CHARS:
        return jsonify({"error": "too_long"}), 400

    # Step 4: LLM
    force_final = sum(1 for h in history if h.get("role") == "bot") >= MAX_FOLLOW_UPS
    try:
        out = call_llm(history, message, lang, force_final)
    except Exception as e:
        # never log str(e): requests errors include the URL, which contains the API key
        status = getattr(getattr(e, "response", None), "status_code", None)
        body = ""
        try:
            body = e.response.json().get("error", {}).get("message", "")[:200]
        except Exception:
            pass
        app.logger.error("LLM failed: %s status=%s %s", type(e).__name__, status, body)
        return jsonify({"type": "error", "reply": ERR_MSG[lang]})

    result = normalize_llm(out, lang)

    # Step 5: safety override on LLM's English symptom list, for every result type
    kw = find_red_flag(raw_symptom_text(out))
    if kw and result.get("level") != "RED":
        return jsonify(red_response(lang, kw))

    # Step 6: follow-up cap. Runs after the override so red-flag symptoms still win
    if force_final and result["type"] == "question":
        return jsonify(fallback_response(lang, result["symptoms_en"]))
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
