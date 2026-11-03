"""Hard-coded emergency check. Runs BEFORE the LLM and again on the LLM output.
Keywords are lowercase substrings. NOTE: have native speakers review kn/hi lists."""

RED_FLAGS = {
    "en": [
        "chest pain", "cant breathe", "can't breathe", "cannot breathe",
        "difficulty breathing", "trouble breathing", "unconscious", "fainted",
        "seizure", "fits", "heavy bleeding", "bleeding a lot", "snake bite",
        "snakebite", "poison", "suicide", "want to die", "face drooping",
        "slurred speech", "paralysis", "baby not breathing", "severe burn",
        "vomiting blood", "coughing blood",
    ],
    "hi": [
        "सीने में दर्द", "छाती में दर्द", "सांस नहीं", "सांस लेने में तकलीफ",
        "साँस नहीं", "साँस लेने में तकलीफ", "बेहोश", "दौरा", "मिर्गी",
        "बहुत खून", "खून बह", "सांप ने काटा", "साँप ने काटा", "ज़हर", "जहर",
        "आत्महत्या", "मरना चाहता", "लकवा", "खून की उल्टी", "खून की खांसी",
    ],
    "kn": [
        "ಎದೆ ನೋವು", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಉಸಿರಾಡಲು ಆಗುತ್ತಿಲ್ಲ", "ಉಸಿರು ಕಟ್ಟ",
        "ಪ್ರಜ್ಞೆ ತಪ್ಪ", "ಪ್ರಜ್ಞೆಯಿಲ್ಲ", "ಫಿಟ್ಸ್", "ಅಪಸ್ಮಾರ", "ತೀವ್ರ ರಕ್ತಸ್ರಾವ",
        "ಬಹಳ ರಕ್ತ", "ಹಾವು ಕಚ್ಚ", "ವಿಷ", "ಆತ್ಮಹತ್ಯೆ", "ಪಾರ್ಶ್ವವಾಯು",
        "ರಕ್ತ ವಾಂತಿ",
    ],
}

ALL_FLAGS = [k for lst in RED_FLAGS.values() for k in lst]


def find_red_flag(text: str):
    """Return the first matching keyword, or None. Checks all languages."""
    t = (text or "").lower().replace("’", "'")
    for kw in ALL_FLAGS:
        if kw in t:
            return kw
    return None
