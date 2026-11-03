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
MUST_NOT_CATCH_DENIAL = [
    "no chest pain",
    "I do not have chest pain",
    "He is not unconscious",
    "ನನಗೆ ಎದೆ ನೋವು ಇಲ್ಲ",
    "நெஞ்சு வலி இல்லை",
    "सीने में दर्द नहीं है",
    "सांस नहीं फूल रही है",
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


# Each negates another word right after the emergency. A 2-token denial window used to hide all five.
EMERGENCY_THEN_OTHER_DENIAL = [
    "सांप ने काटा दर्द नहीं",  # needs native-speaker review
    "बच्चा बेहोश सांस नहीं",  # needs native-speaker review
    "ಹಾವು ಕಡಿದಿದೆ ನೋವು ಇಲ್ಲ",  # needs native-speaker review
    "பாம்பு கடித்த வலி இல்லை",  # needs native-speaker review
    "పాము కరిచింది నొప్పి లేదు",  # needs native-speaker review
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


class HiddenEmergencyTests(OfflineTestCase):
    def test_the_five_hidden_emergencies_are_red(self):
        for phrase in EMERGENCY_THEN_OTHER_DENIAL:
            with self.subTest(phrase=phrase):
                self.assertTrue(find_red_flag(phrase))

    def test_the_five_hidden_emergencies_are_red_through_chat_without_the_llm(self):
        for phrase in EMERGENCY_THEN_OTHER_DENIAL:
            with self.subTest(phrase=phrase), mock.patch("app.call_llm") as llm:
                body = self.post(phrase).get_json()
                self.assertEqual((body["type"], body["level"]), ("final", "RED"))
                llm.assert_not_called()


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


class DenialGuardTests(OfflineTestCase):
    def assert_red(self, *phrases):
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(find_red_flag(phrase), f"should be RED: {phrase}")

    def assert_not_red(self, *phrases):
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIsNone(find_red_flag(phrase), f"should not be RED: {phrase}")

    def test_every_denial_phrase_is_not_red(self):
        self.assert_not_red(*MUST_NOT_CATCH_DENIAL)

    def test_every_denial_phrase_reaches_the_llm_through_chat(self):
        for phrase in MUST_NOT_CATCH_DENIAL:
            with self.subTest(phrase=phrase):
                response, llm = self.chat_with_llm({"type": "final", "level": "GREEN"}, message=phrase)
                self.assertEqual(response.get_json()["level"], "GREEN")
                llm.assert_called_once()

    def test_every_listed_english_negation_denies(self):
        for negation in ("no", "not", "never", "without", "don't have", "do not have", "doesn't have",
                         "does not have", "didn't have", "did not have"):
            for filler in ("", "any ", "a "):
                self.assert_not_red(f"{negation} {filler}chest pain", f"I {negation} {filler}CHEST-PAIN")

    def test_curly_apostrophe_negation_denies(self):
        self.assert_not_red("I don’t have chest pain", "he didn’t have a seizure")

    def test_negation_not_on_the_list_stays_red(self):
        self.assert_red("dont have chest pain", "he isn't unconscious", "she hasn't had a stroke",
                        "I am not having chest pain", "never had chest pain", "not really unconscious")

    def test_a_word_between_negation_and_keyword_stays_red(self):
        self.assert_red("no severe chest pain", "no fever or chest pain", "no such chest pain",
                        "no any a chest pain")

    def test_negation_must_be_a_whole_word(self):
        self.assert_red("piano chest pain", "knot chest pain", "casino chest pain")

    def test_punctuation_after_the_negation_stays_red(self):
        for mark in ".,;!?":
            self.assert_red(f"no{mark} chest pain", f"no {mark} chest pain", f"not{mark}chest pain")

    def test_a_break_that_normalising_would_erase_stays_red(self):
        self.assert_red("no - chest pain", "no -chest pain", "no- chest pain", "no _ chest pain",
                        "no\nchest pain", "no\r\nchest pain", "no \u2014 chest pain", "no\u2014chest pain",
                        "सीने में दर्द - नहीं", "सीने में दर्द\nनहीं")

    def test_a_hyphen_inside_a_phrase_still_denies(self):
        self.assert_not_red("no chest-pain", "no-chest-pain")

    def test_a_keyword_split_across_lines_is_still_found(self):
        self.assert_red("chest\npain")

    def test_any_undenied_occurrence_is_red(self):
        self.assert_red("no chest pain. chest pain is back", "no chest pain chest pain", "chest pain no chest pain",
                        "no chest pain but he collapsed", "सीने में दर्द नहीं पर सीने में दर्द है",
                        "ಎದೆ ನೋವು ಇಲ್ಲ, ಎದೆ ನೋವು ಇದೆ")

    def test_keyword_containing_a_negation_is_not_denied_by_its_own_words(self):
        self.assert_red("not breathing", "he is not breathing", "cannot breathe", "can not breathe",
                        "not able to breathe", "सांस नहीं आ रही", "साँस नहीं आ रही", "सांस नहीं ले पा रहा",
                        "மூச்சு விட முடியவில்லை", "ಉಸಿರಾಡಲು ಆಗುತ್ತಿಲ್ಲ", "ಪ್ರಜ್ಞೆಯಿಲ್ಲ")

    def test_keyword_containing_a_negation_can_be_denied_from_outside(self):
        self.assert_not_red("no not breathing", "सांस नहीं आ नहीं")  # needs native-speaker review
        self.assert_red("सांस नहीं आ रही नहीं")  # the negation is 2 tokens after. needs native-speaker review

    def test_each_indian_language_negation_denies(self):
        self.assert_not_red("सीने में दर्द नहीं", "सीने में दर्द नही", "ಎದೆ ನೋವು ಇಲ್ಲ", "நெஞ்சு வலி இல்லை",
                            "ఛాతీ నొప్పి లేదు", "നെഞ്ചുവേദന ഇല്ല")

    def test_negation_must_be_the_very_next_token(self):
        self.assert_not_red("सीने में दर्द नहीं", "सीने में दर्द नहीं है")  # needs native-speaker review
        self.assert_red("सीने में दर्द बिल्कुल नहीं", "सीने में दर्द बिल्कुल नहीं है")  # needs native-speaker review

    def test_negation_three_tokens_after_stays_red(self):
        self.assert_red("सीने में दर्द है अभी नहीं")  # needs native-speaker review

    def test_punctuation_before_the_indian_language_negation_stays_red(self):
        for mark in (",", ".", ";", "!", "?", "।", ":"):
            self.assert_red(f"सीने में दर्द{mark} नहीं", f"सीने में दर्द है{mark} नहीं", f"ಎದೆ ನೋವು{mark} ಇಲ್ಲ")

    def test_punctuation_right_after_the_indian_language_negation_still_denies(self):
        for mark in (".", ",", "!", "।"):
            self.assert_not_red(f"सीने में दर्द नहीं{mark}", f"ಎದೆ ನೋವು ಇಲ್ಲ{mark}")

    def test_negation_must_be_a_whole_token(self):
        self.assert_red("ಎದೆ ನೋವು ಗೊತ್ತಿಲ್ಲ", "நெஞ்சு வலி முடியவில்லை")  # needs native-speaker review

    def test_stem_keyword_skips_the_rest_of_its_word(self):
        self.assert_not_red("दौरा पड़ा नहीं")  # needs native-speaker review
        self.assert_red("दौरा पड़ा")

    def test_each_rule_applies_only_to_its_own_script(self):
        self.assert_red("no सीने में दर्द", "not ಎದೆ ನೋವು", "chest pain नहीं", "chest pain ಇಲ್ಲ",
                        "नहीं, सीने में दर्द है", "नहीं सीने में दर्द है")

    def test_romanised_keyword_uses_the_english_rule_only(self):
        self.assert_not_red("no seene mein dard", "not behosh")
        self.assert_red("seene mein dard nahi hai", "ede novu illa")  # needs native-speaker review

    def test_emergency_that_uses_a_separate_negation_word_stays_red(self):
        self.assert_red("ఊపిరి ఆడటం లేదు", "ఊపిరి ఆడడం లేదు", "खून बहना बंद नहीं हो रहा", "खून बंद नहीं हो रहा",
                        "ಪ್ರಜ್ಞೆ ಇಲ್ಲ", "మూర్ఛ వచ్చింది", "ശ്വാസം ഇല്ല")  # needs native-speaker review


class DenialThroughChatTests(OfflineTestCase):
    GREEN = {"type": "final", "level": "GREEN"}

    def assert_red_without_llm(self, message, history):
        with mock.patch("app.call_llm") as llm:
            body = self.post(message, history=history).get_json()
        self.assertEqual(body["level"], "RED")
        llm.assert_not_called()

    def test_negation_cannot_cross_from_one_turn_to_the_next(self):
        self.assert_red_without_llm("chest pain", [{"role": "user", "text": "no"}])
        self.assert_red_without_llm("ಇಲ್ಲ", [{"role": "user", "text": "ಎದೆ ನೋವು"}])
        self.assert_red_without_llm("नहीं", [{"role": "user", "text": "सीने में दर्द"}])

    def test_answering_no_to_the_bot_is_not_red(self):
        history = [{"role": "user", "text": "I feel unwell"}, {"role": "bot", "text": "Do you have chest pain?"}]
        response, llm = self.chat_with_llm(self.GREEN, message="no chest pain", history=history)
        self.assertEqual(response.get_json()["level"], "GREEN")
        llm.assert_called_once()

    def test_a_later_turn_can_still_report_the_denied_symptom(self):
        self.assert_red_without_llm("now chest pain started", [{"role": "user", "text": "no chest pain"}])

    def test_llm_listing_a_denied_symptom_is_not_overridden(self):
        result = {**self.GREEN, "symptoms_en": ["no chest pain", "mild cough"]}
        self.assertEqual(self.chat_with_llm(result)[0].get_json()["level"], "GREEN")

    def test_negation_cannot_cross_between_llm_symptoms(self):
        for symptoms in (["no", "chest pain"], ["cough without", "chest pain"], ["no fever", "chest pain"],
                         ["no chest pain", "chest pain"], ["mild cough", "not", "unconscious"]):
            with self.subTest(symptoms=symptoms):
                body = self.chat_with_llm({**self.GREEN, "symptoms_en": symptoms})[0].get_json()
                self.assertEqual(body["level"], "RED")

    def test_llm_symptoms_sent_as_one_string_use_the_same_check(self):
        self.assertEqual(self.chat_with_llm({**self.GREEN, "symptoms_en": "chest pain"})[0].get_json()["level"], "RED")
        self.assertEqual(self.chat_with_llm({**self.GREEN, "symptoms_en": "no chest pain"})[0].get_json()["level"], "GREEN")
