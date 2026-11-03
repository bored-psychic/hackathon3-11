"""Hard-coded emergency check. Runs BEFORE the LLM and again on the LLM output.
Keywords are matched against normalised text: lowercase, ’ becomes ', hyphens and underscores
become spaces, repeated whitespace collapses. ASCII keywords match whole words only; other
keywords match as substrings, so a stem like "ಹಾವು ಕಚ್ಚ" also matches its inflected forms.
Avoid bare words with an innocent second meaning: "fits" (shoe fits), "poison" (poison ivy),
"दौरा" (a doctor's visit).
A message is RED if ANY occurrence of ANY keyword is not denied. See _is_denied: the rule is narrow on
purpose, because a loose one hides real emergencies. When unsure, RED.
NOTE: have native speakers review every non-English list."""
import re
import unicodedata

RED_FLAGS = {
    "en": [
        "chest pain", "chest pains", "chest hurts", "chest hurting", "chest is hurting",
        "chest tightness", "tight chest", "chest feels tight", "chest pressure",
        "pain in chest", "pain in my chest", "pain in his chest", "pain in her chest", "pain in the chest",
        "heart attack", "cardiac arrest",
        "cant breathe", "can't breathe", "cannot breathe", "can not breathe",
        "cant breath", "can't breath", "cannot breath", "can not breath",
        "unable to breathe", "not able to breathe", "hard to breathe", "struggling to breathe",
        "difficulty breathing", "trouble breathing", "short of breath", "shortness of breath",
        "breathless", "breathlessness", "gasping", "choking",
        "not breathing", "isn't breathing", "isnt breathing", "stopped breathing", "baby not breathing",
        "turning blue", "lips are blue", "blue lips", "no pulse", "is dying", "am dying",
        "drowned", "drowning", "electric shock", "road accident",
        "unconscious", "not conscious", "lost consciousness", "fainted", "passed out", "blacked out",
        "collapsed", "unresponsive", "not responding", "not waking", "isn't waking", "isnt waking",
        "won't wake up", "wont wake up",
        "seizure", "seizures", "has fits", "having fits", "had fits", "had a fit", "having a fit",
        "he is fitting", "she is fitting",
        "convulsion", "convulsions", "convulsing",
        "heavy bleeding", "bleeding heavily", "bleeding a lot", "bleeding badly", "bleeding profusely",
        "bleeding won't stop", "bleeding wont stop", "bleeding will not stop",
        "won't stop bleeding", "wont stop bleeding", "bleeding is not stopping", "bleeding not stopping",
        "blood is not stopping", "blood not stopping", "lot of blood", "lots of blood",
        "vomiting blood", "vomited blood", "coughing blood", "coughing up blood",
        "snake bite", "snake bites", "snakebite", "snake bit", "snake bitten", "snake has bitten",
        "bitten by a snake", "bitten by snake", "bit by a snake", "bit by snake", "snake just bit",
        "cobra bit", "cobra bite", "bitten by a cobra",
        "drank poison", "ate poison", "swallowed poison", "took poison", "consumed poison",
        "ingested poison", "poison ingestion", "poisoned", "rat poison", "pesticide", "insecticide",
        "overdose", "too many tablets", "too many pills",
        "suicide", "suicidal", "want to die", "wants to die", "kill myself", "kill himself", "kill herself",
        "end my life", "take my own life", "self harm", "end it all",
        "don't want to live", "dont want to live", "do not want to live",
        "stroke", "face drooping", "face is drooping", "slurred speech", "speech is slurred",
        "paralysis", "paralysed", "paralyzed", "one side of his body", "one side of her body", "one side of my body",
        "severe burn", "severe burns", "serious burn", "serious burns", "badly burned", "badly burnt",
        "burned badly", "burnt badly",
    ],
    "hi": [
        "सीने में दर्द", "छाती में दर्द", "सांस लेने में तकलीफ", "साँस लेने में तकलीफ", "बेहोश", "मिर्गी",
        "बहुत खून", "खून बह", "आत्महत्या", "मरना चाहता", "लकवा", "खून की उल्टी", "खून की खांसी",
        "दिल का दौरा", "दौरा पड़", "दौरे पड़", "दौरा पड", "दौरे पड", "हार्ट अटैक", "स्ट्रोक",  # needs native-speaker review
        "सांस नहीं आ", "सांस नहीं ले", "सांस नहीं चल", "सांस फूल रही", "सांस रुक",  # needs native-speaker review
        "साँस नहीं आ", "साँस नहीं ले", "साँस नहीं चल", "साँस फूल रही", "साँस रुक",  # needs native-speaker review
        "दम घुट", "सांस लेने में दिक्कत", "साँस लेने में दिक्कत", "होश नहीं आ",  # needs native-speaker review
        "सांप ने काट", "साँप ने काट", "सांप काट", "साँप काट", "सांप ने डस", "साँप ने डस",  # needs native-speaker review
        "सीने में तेज दर्द", "छाती में तेज दर्द", "सीने में बहुत दर्द", "छाती में बहुत दर्द", "दिल में दर्द",  # needs native-speaker review
        "ज़हर खा", "ज़हर पी", "ज़हर ले", "जहर खा", "जहर पी", "जहर ले",  # needs native-speaker review
        "कीटनाशक", "कीड़े मार", "कीड़ेमार", "मरना चाहती", "खुदकुशी",  # needs native-speaker review
        "खून बंद नहीं", "खून रुक नहीं", "बहना बंद नहीं",  # needs native-speaker review
    ],
    "kn": [
        "ಎದೆ ನೋವು", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಉಸಿರಾಡಲು ಆಗುತ್ತಿಲ್ಲ", "ಉಸಿರು ಕಟ್ಟ",
        "ಪ್ರಜ್ಞೆ ತಪ್ಪ", "ಪ್ರಜ್ಞೆಯಿಲ್ಲ", "ಫಿಟ್ಸ್", "ಅಪಸ್ಮಾರ", "ತೀವ್ರ ರಕ್ತಸ್ರಾವ",
        "ಬಹಳ ರಕ್ತ", "ಹಾವು ಕಚ್ಚ", "ವಿಷ ಕುಡಿ", "ವಿಷ ಸೇವ", "ವಿಷಪ್ರಾಶನ", "ವಿಷ ಹಾಕ",
        "ಆತ್ಮಹತ್ಯೆ", "ಪಾರ್ಶ್ವವಾಯು", "ರಕ್ತ ವಾಂತಿ",
        "ಎದೆನೋವು", "ಹೃದಯಾಘಾತ", "ಹಾರ್ಟ್ ಅಟ್ಯಾಕ್", "ಸ್ಟ್ರೋಕ್", "ಹಾವು ಕಡಿ", "ಹಾವಿನ ಕಡಿತ",  # needs native-speaker review
        "ಕೀಟನಾಶಕ", "ಕ್ರಿಮಿನಾಶಕ", "ಸಾಯಬೇಕು", "ಮೂರ್ಛೆ", "ರಕ್ತ ನಿಲ್ಲುತ್ತಿಲ್ಲ",  # needs native-speaker review
        "ಪ್ರಜ್ಞೆ ಇಲ್ಲ", "ಉಸಿರಾಟ ಇಲ್ಲ", "ಉಸಿರಾಡಲು ಆಗುವುದಿಲ್ಲ", "ಉಸಿರಾಡಲು ಕಷ್ಟ",  # needs native-speaker review
    ],
    "ta": [
        "நெஞ்சு வலி", "மார்பு வலி", "மூச்சு விட முடியவில்லை", "மூச்சுத் திணறல்",
        "மயங்கி", "வலிப்பு", "அதிக ரத்தப்போக்கு", "அதிக இரத்தப்போக்கு",
        "பாம்பு கடி", "பாம்பு கடித்த", "விஷம்", "தற்கொலை", "பக்கவாதம்",
        "ரத்த வாந்தி", "இரத்த வாந்தி",
        "நெஞ்சுவலி", "மார்புவலி", "மாரடைப்பு", "ஹார்ட் அட்டாக்", "ஸ்ட்ரோக்",  # needs native-speaker review
        "பூச்சிக்கொல்லி", "பூச்சி மருந்து", "சாக வேண்டும்",  # needs native-speaker review
        "மூச்சு திணறல்", "மூச்சு விட முடியல", "மூச்சு இல்லை", "நினைவு இல்லை",  # needs native-speaker review
        "ரத்தம் நிற்கவில்லை", "இரத்தம் நிற்கவில்லை",  # needs native-speaker review
    ],
    "te": [
        "ఛాతీ నొప్పి", "ఊపిరి ఆడ", "ఊపిరి తీసుకోలేక", "స్పృహ తప్పి", "మూర్ఛ",
        "తీవ్ర రక్తస్రావం", "పాము కాటు", "పాము కరిచ", "విషం", "ఆత్మహత్య",
        "పక్షవాతం", "రక్తం వాంతి",
        "ఛాతి నొప్పి", "గుండె నొప్పి", "గుండెపోటు", "గుండె పోటు", "హార్ట్ ఎటాక్", "స్ట్రోక్",  # needs native-speaker review
        "పురుగుల మందు", "పురుగు మందు", "క్రిమిసంహారక", "చనిపోవాలని",  # needs native-speaker review
        "ఊపిరి ఆడటం లేదు", "ఊపిరి ఆడడం లేదు", "ఊపిరి లేదు", "స్పృహ లేదు", "రక్తం ఆగడం లేదు",  # needs native-speaker review
    ],
    "ml": [
        "നെഞ്ചുവേദന", "നെഞ്ച് വേദന", "ശ്വാസം മുട്ട", "ശ്വാസം എടുക്കാൻ",
        "ബോധം പോയ", "അപസ്മാരം", "അമിത രക്തസ്രാവം", "പാമ്പ് കടി", "പാമ്പ് കടിച്ച",
        "വിഷം", "ആത്മഹത്യ", "പക്ഷാഘാതം", "രക്തം ഛർദ്ദ",
        "ഹൃദയാഘാതം", "ഹാർട്ട് അറ്റാക്ക്", "സ്ട്രോക്ക്", "കീടനാശിനി", "മരിക്കണം",  # needs native-speaker review
        "ശ്വാസം ഇല്ല", "ശ്വാസമില്ല", "ബോധം ഇല്ല", "ബോധമില്ല", "രക്തം നിൽക്കുന്നില്ല",  # needs native-speaker review
    ],
    "romanised": [
        "seene mein dard", "seene me dard", "sine me dard", "chhati me dard",  # needs native-speaker review
        "saans nahi aa", "saans nahi aati", "sans nahi aa", "saans nahi le", "behosh",  # needs native-speaker review
        "saanp ne kaata", "saanp ne kata", "saanp ne kaat", "sanp ne kata", "sanp ne kaat",  # needs native-speaker review
        "dil ka daura",  # needs native-speaker review
        "zeher kha", "zehar kha", "jahar kha", "zeher pi", "zehar pi", "jahar pi",  # needs native-speaker review
        "atmahatya", "aatmahatya",  # needs native-speaker review
        "ede novu", "haavu kachide", "haavu kadide", "havu kachide", "havu kadide",  # needs native-speaker review
        "prajne tappide",  # needs native-speaker review
        "nenju vali", "pambu kadi", "chathi noppi", "paamu karichindi",  # needs native-speaker review
        "nenju vedana", "pambu kadichu",  # needs native-speaker review
    ],
}

# Hyphen and dash look-alikes count as hyphens. Zero-width joiners are invisible and vary by keyboard.
_CHAR_MAP = str.maketrans({
    "’": "'", "-": " ", "_": " ", "‐": " ", "‑": " ", "‒": " ", "–": " ", "—": " ",
    "−": " ", "‌": None, "‍": None,
})


def normalise(text):
    """NFC first, so "ज़" typed as one code point or as two compares equal."""
    return " ".join(unicodedata.normalize("NFC", text or "").lower().translate(_CHAR_MAP).split())


ALL_FLAGS = list(dict.fromkeys(normalise(k) for lst in RED_FLAGS.values() for k in lst))
_PATTERNS = [(k, re.compile(r"\b" + re.escape(k) + r"\b" if k.isascii() else re.escape(k))) for k in ALL_FLAGS]


# Denial forms for ASCII (English and romanised) keywords. The negation must sit directly before the keyword.
_NEGATION_BEFORE = re.compile(
    r"(?:\bno|\bnot|\bnever|\bwithout|\bdon't have|\bdo not have|\bdoesn't have|\bdoes not have"
    r"|\bdidn't have|\bdid not have)\s+(?:any\s+|a\s+)?$"
)
_LOOKBEHIND_CHARS = 32  # longer than the longest form, "does not have any "

# Denial words for hi/kn/ta/te/ml keywords. A whole token only: "ಗೊತ್ತಿಲ್ಲ" ends in "ಇಲ್ಲ" but is not one.
_NEGATION_AFTER = frozenset(normalise(w) for w in ("नहीं", "नही", "ಇಲ್ಲ", "இல்லை", "లేదు", "ഇല്ല"))
_NOT_IN_TOKEN = r"\s.,;:!?।॥|()\[\]{}\"…"
# Skips the rest of the current word, since a keyword can be a stem, then captures up to 2 tokens.
# Punctuation ends the match, so a denial word after punctuation is never reached.
_NEXT_TWO_TOKENS = re.compile(rf"[^{_NOT_IN_TOKEN}]*(?:\s+([^{_NOT_IN_TOKEN}]+))?(?:\s+([^{_NOT_IN_TOKEN}]+))?")

# Normalising turns these into plain spaces, which erases a break between two statements.
_ERASED_BREAK = re.compile(r"\s+[-_]+\s*|[-_]+\s+|\s*[\u2010-\u2014\u2212]+\s*|[\r\n]+")


def _is_denied(text, match):
    """True only for the exact denial forms. Looks only outside the keyword's own span, so a keyword that
    contains a negation ("not breathing", "सांस नहीं आ") is never denied by its own words."""
    if match.group().isascii():
        return bool(_NEGATION_BEFORE.search(text, max(0, match.start() - _LOOKBEHIND_CHARS), match.start()))
    return not _NEGATION_AFTER.isdisjoint(_NEXT_TWO_TOKENS.match(text, match.end()).groups())


def _scan(text):
    for kw, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            if not _is_denied(text, match):
                return kw
    return None


def find_red_flag(text: str):
    """Return the first keyword with an occurrence that is not denied, or None. Checks all languages.
    Scans twice. The plain scan finds "chest\\npain". The second keeps the breaks normalising erases, so
    "no - chest pain" and "no\\nchest pain" do not read as a denial. RED if either scan finds a keyword."""
    raw = text or ""
    return _scan(normalise(raw)) or _scan(normalise(_ERASED_BREAK.sub(" . ", raw)))
