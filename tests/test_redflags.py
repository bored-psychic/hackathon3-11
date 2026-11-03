"""Offline tests for the hard-coded red-flag check. Makes no network calls: OfflineTestCase keeps the guard.
Run from the repo root, venv active:  python -m unittest discover -s tests -v

MUST_CATCH and MUST_NOT_CATCH_BY_MEANING are the project brief's lists, copied as written."""
import os
import unicodedata
from unittest import mock

from test_chat import REPO_ROOT, OfflineTestCase

from redflags import ALL_FLAGS, RED_FLAGS, find_red_flag, normalise

MUST_CATCH = [
    "A snake bit my son on the leg",
    "My son was bitten by a snake",
    "He is having a heart attack",
    "She had a stroke",
    "I am short of breath",
    "I can't breath",
    "He drank pesticide",
    "I want to kill myself",
    "She is bleeding heavily",
    "My baby is not breathing",
    "He has severe burns",
    "She is having convulsions",
    "He collapsed",
    "my chest hurts",
    "chest  pain",
    "chest-pain",
    "No, chest pain is getting worse",
    "no chest pain but he can't breathe",
    "ede novu ide",
    "seene mein dard hai",
    "ಹಾವು ಕಡಿದಿದೆ",
    "ಹೃದಯಾಘಾತ ಆಗಿದೆ",
    "ಎದೆ ನೋವು ಇಲ್ಲ ಆದರೆ ಉಸಿರಾಡಲು ಆಗುತ್ತಿಲ್ಲ",
    "मुझे सांप ने काट लिया",
    "उसे दिल का दौरा पड़ा",
    "उसने कीटनाशक पी लिया",
    "மாரடைப்பு வந்துவிட்டது",
    "గుండెపోటు వచ్చింది",
    "ഹൃദയാഘാതം ഉണ്ടായി",
]
MUST_NOT_CATCH_BY_MEANING = [
    "My shoe fits badly and my foot hurts",
    "I get fits of coughing at night",
    "I touched poison ivy and have a rash",
    "डॉक्टर का दौरा कल है",
    "I want benefits",
    "ನನಗೆ ಈ ವಿಷಯ ಗೊತ್ತಿಲ್ಲ",
]

# Natural phrasings beyond the brief's list, found by probing. The non-English ones need native-speaker review.
NATURAL_PHRASINGS = [
    "a cobra bit him", "a snake just bit me", "he is turning blue", "his lips are blue", "the bleeding is not stopping",
    "blood is not stopping", "road accident, lot of blood", "he is dying", "she isn't waking up", "she is not waking",
    "I don't want to live", "I will end it all", "she took too many tablets", "he took an overdose",
    "one side of his body is weak", "her face is drooping", "he got an electric shock", "the child drowned",
    "burned badly", "my chest feels tight", "severe chest tightness", "he had a fit", "she is fitting",
    "he has no chest pain and no pulse", "saanp ne kaat liya",
    "सांप ने डस लिया", "साँप ने डसा", "सीने में तेज दर्द है", "గుండె నొప్పి వస్తోంది",
]


def demo_rows():
    with open(os.path.join(REPO_ROOT, "tests", "demo_sentences.txt"), encoding="utf-8") as f:
        rows = [line.split("|", 2) for line in f if line.strip() and not line.startswith("#")]
    return [(level.strip(), lang.strip(), text.strip()) for level, lang, text in rows]


class CoverageTests(OfflineTestCase):
    def test_every_must_catch_phrase_is_red(self):
        for phrase in MUST_CATCH:
            with self.subTest(phrase=phrase):
                self.assertTrue(find_red_flag(phrase))

    def test_every_must_catch_phrase_is_red_through_chat_without_the_llm(self):
        for phrase in MUST_CATCH:
            with self.subTest(phrase=phrase), mock.patch("app.call_llm") as llm:
                body = self.post(phrase).get_json()
                self.assertEqual((body["type"], body["level"]), ("final", "RED"))
                llm.assert_not_called()

    def test_natural_phrasings_are_red(self):
        for phrase in NATURAL_PHRASINGS:
            with self.subTest(phrase=phrase):
                self.assertTrue(find_red_flag(phrase))

    def test_shoe_that_is_fitting_is_not_red(self):
        self.assertIsNone(find_red_flag("the shoe is fitting badly"))

    def test_other_meanings_are_not_red(self):
        for phrase in MUST_NOT_CATCH_BY_MEANING:
            with self.subTest(phrase=phrase):
                self.assertIsNone(find_red_flag(phrase))

    def test_other_meanings_reach_the_llm_through_chat(self):
        for phrase in MUST_NOT_CATCH_BY_MEANING:
            with self.subTest(phrase=phrase):
                response, llm = self.chat_with_llm({"type": "final", "level": "GREEN"}, message=phrase)
                self.assertEqual(response.get_json()["level"], "GREEN")
                llm.assert_called_once()

    def test_non_red_demo_sentences_are_not_caught_by_a_keyword(self):
        rows = [text for level, _, text in demo_rows() if level != "RED"]
        self.assertTrue(rows)
        for text in rows:
            with self.subTest(sentence=text):
                self.assertIsNone(find_red_flag(text))

    def test_ambiguous_bare_words_are_gone(self):
        for word in ("fits", "poison", "दौरा", "सांस नहीं", "साँस नहीं", "ज़हर", "जहर"):
            with self.subTest(word=word):
                self.assertNotIn(normalise(word), ALL_FLAGS)

    def test_specific_phrases_replace_them(self):
        for keyword in ("has fits", "having fits", "had fits", "drank poison", "ate poison", "swallowed poison",
                        "took poison", "poisoned", "pesticide", "insecticide", "rat poison", "दौरा पड़", "दौरे पड़",
                        "दिल का दौरा", "सांस नहीं आ", "सांस नहीं ले", "साँस नहीं आ", "दम घुट", "सांस फूल रही",
                        "ज़हर खा", "ज़हर पी", "ज़हर ले", "जहर खा", "जहर पी", "जहर ले", "seene mein dard",
                        "saans nahi aa", "behosh", "saanp ne kaata", "ede novu", "haavu kachide", "haavu kadide",
                        "prajne tappide"):
            with self.subTest(keyword=keyword):
                self.assertIn(normalise(keyword), ALL_FLAGS)

    def test_ta_te_ml_cover_heart_attack_stroke_pesticide_and_suicide(self):
        expected = {
            "ta": ("மாரடைப்பு", "பக்கவாதம்", "பூச்சிக்கொல்லி", "தற்கொலை"),
            "te": ("గుండెపోటు", "పక్షవాతం", "పురుగుల మందు", "ఆత్మహత్య"),
            "ml": ("ഹൃദയാഘാതം", "പക്ഷാഘാതം", "കീടനാശിനി", "ആത്മഹത്യ"),
        }
        for lang, keywords in expected.items():
            for keyword in keywords:
                with self.subTest(lang=lang, keyword=keyword):
                    self.assertIn(keyword, RED_FLAGS[lang])
                    self.assertEqual(find_red_flag(keyword), normalise(keyword))


class NormaliseTests(OfflineTestCase):
    def test_normalisation_rules(self):
        cases = {"CHEST PAIN": "chest pain", "chest  \t pain": "chest pain", "chest-pain": "chest pain",
                 "chest_pain": "chest pain", "can’t breathe": "can't breathe", "  chest\npain  ": "chest pain"}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalise(raw), expected)

    def test_hindi_spelled_with_either_nukta_encoding_matches(self):
        composed = "ज़हर खा लिया"  # ज़ as one code point
        decomposed = "ज़हर खा लिया"  # ज + nukta
        self.assertNotEqual(composed, decomposed)
        self.assertEqual(unicodedata.normalize("NFC", composed), unicodedata.normalize("NFC", decomposed))
        self.assertTrue(find_red_flag(composed))
        self.assertTrue(find_red_flag(decomposed))

    def test_zero_width_joiners_do_not_hide_a_keyword(self):
        self.assertTrue(find_red_flag("ಎದೆ‌ ನೋವು"))
        self.assertTrue(find_red_flag("नहीं है पर सी‍ने में दर्द"))

    def test_empty_input_is_not_red(self):
        for text in ("", None, "   "):
            with self.subTest(text=text):
                self.assertIsNone(find_red_flag(text))


class HistoryJoinTests(OfflineTestCase):
    def test_user_turns_are_joined_with_a_sentence_break(self):
        history = [{"role": "user", "text": "first"}, {"role": "bot", "text": "bot text"},
                   {"role": "user", "text": "second"}]
        with mock.patch("app.call_llm", return_value={"type": "final", "level": "GREEN"}), \
                mock.patch("app.find_red_flag", return_value=None) as check:
            self.post("third", history=history)
        self.assertEqual(check.call_args_list[0].args[0], "first . second . third")
