import json, os
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from redflags import find_red_flag

load_dotenv()
app = Flask(__name__)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LANG_NAMES = {"en": "English", "kn": "Kannada", "hi": "Hindi"}

RED_MSG = {
    "en": "This may be an emergency. Call 108 now or go to the nearest hospital immediately.",
    "kn": "ಇದು ತುರ್ತು ಪರಿಸ್ಥಿತಿ ಆಗಿರಬಹುದು. ಈಗಲೇ 108 ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ.",
    "hi": "यह आपातकाल हो सकता है। अभी 108 पर कॉल करें या नज़दीकी अस्पताल जाएँ।",
}
ERR_MSG = {
    "en": "Sorry, something went wrong. If this is urgent, call 108.",
    "kn": "ಕ್ಷಮಿಸಿ, ಏನೋ ತಪ್ಪಾಗಿದೆ. ತುರ್ತು ಇದ್ದರೆ 108 ಗೆ ಕರೆ ಮಾಡಿ.",
    "hi": "माफ़ कीजिए, कुछ गड़बड़ हुई। अगर जरूरी है तो 108 पर कॉल करें।",
}

SYSTEM_PROMPT = """You are a symptom triage assistant for rural India. You are NOT a doctor.
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


def call_llm(history, message, lang):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    contents = []
    for h in history[-10:]:
        role = "user" if h.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h.get("text", "")}]})
    contents.append({"role": "user", "parts": [{"text": message}]})
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT.format(lang=LANG_NAMES[lang])}]},
        "contents": contents,
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    r = requests.post(url, params={"key": key}, json=body, timeout=25)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def red_response(lang, kw):
    return {"type": "final", "level": "RED", "reply": RED_MSG[lang],
            "reason": RED_MSG[lang], "advice": RED_MSG[lang], "matched": kw}


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

    # Step 4: LLM
    try:
        out = call_llm(history, message, lang)
    except Exception as e:
        app.logger.error("LLM failed: %s", e)
        return jsonify({"type": "error", "reply": ERR_MSG[lang]})

    # Step 5: safety override on LLM's English symptom list
    kw = find_red_flag(" ".join(out.get("symptoms_en") or []))
    if kw and out.get("level") != "RED":
        return jsonify(red_response(lang, kw))
    return jsonify(out)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
