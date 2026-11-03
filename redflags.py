"""Hard-coded emergency check. Runs BEFORE the LLM and again on the LLM output.
Keywords are lowercase substrings (ASCII keywords match whole words only).
NOTE: have native speakers review every non-English list."""
import re

RED_FLAGS = {
    "en": [
        "chest pain", "cant breathe", "can't breathe", "cannot breathe",
        "difficulty breathing", "trouble breathing", "unconscious", "fainted",
        "seizure", "fits", "heavy bleeding", "bleeding a lot", "snake bite",
        "snakebite", "poison", "suicide", "want to die", "face drooping",
        "slurred speech", "paralysis", "baby not breathing", "severe burn",
        "vomiting blood", "coughing blood",
        # bleeding signs (dengue warning signs in Karnataka) - NEEDS CLINICAL REVIEW
        "blood in urine", "bloody urine", "hematuria", "haematuria",
        "blood in stool", "bloody stool", "black stool", "black stools",
        "bleeding gums", "gums bleeding", "bleeding from gums",
    ],
    "hi": [
        "सीने में दर्द", "छाती में दर्द", "सांस नहीं", "सांस लेने में तकलीफ",
        "साँस नहीं", "साँस लेने में तकलीफ", "बेहोश", "दौरा", "मिर्गी",
        "बहुत खून", "खून बह", "सांप ने काटा", "साँप ने काटा", "ज़हर", "जहर",
        "आत्महत्या", "मरना चाहता", "लकवा", "खून की उल्टी", "खून की खांसी",
        "पेशाब में खून", "मल में खून", "मसूड़ों से खून",
    ],
    "kn": [
        "ಎದೆ ನೋವು", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಉಸಿರಾಡಲು ಆಗುತ್ತಿಲ್ಲ", "ಉಸಿರು ಕಟ್ಟ",
        "ಪ್ರಜ್ಞೆ ತಪ್ಪ", "ಪ್ರಜ್ಞೆಯಿಲ್ಲ", "ಫಿಟ್ಸ್", "ಅಪಸ್ಮಾರ", "ತೀವ್ರ ರಕ್ತಸ್ರಾವ",
        "ಬಹಳ ರಕ್ತ", "ಹಾವು ಕಚ್ಚ", "ವಿಷ ಕುಡಿ", "ವಿಷ ಸೇವ", "ವಿಷಪ್ರಾಶನ", "ವಿಷ ಹಾಕ",
        "ಆತ್ಮಹತ್ಯೆ", "ಪಾರ್ಶ್ವವಾಯು", "ರಕ್ತ ವಾಂತಿ",
        "ಮೂತ್ರದಲ್ಲಿ ರಕ್ತ", "ಮಲದಲ್ಲಿ ರಕ್ತ", "ಒಸಡಿನಿಂದ ರಕ್ತ",
    ],
    "ta": [
        "நெஞ்சு வலி", "மார்பு வலி", "மூச்சு விட முடியவில்லை", "மூச்சுத் திணறல்",
        "மயங்கி", "வலிப்பு", "அதிக ரத்தப்போக்கு", "அதிக இரத்தப்போக்கு",
        "பாம்பு கடி", "பாம்பு கடித்த", "விஷம்", "தற்கொலை", "பக்கவாதம்",
        "ரத்த வாந்தி", "இரத்த வாந்தி",
    ],
    "te": [
        "ఛాతీ నొప్పి", "ఊపిరి ఆడ", "ఊపిరి తీసుకోలేక", "స్పృహ తప్పి", "మూర్ఛ",
        "తీవ్ర రక్తస్రావం", "పాము కాటు", "పాము కరిచ", "విషం", "ఆత్మహత్య",
        "పక్షవాతం", "రక్తం వాంతి",
    ],
    "ml": [
        "നെഞ്ചുവേദന", "നെഞ്ച് വേദന", "ശ്വാസം മുട്ട", "ശ്വാസം എടുക്കാൻ",
        "ബോധം പോയ", "അപസ്മാരം", "അമിത രക്തസ്രാവം", "പാമ്പ് കടി", "പാമ്പ് കടിച്ച",
        "വിഷം", "ആത്മഹത്യ", "പക്ഷാഘാതം", "രക്തം ഛർദ്ദ",
    ],
}

ALL_FLAGS = [k for lst in RED_FLAGS.values() for k in lst]
_ASCII_RE = {k: re.compile(r"\b" + re.escape(k) + r"\b") for k in ALL_FLAGS if k.isascii()}

# Free-word-order English phrases, e.g. "bloody colour urine", "blood coming in my pee".
_BLEED = r"\bblood(?:y)?\b(?!\s+(?:pressure|test|tests|sugar|report|group|donation|bank))"
_BODY = r"\b(?:urine|pee|stools?|motions?|potty)\b(?!\s+(?:test|tests|report))"
_GAP = r"[^\w.,;!?]+"                  # spaces etc., but never across a comma or full stop
_NEAR = r"(?:" + _GAP + r"\w+){0,3}?" + _GAP  # up to 3 words in between
PATTERNS = {
    "blood in urine/stool": re.compile(_BLEED + _NEAR + _BODY + "|" + _BODY + _NEAR + _BLEED),
}


def find_red_flag(text: str):
    """Return the first matching keyword, or None. Checks all languages."""
    t = (text or "").lower().replace("’", "'")
    for kw in ALL_FLAGS:
        if kw in _ASCII_RE:
            if _ASCII_RE[kw].search(t):
                return kw
        elif kw in t:
            return kw
    for name, rx in PATTERNS.items():
        if rx.search(t):
            return name
    return None
