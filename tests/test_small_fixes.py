"""Offline tests for the RED response, the debug setting and the doc notes. OfflineTestCase keeps the network guard.
Run from the repo root, venv active:  python -m unittest discover -s tests -v"""
import os
import runpy
from unittest import mock

from test_chat import FINAL_KEYS, LANGS, REPO_ROOT, OfflineTestCase, bot_turns

import app as chat_app


def read_doc(name):
    with open(os.path.join(REPO_ROOT, name), encoding="utf-8") as f:
        return f.read()


class QuestionWithRedLevelTests(OfflineTestCase):
    def test_question_with_level_red_returns_the_red_response(self):
        for level in ("RED", "red", " Red "):
            for lang in LANGS:
                with self.subTest(level=level, lang=lang):
                    llm_result = {"type": "question", "level": level, "reply": "How long?", "symptoms_en": ["cough"]}
                    body = self.chat_with_llm(llm_result, language=lang)[0].get_json()
                    self.assertEqual(body, chat_app.red_response(lang))

    def test_it_is_red_even_without_a_reply(self):
        body = self.chat_with_llm({"type": "question", "level": "RED"})[0].get_json()
        self.assertEqual((body["type"], body["level"]), ("final", "RED"))

    def test_it_beats_the_follow_up_cap(self):
        body = self.chat_with_llm({"type": "question", "level": "RED", "reply": "?"}, history=bot_turns(2))[0].get_json()
        self.assertEqual(body["level"], "RED")

    def test_it_keeps_the_api_md_shape_without_matched(self):
        body = self.chat_with_llm({"type": "question", "level": "RED", "reply": "?"})[0].get_json()
        self.assertEqual(set(body), FINAL_KEYS)

    def test_a_red_symptom_on_top_still_gives_red(self):
        llm_result = {"type": "question", "level": "RED", "reply": "?", "symptoms_en": ["chest pain"]}
        self.assertEqual(self.chat_with_llm(llm_result)[0].get_json()["level"], "RED")

    def test_question_with_any_other_level_stays_a_question(self):
        for level in ("AMBER", "GREEN", None, "PURPLE"):
            with self.subTest(level=level):
                body = self.chat_with_llm({"type": "question", "level": level, "reply": "How long?"})[0].get_json()
                self.assertEqual((body["type"], body["level"]), ("question", None))


class RedResponseTests(OfflineTestCase):
    def test_hard_coded_red_shows_the_message_once(self):
        for lang in LANGS:
            with self.subTest(lang=lang), mock.patch("app.call_llm") as llm:
                body = self.post("chest pain", lang).get_json()
                llm.assert_not_called()
                self.assertEqual(body, {"type": "final", "level": "RED", "reply": chat_app.RED_MSG[lang],
                                        "reason": chat_app.RED_MSG[lang], "advice": "", "symptoms_en": [],
                                        "matched": "chest pain"})

    def test_llm_override_uses_the_same_response(self):
        llm_result = {"type": "final", "level": "GREEN", "symptoms_en": ["chest pain", "cough"]}
        body = self.chat_with_llm(llm_result)[0].get_json()
        self.assertEqual(body, chat_app.red_response("en", "chest pain"))
        self.assertEqual(body["symptoms_en"], [])

    def test_red_response_has_the_final_shape_plus_matched(self):
        self.assertEqual(set(chat_app.red_response("en", "x")), FINAL_KEYS | {"matched"})
        self.assertEqual(set(chat_app.red_response("en")), FINAL_KEYS)


class DebugSettingTests(OfflineTestCase):
    def test_debug_values(self):
        for value, expected in (("1", True), ("true", True), ("TRUE", True), (" yes ", True), ("on", True),
                                ("0", False), ("false", False), ("no", False), ("off", False), ("", False)):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"FLASK_DEBUG": value}):
                self.assertIs(chat_app.debug_enabled(), expected)

    def test_debug_is_off_when_unset(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("FLASK_DEBUG", None)
            self.assertIs(chat_app.debug_enabled(), False)

    def run_app_as_main(self):
        # load_dotenv is patched so running the file does not load the real .env
        with mock.patch("dotenv.load_dotenv"), mock.patch("flask.Flask.run") as run:
            runpy.run_path(os.path.join(REPO_ROOT, "app.py"), run_name="__main__")
        return run

    def test_main_passes_debug_off_and_port_5001_by_default(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("FLASK_DEBUG", None)
            self.run_app_as_main().assert_called_once_with(debug=False, port=5001)

    def test_main_reads_flask_debug(self):
        with mock.patch.dict(os.environ, {"FLASK_DEBUG": "1"}):
            self.run_app_as_main().assert_called_once_with(debug=True, port=5001)


class DocTests(OfflineTestCase):
    def test_readme_first_line_lists_all_six_languages(self):
        first_line = read_doc("README.md").splitlines()[0]
        for language in ("English", "Kannada", "Hindi", "Tamil", "Telugu", "Malayalam"):
            with self.subTest(language=language):
                self.assertIn(language, first_line)

    def test_api_md_has_the_frontend_notes(self):
        text = read_doc("API.md")
        for note in ('HTTP 400 {"error":"too_long"} for messages over 1000 characters',
                     "do not add type error replies to history", "clear history after a final result"):
            with self.subTest(note=note):
                self.assertIn(note, text)
