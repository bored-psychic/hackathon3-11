"""Offline unit tests for the /chat pipeline. Standard library only; makes no network calls.
Run from the repo root, venv active:  python -m unittest discover -s tests -v

Non-English sentences here are copied from tests/demo_sentences.txt or the project brief.
No new translations are introduced in this file."""
import contextlib
import io
import json
import logging
import os
import socket
import sys
import unittest
from unittest import mock

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Keep the real key out of the test process: importing app would otherwise load .env.
with mock.patch("dotenv.load_dotenv"):
    import app as chat_app

from redflags import find_red_flag  # noqa: E402

LANGS = ("en", "kn", "hi", "ta", "te", "ml")
RED_SENTENCE = {
    "en": "My father has chest pain and is sweating a lot",
    "kn": "ನನ್ನ ಅಪ್ಪನಿಗೆ ಎದೆ ನೋವು ಇದೆ",
    "hi": "मेरी माँ को सीने में दर्द हो रहा है",
    "ta": "எனக்கு நெஞ்சு வலி இருக்கிறது",
    "te": "నాకు ఛాతీ నొప్పి ఉంది",
    "ml": "അച്ഛന് നെഞ്ചുവേദന ഉണ്ട്",
}
FAKE_KEY = "fake-key-for-tests"
QUESTION_KEYS = {"type", "reply", "level", "symptoms_en"}
FINAL_KEYS = {"type", "level", "reply", "reason", "advice", "symptoms_en"}
ERROR_KEYS = {"type", "reply"}


class NetworkCallBlocked(BaseException):
    """BaseException on purpose: /chat has `except Exception`, which would swallow anything
    weaker and turn a real network call into a passing test."""


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        self.network_attempts = []

        def blocked(*args, **kwargs):
            self.network_attempts.append(args)
            raise NetworkCallBlocked(f"unpatched network call: {args!r}")

        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "socket.gethostbyname"):
            patcher = mock.patch(target, blocked)
            patcher.start()
            self.addCleanup(patcher.stop)

        env = mock.patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY})
        env.start()
        self.addCleanup(env.stop)
        self.client = chat_app.app.test_client()

    def tearDown(self):
        self.assertEqual(self.network_attempts, [], "test attempted a real network call")

    def post(self, message="I have a cold", language="en", history=None):
        return self.client.post("/chat", json={"message": message, "language": language, "history": history or []})

    def chat_with_llm(self, llm_result, **kwargs):
        """POST to /chat with call_llm faked. Returns (response, the call_llm mock)."""
        with mock.patch("app.call_llm", return_value=llm_result) as llm:
            return self.post(**kwargs), llm


def bot_turns(count):
    """A history holding `count` earlier follow-up questions from the bot."""
    history = []
    for i in range(count):
        history += [{"role": "user", "text": f"answer {i}"}, {"role": "bot", "text": f"question {i}?"}]
    return history


def gemini_reply(text):
    """A fake successful requests.post result carrying `text` as the model output."""
    response = mock.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return response


class RedFlagPathTests(OfflineTestCase):
    def assert_hard_coded_red(self, response, lang="en"):
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["type"], "final")
        self.assertEqual(body["level"], "RED")
        self.assertEqual(body["reply"], chat_app.RED_MSG[lang])
        self.assertTrue(body["matched"])

    def test_red_flag_in_each_language_is_red_without_llm(self):
        for lang in LANGS:
            with self.subTest(lang=lang), mock.patch("app.call_llm") as llm:
                self.assert_hard_coded_red(self.post(RED_SENTENCE[lang], lang), lang)
                llm.assert_not_called()

    def test_every_red_row_in_demo_sentences_is_red_without_llm(self):
        with open(os.path.join(REPO_ROOT, "tests", "demo_sentences.txt"), encoding="utf-8") as f:
            rows = [line.split("|", 2) for line in f if line.strip() and not line.startswith("#")]
        red_rows = [(lang.strip(), text.strip()) for level, lang, text in rows if level.strip() == "RED"]
        self.assertEqual(len(red_rows), 9)
        for lang, text in red_rows:
            with self.subTest(sentence=text), mock.patch("app.call_llm") as llm:
                self.assert_hard_coded_red(self.post(text, lang), lang)
                llm.assert_not_called()

    def test_red_flag_only_in_earlier_history_turn_is_red(self):
        history = [{"role": "user", "text": "my father has chest pain"}, {"role": "bot", "text": "How long?"}]
        with mock.patch("app.call_llm") as llm:
            self.assert_hard_coded_red(self.post("about two hours", history=history))
            llm.assert_not_called()

    def test_red_flag_word_in_a_bot_turn_does_not_trigger_red(self):
        history = [{"role": "user", "text": "I feel unwell"}, {"role": "bot", "text": "Do you have chest pain?"}]
        response, llm = self.chat_with_llm({"type": "final", "level": "GREEN"}, message="no", history=history)
        self.assertEqual(response.get_json()["level"], "GREEN")
        llm.assert_called_once()

    def test_message_over_the_limit_with_a_red_flag_is_still_red(self):
        with mock.patch("app.call_llm") as llm:
            self.assert_hard_coded_red(self.post("x" * 1500 + " chest pain"))
            llm.assert_not_called()


class SafetyOverrideTests(OfflineTestCase):
    def assert_overridden(self, llm_result):
        response, _ = self.chat_with_llm(llm_result)
        body = response.get_json()
        self.assertEqual(body["type"], "final")
        self.assertEqual(body["level"], "RED")
        self.assertEqual(body["matched"], "chest pain")

    def test_llm_green_with_red_symptom_becomes_red(self):
        self.assert_overridden({"type": "final", "level": "GREEN", "reply": "rest", "symptoms_en": ["chest pain"]})

    def test_llm_question_with_red_symptom_becomes_red(self):
        self.assert_overridden({"type": "question", "reply": "How long?", "level": None, "symptoms_en": ["chest pain"]})

    def test_reply_that_normalises_to_error_still_becomes_red(self):
        self.assert_overridden({"type": "nonsense", "symptoms_en": ["chest pain"]})
        self.assert_overridden({"type": "question", "reply": "", "symptoms_en": ["chest pain"]})

    def test_malformed_symptom_list_still_becomes_red(self):
        self.assert_overridden({"type": "final", "level": "GREEN", "symptoms_en": "chest pain"})
        self.assert_overridden({"type": "final", "level": "GREEN", "symptoms_en": ["chest pain", 5, None]})

    def test_llm_red_stays_red_with_its_own_text(self):
        llm_result = {"type": "final", "level": "RED", "reply": "r", "reason": "why", "advice": "go",
                      "symptoms_en": ["chest pain"]}
        body = self.chat_with_llm(llm_result)[0].get_json()
        self.assertEqual((body["level"], body["reason"], body["advice"]), ("RED", "why", "go"))


class LlmFailureTests(OfflineTestCase):
    def test_llm_exception_gives_http_200_localised_error(self):
        for lang in LANGS:
            with self.subTest(lang=lang), mock.patch("app.call_llm", side_effect=RuntimeError("boom")):
                with self.assertLogs("app", level="ERROR"):
                    response = self.post("I have a cold", lang)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), {"type": "error", "reply": chat_app.ERR_MSG[lang]})

    def test_missing_api_key_gives_error_response(self):
        with mock.patch.dict(os.environ), self.assertLogs("app", level="ERROR"):
            del os.environ["GEMINI_API_KEY"]
            response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["type"], "error")

    def test_unusable_gemini_payloads_give_error_response(self):
        blocked = mock.Mock()
        blocked.raise_for_status.return_value = None
        blocked.json.return_value = {"promptFeedback": {"blockReason": "SAFETY"}}
        for fake in (gemini_reply("this is not json"), gemini_reply("```json\nnot json\n```"), blocked):
            with self.subTest(fake=fake), mock.patch("requests.post", return_value=fake):
                with self.assertLogs("app", level="ERROR"):
                    response = self.post()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["type"], "error")


class NormalizeTests(OfflineTestCase):
    def test_lowercase_level_is_uppercased(self):
        self.assertEqual(chat_app.normalize_llm({"type": "final", "level": "amber"}, "en")["level"], "AMBER")
        self.assertEqual(chat_app.normalize_llm({"type": "final", "level": " green "}, "en")["level"], "GREEN")

    def test_missing_or_invalid_level_on_final_becomes_amber(self):
        for level in ({}, {"level": None}, {"level": "PURPLE"}, {"level": 5}, {"level": ["RED"]}):
            with self.subTest(level=level):
                self.assertEqual(chat_app.normalize_llm({"type": "final", **level}, "en")["level"], "AMBER")

    def test_unknown_type_with_valid_level_becomes_final(self):
        out = chat_app.normalize_llm({"type": "triage", "level": "green", "reason": "r"}, "en")
        self.assertEqual((out["type"], out["level"], out["reason"]), ("final", "GREEN", "r"))

    def test_unknown_type_with_reply_becomes_question(self):
        for out in ({"type": "ask", "reply": "How long?"}, {"reply": "How long?"}, {"type": ["x"], "reply": "How long?"}):
            with self.subTest(out=out):
                self.assertEqual(chat_app.normalize_llm(out, "en"),
                                 {"type": "question", "reply": "How long?", "level": None, "symptoms_en": []})

    def test_unknown_type_with_nothing_usable_is_localised_error(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(chat_app.normalize_llm({"type": "x", "level": "BLUE"}, lang),
                                 {"type": "error", "reply": chat_app.ERR_MSG[lang]})

    def test_non_dict_reply_is_localised_error(self):
        for out in (None, "text", 5, True, [{"type": "final", "level": "GREEN"}]):
            for lang in LANGS:
                with self.subTest(out=out, lang=lang):
                    self.assertEqual(chat_app.normalize_llm(out, lang),
                                     {"type": "error", "reply": chat_app.ERR_MSG[lang]})

    def test_question_needs_a_non_empty_string_reply(self):
        for reply in ({}, {"reply": ""}, {"reply": "   "}, {"reply": None}, {"reply": 5}, {"reply": ["How long?"]}):
            with self.subTest(reply=reply):
                self.assertEqual(chat_app.normalize_llm({"type": "question", **reply}, "en")["type"], "error")

    def test_question_level_is_always_null(self):
        out = chat_app.normalize_llm({"type": "question", "reply": "How long?", "level": "AMBER"}, "en")
        self.assertIsNone(out["level"])

    def test_reason_and_advice_are_always_strings(self):
        out = chat_app.normalize_llm({"type": "final", "level": "GREEN"}, "en")
        self.assertEqual((out["reason"], out["advice"], out["reply"]), ("", "", ""))
        out = chat_app.normalize_llm({"type": "final", "level": "GREEN", "reason": 5, "advice": {"a": 1}, "reply": 7}, "en")
        self.assertEqual((out["reason"], out["advice"], out["reply"]), ("", "", ""))

    def test_advice_sent_as_a_list_of_steps_is_joined(self):
        out = chat_app.normalize_llm({"type": "final", "level": "GREEN", "advice": ["Rest.", "Drink water."]}, "en")
        self.assertEqual(out["advice"], "Rest. Drink water.")

    def test_symptoms_must_be_a_list_of_strings(self):
        for bad in ("cough", 5, None, {"a": 1}, ["cough", 5]):
            with self.subTest(bad=bad):
                out = chat_app.normalize_llm({"type": "final", "level": "GREEN", "symptoms_en": bad}, "en")
                self.assertEqual(out["symptoms_en"], [])
        out = chat_app.normalize_llm({"type": "final", "level": "GREEN", "symptoms_en": ["cough"]}, "en")
        self.assertEqual(out["symptoms_en"], ["cough"])

    def test_responses_keep_exactly_the_api_md_shapes(self):
        extra = {"debug": "secret", "matched": "x"}
        cases = [
            ({"type": "question", "reply": "How long?", **extra}, QUESTION_KEYS),
            ({"type": "final", "level": "GREEN", **extra}, FINAL_KEYS),
            ({"type": "question", **extra}, ERROR_KEYS),
        ]
        for llm_result, keys in cases:
            with self.subTest(llm_result=llm_result):
                self.assertEqual(set(self.chat_with_llm(llm_result)[0].get_json()), keys)


class CallLlmTests(OfflineTestCase):
    EXPECTED = {"type": "final", "level": "amber"}
    RAW = json.dumps(EXPECTED)

    def test_fenced_and_plain_json_parse_the_same(self):
        for text in (self.RAW, f"```json\n{self.RAW}\n```", f"```\n{self.RAW}\n```", f"```JSON {self.RAW}```",
                     f"\n  ```json\n{self.RAW}\n```  \n"):
            with self.subTest(text=text), mock.patch("requests.post", return_value=gemini_reply(text)):
                self.assertEqual(chat_app.call_llm([], "hi", "en"), self.EXPECTED)

    def test_backticks_inside_a_json_value_are_kept(self):
        text = json.dumps({"reply": "use ```this``` word"})
        with mock.patch("requests.post", return_value=gemini_reply(text)):
            self.assertEqual(chat_app.call_llm([], "hi", "en")["reply"], "use ```this``` word")

    def test_fenced_lowercase_reply_is_normalised_through_chat(self):
        with mock.patch("requests.post", return_value=gemini_reply(f"```json\n{self.RAW}\n```")):
            body = self.post().get_json()
        self.assertEqual((body["type"], body["level"]), ("final", "AMBER"))

    def test_system_prompt_keeps_the_safety_rules(self):
        self.assertIn("Never recommend specific medicines or doses", chat_app.SYSTEM_PROMPT)
        self.assertIn("choose the more serious", chat_app.SYSTEM_PROMPT)


class FollowUpCapTests(OfflineTestCase):
    QUESTION = {"type": "question", "reply": "One more question?", "level": None, "symptoms_en": ["cough"]}

    def system_text_sent(self, history):
        with mock.patch("requests.post", return_value=gemini_reply(json.dumps(self.QUESTION))) as post:
            self.post(history=history)
        return post.call_args.kwargs["json"]["systemInstruction"]["parts"][0]["text"]

    def test_question_after_two_bot_turns_becomes_final_amber(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                response, _ = self.chat_with_llm(self.QUESTION, language=lang, history=bot_turns(2))
                self.assertEqual(response.status_code, 200)
                body = response.get_json()
                self.assertEqual(set(body), FINAL_KEYS)
                self.assertEqual((body["type"], body["level"]), ("final", "AMBER"))
                self.assertEqual(body["reply"], chat_app.FALLBACK_MSG[lang])
                self.assertEqual(body["advice"], chat_app.FALLBACK_MSG[lang])
                self.assertEqual(body["symptoms_en"], ["cough"])

    def test_more_than_two_bot_turns_is_also_capped(self):
        body = self.chat_with_llm(self.QUESTION, history=bot_turns(5))[0].get_json()
        self.assertEqual((body["type"], body["level"]), ("final", "AMBER"))

    def test_first_and_second_follow_up_are_allowed(self):
        for count in (0, 1):
            with self.subTest(bot_turns=count):
                body = self.chat_with_llm(self.QUESTION, history=bot_turns(count))[0].get_json()
                self.assertEqual(body["type"], "question")

    def test_model_final_at_the_cap_passes_through(self):
        llm_result = {"type": "final", "level": "GREEN", "reason": "r", "advice": "a"}
        body = self.chat_with_llm(llm_result, history=bot_turns(2))[0].get_json()
        self.assertEqual((body["level"], body["reason"]), ("GREEN", "r"))

    def test_prompt_demands_final_only_at_the_cap(self):
        line = "You must now return type final."
        self.assertIn(line, self.system_text_sent(bot_turns(2)))
        self.assertNotIn(line, self.system_text_sent(bot_turns(1)))

    def test_red_symptom_beats_the_cap_fallback(self):
        llm_result = {"type": "question", "reply": "How long?", "symptoms_en": ["chest pain"]}
        body = self.chat_with_llm(llm_result, history=bot_turns(2))[0].get_json()
        self.assertEqual(body["level"], "RED")

    def test_fallback_text_exists_for_every_language(self):
        self.assertEqual(set(chat_app.FALLBACK_MSG), set(chat_app.LANG_NAMES))
        self.assertEqual(chat_app.FALLBACK_MSG["en"], "I could not decide safely. Please visit your nearest PHC "
                                                      "within 24 hours. If it gets worse, call 108.")
        for lang, text in chat_app.FALLBACK_MSG.items():
            with self.subTest(lang=lang):
                self.assertIn("108", text)
                self.assertIn("24", text)


class InputTests(OfflineTestCase):
    def test_empty_message_is_400(self):
        for message in ("", "   ", None):
            with self.subTest(message=message), mock.patch("app.call_llm") as llm:
                response = self.client.post("/chat", json={"message": message, "language": "en", "history": []})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json(), {"error": "empty"})
                llm.assert_not_called()

    def test_message_over_1000_characters_is_400(self):
        with mock.patch("app.call_llm") as llm:
            response = self.post("a" * 1001)
            llm.assert_not_called()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "too_long"})

    def test_message_of_exactly_1000_characters_is_accepted(self):
        response, llm = self.chat_with_llm({"type": "final", "level": "GREEN"}, message="a" * 1000)
        self.assertEqual(response.status_code, 200)
        llm.assert_called_once()

    def test_unknown_language_falls_back_to_english(self):
        with mock.patch("app.call_llm", side_effect=RuntimeError("boom")), self.assertLogs("app", level="ERROR"):
            self.assertEqual(self.post(language="fr").get_json()["reply"], chat_app.ERR_MSG["en"])
        self.assertEqual(self.post("chest pain", "fr").get_json()["reply"], chat_app.RED_MSG["en"])
        response, llm = self.chat_with_llm({"type": "final", "level": "GREEN"}, language="fr")
        self.assertEqual(llm.call_args.args[2], "en")
        self.assertEqual(response.status_code, 200)


class FalseAlarmTests(OfflineTestCase):
    def test_innocent_sentences_are_not_red(self):
        for sentence, lang in (("I want benefits", "en"), ("ನನಗೆ ಈ ವಿಷಯ ಗೊತ್ತಿಲ್ಲ", "kn")):
            with self.subTest(sentence=sentence):
                self.assertIsNone(find_red_flag(sentence))
                response, llm = self.chat_with_llm({"type": "final", "level": "GREEN"}, message=sentence, language=lang)
                self.assertEqual(response.get_json()["level"], "GREEN")
                llm.assert_called_once()


class KeyLeakTests(OfflineTestCase):
    SECRET = "SECRET123"
    URL = f"https://generativelanguage.googleapis.com/v1beta/models/m:generateContent?key={SECRET}"

    def http_error(self, status, google_message):
        response = requests.Response()
        response.status_code = status
        response.url = self.URL
        response._content = json.dumps({"error": {"message": google_message}}).encode()
        return requests.HTTPError(f"{status} Client Error: Forbidden for url: {self.URL}", response=response)

    def run_and_capture(self, error):
        """POST to /chat with requests.post raising `error`. Returns (response, all log and stderr text)."""
        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(self.format(record))

        handler = Capture(level=logging.DEBUG)
        root = logging.getLogger()
        old_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        stderr = io.StringIO()
        try:
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": self.SECRET}), \
                    mock.patch("requests.post", side_effect=error), contextlib.redirect_stderr(stderr):
                response = self.post()
        finally:
            root.removeHandler(handler)
            root.setLevel(old_level)
        return response, "\n".join(records) + stderr.getvalue()

    def assert_no_leak(self, response, logged):
        self.assertNotIn(self.SECRET, logged)
        self.assertNotIn(self.SECRET, response.get_data(as_text=True))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"type": "error", "reply": chat_app.ERR_MSG["en"]})

    def test_http_error_url_never_reaches_the_logs(self):
        self.assertIn(self.SECRET, str(self.http_error(403, "x")))  # the error really does carry the key
        response, logged = self.run_and_capture(self.http_error(403, "free tier is not available"))
        self.assert_no_leak(response, logged)
        self.assertIn("status=403", logged)  # proves the capture saw the log line
        self.assertIn("free tier is not available", logged)

    def test_key_echoed_in_google_message_is_scrubbed(self):
        message = f"Permission denied: Consumer 'api_key:{self.SECRET}' has been suspended."
        response, logged = self.run_and_capture(self.http_error(403, message))
        self.assert_no_leak(response, logged)
        self.assertIn("Consumer 'api_key:***' has been suspended", logged)

    def test_connection_error_url_never_reaches_the_logs(self):
        error = requests.ConnectionError(f"Max retries exceeded with url: {self.URL}")
        response, logged = self.run_and_capture(error)
        self.assert_no_leak(response, logged)
        self.assertIn("ConnectionError", logged)


class NetworkGuardTests(OfflineTestCase):
    def test_unpatched_request_is_blocked_and_recorded(self):
        with self.assertRaises(NetworkCallBlocked):
            requests.post("https://example.invalid/", timeout=1)
        self.assertTrue(self.network_attempts)
        self.network_attempts.clear()  # expected here; tearDown fails on any other attempt

    def test_unpatched_chat_call_is_not_swallowed_by_the_error_path(self):
        with self.assertRaises(NetworkCallBlocked):
            self.post()
        self.assertTrue(self.network_attempts)
        self.network_attempts.clear()


if __name__ == "__main__":
    unittest.main()
