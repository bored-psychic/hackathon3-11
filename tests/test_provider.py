"""Offline tests for the LLM providers. requests is always mocked, and OfflineTestCase keeps the network guard.
Run from the repo root, venv active:  python -m unittest discover -s tests -v"""
import contextlib
import io
import json
import logging
import os
from unittest import mock

import requests
from test_chat import OfflineTestCase

import app as chat_app
import list_models

KEY = "placeholder-key-value"
ENV_NAMES = ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "GEMINI_API_KEY", "GEMINI_MODEL")
GREEN = {"type": "final", "level": "GREEN", "reply": "r", "reason": "why", "advice": "rest", "symptoms_en": ["cough"]}


def http_response(status, payload):
    response = requests.Response()
    response.status_code = status
    response.url = "https://provider.invalid/path"
    response._content = json.dumps(payload).encode()
    return response


def completion(text=json.dumps(GREEN)):
    return http_response(200, {"choices": [{"message": {"content": text}}]})


def gemini(text=json.dumps(GREEN)):
    return http_response(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})


def error(status, message):
    return http_response(status, {"error": {"message": message}})


class ProviderTestCase(OfflineTestCase):
    ENV = {"LLM_PROVIDER": "groq", "LLM_API_KEY": KEY}

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, self.ENV)
        env.start()
        self.addCleanup(env.stop)
        for name in ENV_NAMES:
            if name not in self.ENV:
                os.environ.pop(name, None)
        sleep = mock.patch("time.sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def call(self, *responses, history=(), force_final=False):
        """Run call_llm against these fake responses. Returns (result, the requests.post mock)."""
        with mock.patch("requests.post", side_effect=list(responses)) as post:
            return chat_app.call_llm(list(history), "my message", "en", force_final), post


class GroqRequestTests(ProviderTestCase):
    def test_key_goes_in_the_authorization_header(self):
        _, post = self.call(completion())
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], f"Bearer {KEY}")

    def test_key_is_never_in_the_url_or_params(self):
        _, post = self.call(completion())
        self.assertNotIn(KEY, post.call_args.args[0])
        self.assertNotIn("params", post.call_args.kwargs)
        self.assertNotIn(KEY, json.dumps(post.call_args.kwargs["json"]))

    def test_posts_to_the_chat_completions_endpoint(self):
        _, post = self.call(completion())
        self.assertEqual(post.call_args.args[0], "https://api.groq.com/openai/v1/chat/completions")

    def test_response_format_temperature_and_timeout_are_sent(self):
        _, post = self.call(completion())
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(post.call_args.kwargs["json"]["temperature"], 0.2)
        self.assertEqual(post.call_args.kwargs["timeout"], 20)

    def test_default_model_is_the_one_chosen_from_the_live_list(self):
        _, post = self.call(completion())
        self.assertEqual(post.call_args.kwargs["json"]["model"], "openai/gpt-oss-120b")

    def test_llm_model_overrides_the_default(self):
        with mock.patch.dict(os.environ, {"LLM_MODEL": "other/model"}):
            _, post = self.call(completion())
        self.assertEqual(post.call_args.kwargs["json"]["model"], "other/model")

    def test_messages_hold_system_then_history_then_the_new_message(self):
        history = [{"role": "user", "text": "u1"}, {"role": "bot", "text": "b1"}]
        _, post = self.call(completion(), history=history)
        messages = post.call_args.kwargs["json"]["messages"]
        self.assertEqual([m["role"] for m in messages], ["system", "user", "assistant", "user"])
        self.assertEqual([m["content"] for m in messages[1:]], ["u1", "b1", "my message"])
        self.assertIn("Reply ONLY in English", messages[0]["content"])

    def test_system_message_says_json_because_groq_json_mode_requires_it(self):
        _, post = self.call(completion())
        self.assertIn("json", post.call_args.kwargs["json"]["messages"][0]["content"].lower())

    def test_force_final_is_added_to_the_system_message(self):
        _, post = self.call(completion(), force_final=True)
        self.assertIn("You must now return type final.", post.call_args.kwargs["json"]["messages"][0]["content"])

    def test_reply_is_parsed_with_and_without_fences(self):
        for text in (json.dumps(GREEN), f"```json\n{json.dumps(GREEN)}\n```"):
            with self.subTest(text=text):
                self.assertEqual(self.call(completion(text))[0], GREEN)

    def test_full_chat_round_trip(self):
        with mock.patch("requests.post", return_value=completion()):
            body = self.post().get_json()
        self.assertEqual((body["type"], body["level"], body["advice"]), ("final", "GREEN", "rest"))


class ResponseFormatRetryTests(ProviderTestCase):
    def test_400_about_response_format_retries_once_without_it(self):
        refused = error(400, "response_format is not supported by this model")
        result, post = self.call(refused, completion(f"```json\n{json.dumps(GREEN)}\n```"))
        self.assertEqual(result, GREEN)
        self.assertEqual(post.call_count, 2)
        self.assertIn("response_format", post.call_args_list[0].kwargs["json"])
        self.assertNotIn("response_format", post.call_args_list[1].kwargs["json"])
        self.sleep.assert_not_called()

    def test_retry_keeps_everything_else_in_the_body(self):
        _, post = self.call(error(400, "response_format unsupported"), completion())
        first, second = (c.kwargs["json"] for c in post.call_args_list)
        first.pop("response_format")
        self.assertEqual(first, second)

    def test_groq_json_mode_failure_also_retries_without_it(self):
        refused = http_response(400, {"error": {"message": "Failed to generate JSON.", "code": "json_validate_failed"}})
        self.assertEqual(self.call(refused, completion())[0], GREEN)

    def test_second_400_is_not_retried_again(self):
        refused = error(400, "response_format unsupported")
        with mock.patch("requests.post", side_effect=[refused, refused]) as post, self.assertRaises(requests.HTTPError):
            chat_app.call_llm([], "m", "en")
        self.assertEqual(post.call_count, 2)

    def test_other_400_is_not_retried(self):
        with mock.patch("requests.post", side_effect=[error(400, "messages too long")]) as post, \
                self.assertRaises(requests.HTTPError):
            chat_app.call_llm([], "m", "en")
        self.assertEqual(post.call_count, 1)

    def test_other_status_mentioning_response_format_is_not_retried(self):
        with mock.patch("requests.post", side_effect=[error(500, "response_format broke")]) as post, \
                self.assertRaises(requests.HTTPError):
            chat_app.call_llm([], "m", "en")
        self.assertEqual(post.call_count, 1)


class RateLimitTests(ProviderTestCase):
    def test_429_waits_60_seconds_and_retries_once(self):
        with self.assertLogs("app", level="WARNING"):
            result, post = self.call(error(429, "slow down"), completion())
        self.assertEqual(result, GREEN)
        self.assertEqual(post.call_count, 2)
        self.sleep.assert_called_once_with(60)

    def test_second_429_is_not_retried_and_gives_the_error_reply(self):
        with mock.patch("requests.post", side_effect=[error(429, "slow down"), error(429, "slow down")]) as post, \
                self.assertLogs("app", level="WARNING") as logs:
            response = self.post()
        self.assertEqual(post.call_count, 2)
        self.sleep.assert_called_once_with(60)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"type": "error", "reply": chat_app.ERR_MSG["en"]})
        self.assertIn("status=429", "\n".join(logs.output))

    def test_success_does_not_wait(self):
        self.call(completion())
        self.sleep.assert_not_called()

    def test_only_one_wait_across_the_response_format_retry(self):
        responses = [error(429, "slow down"), error(400, "response_format unsupported"), error(429, "slow down")]
        with mock.patch("requests.post", side_effect=responses) as post, self.assertLogs("app", level="WARNING"), \
                self.assertRaises(requests.HTTPError):
            chat_app.call_llm([], "m", "en")
        self.assertEqual(post.call_count, 3)
        self.sleep.assert_called_once_with(60)

    def test_429_on_the_retry_without_response_format_still_waits_once(self):
        responses = [error(400, "response_format unsupported"), error(429, "slow down"), completion()]
        with self.assertLogs("app", level="WARNING"):
            result, post = self.call(*responses)
        self.assertEqual(result, GREEN)
        self.assertEqual(post.call_count, 3)
        self.assertNotIn("response_format", post.call_args.kwargs["json"])
        self.sleep.assert_called_once_with(60)

    def test_red_flag_message_never_reaches_the_rate_limited_provider(self):
        with mock.patch("requests.post") as post:
            self.assertEqual(self.post("chest pain").get_json()["level"], "RED")
        post.assert_not_called()
        self.sleep.assert_not_called()


class OpenRouterTests(ProviderTestCase):
    ENV = {"LLM_PROVIDER": "openrouter", "LLM_API_KEY": KEY, "LLM_MODEL": "vendor/some-model:free"}

    def test_uses_its_base_url_header_and_model(self):
        _, post = self.call(completion())
        self.assertEqual(post.call_args.args[0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], f"Bearer {KEY}")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "vendor/some-model:free")
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})

    def test_no_model_means_no_call_rather_than_a_guessed_model(self):
        del os.environ["LLM_MODEL"]
        with mock.patch("requests.post") as post, self.assertLogs("app", level="ERROR") as logs:
            body = self.post().get_json()
        post.assert_not_called()
        self.assertEqual(body["type"], "error")
        self.assertIn("LLM_MODEL is required for openrouter", "\n".join(logs.output))

    def test_payment_required_gives_the_error_reply_and_no_retry(self):
        with mock.patch("requests.post", side_effect=[error(402, "Insufficient credits")]) as post, \
                self.assertLogs("app", level="ERROR") as logs:
            body = self.post().get_json()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(body["type"], "error")
        self.assertIn("status=402", "\n".join(logs.output))


class GeminiTests(ProviderTestCase):
    ENV = {"LLM_PROVIDER": "gemini", "LLM_API_KEY": KEY}

    def test_key_goes_in_the_goog_header_and_never_in_the_url(self):
        _, post = self.call(gemini())
        self.assertEqual(post.call_args.kwargs["headers"], {"x-goog-api-key": KEY})
        self.assertNotIn(KEY, post.call_args.args[0])
        self.assertNotIn("params", post.call_args.kwargs)
        self.assertNotIn("key=", post.call_args.args[0])

    def test_keeps_the_gemini_request_shape(self):
        history = [{"role": "user", "text": "u1"}, {"role": "bot", "text": "b1"}]
        result, post = self.call(gemini(), history=history)
        body = post.call_args.kwargs["json"]
        self.assertEqual(result, GREEN)
        self.assertEqual([c["role"] for c in body["contents"]], ["user", "model", "user"])
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("Reply ONLY in English", body["systemInstruction"]["parts"][0]["text"])

    def test_gemini_key_and_model_are_fallbacks(self):
        del os.environ["LLM_API_KEY"]
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "old-key", "GEMINI_MODEL": "gemini-old"}):
            _, post = self.call(gemini())
        self.assertEqual(post.call_args.kwargs["headers"], {"x-goog-api-key": "old-key"})
        self.assertIn("/models/gemini-old:generateContent", post.call_args.args[0])

    def test_llm_settings_win_over_the_fallbacks(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "old-key", "GEMINI_MODEL": "gemini-old", "LLM_MODEL": "gemini-new"}):
            _, post = self.call(gemini())
        self.assertEqual(post.call_args.kwargs["headers"], {"x-goog-api-key": KEY})
        self.assertIn("/models/gemini-new:generateContent", post.call_args.args[0])

    def test_429_waits_and_retries_once(self):
        with self.assertLogs("app", level="WARNING"):
            result, post = self.call(error(429, "slow down"), gemini())
        self.assertEqual(result, GREEN)
        self.assertEqual(post.call_count, 2)
        self.sleep.assert_called_once_with(60)


class ProviderChoiceTests(ProviderTestCase):
    ENV = {}

    def provider_with(self, **env):
        with mock.patch.dict(os.environ, env):
            return chat_app.llm_provider()

    def test_default_is_groq(self):
        self.assertEqual(self.provider_with(), "groq")
        self.assertEqual(self.provider_with(LLM_API_KEY=KEY), "groq")

    def test_groq_is_the_default_even_with_an_old_gemini_key_present(self):
        self.assertEqual(self.provider_with(LLM_API_KEY=KEY, GEMINI_API_KEY="old-key"), "groq")

    def test_a_config_with_only_the_old_gemini_key_stays_on_gemini(self):
        self.assertEqual(self.provider_with(GEMINI_API_KEY="old-key"), "gemini")

    def test_explicit_provider_always_wins(self):
        self.assertEqual(self.provider_with(LLM_PROVIDER="openrouter", GEMINI_API_KEY="old-key"), "openrouter")
        self.assertEqual(self.provider_with(LLM_PROVIDER=" Gemini ", LLM_API_KEY=KEY), "gemini")
        self.assertEqual(self.provider_with(LLM_PROVIDER="", LLM_API_KEY=KEY), "groq")

    def test_groq_never_falls_back_to_the_gemini_key(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GEMINI_API_KEY": "old-key"}), \
                mock.patch("requests.post") as post, self.assertLogs("app", level="ERROR") as logs:
            body = self.post().get_json()
        post.assert_not_called()
        self.assertEqual(body["type"], "error")
        self.assertIn("LLM_API_KEY missing", "\n".join(logs.output))

    def test_unknown_provider_gives_the_error_reply_and_no_call(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "paid-thing", "LLM_API_KEY": KEY}), \
                mock.patch("requests.post") as post, self.assertLogs("app", level="ERROR"):
            body = self.post().get_json()
        post.assert_not_called()
        self.assertEqual(body["type"], "error")


class GroqKeyLeakTests(ProviderTestCase):
    def logged_text(self, side_effect):
        """POST to /chat with requests.post failing. Returns (response, all log and stderr text)."""
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
            with mock.patch("requests.post", side_effect=side_effect), contextlib.redirect_stderr(stderr):
                response = self.post()
        finally:
            root.removeHandler(handler)
            root.setLevel(old_level)
        return response, "\n".join(records) + stderr.getvalue()

    def test_key_echoed_in_the_provider_message_is_scrubbed(self):
        response, logged = self.logged_text([error(401, f"Invalid API key: {KEY}")])
        self.assertNotIn(KEY, logged)
        self.assertNotIn(KEY, response.get_data(as_text=True))
        self.assertIn("Invalid API key: ***", logged)
        self.assertIn("status=401", logged)

    def test_cutting_a_long_message_cannot_leave_part_of_the_key(self):
        _, logged = self.logged_text([error(401, "x" * 190 + KEY)])
        self.assertNotIn(KEY[:8], logged)

    def test_raw_requests_error_text_is_never_logged(self):
        raw = f"boom Authorization: Bearer {KEY}"
        _, logged = self.logged_text(requests.ConnectionError(raw))
        self.assertNotIn(KEY, logged)
        self.assertNotIn("boom", logged)
        self.assertIn("ConnectionError", logged)

    def test_stray_runtime_error_text_is_never_logged(self):
        _, logged = self.logged_text(RuntimeError(f"boom {KEY}"))
        self.assertNotIn(KEY, logged)
        self.assertNotIn("boom", logged)
        self.assertIn("RuntimeError", logged)


class ListModelsTests(ProviderTestCase):
    def run_main(self, argv, response=None, side_effect=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("requests.get", return_value=response, side_effect=side_effect) as get, \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = list_models.main(argv)
        return code, out.getvalue(), err.getvalue(), get

    def test_prints_only_sorted_model_ids(self):
        payload = {"data": [{"id": "b-model", "owned_by": "x", "active": True}, {"id": "a-model", "owned_by": "y"}]}
        code, out, err, _ = self.run_main(["list_models.py"], http_response(200, payload))
        self.assertEqual((code, out, err), (0, "a-model\nb-model\n", ""))

    def test_inactive_models_are_left_out(self):
        payload = {"data": [{"id": "live"}, {"id": "retired", "active": False}]}
        self.assertEqual(self.run_main(["list_models.py"], http_response(200, payload))[1], "live\n")

    def test_key_is_sent_in_the_header_and_never_printed(self):
        code, out, err, get = self.run_main(["list_models.py"], http_response(200, {"data": [{"id": "m"}]}))
        self.assertEqual(get.call_args.args[0], "https://api.groq.com/openai/v1/models")
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": f"Bearer {KEY}"})
        self.assertNotIn(KEY, get.call_args.args[0] + out + err)

    def test_provider_argument_chooses_the_endpoint(self):
        _, _, _, get = self.run_main(["list_models.py", "openrouter"], http_response(200, {"data": [{"id": "m:free"}]}))
        self.assertEqual(get.call_args.args[0], "https://openrouter.ai/api/v1/models")

    def test_gemini_uses_its_header_and_prints_bare_ids(self):
        payload = {"models": [{"name": "models/gemini-x", "displayName": "X"}]}
        code, out, _, get = self.run_main(["list_models.py", "gemini"], http_response(200, payload))
        self.assertEqual((code, out), (0, "gemini-x\n"))
        self.assertEqual(get.call_args.kwargs["headers"], {"x-goog-api-key": KEY})

    def test_refusal_prints_status_with_the_key_scrubbed(self):
        code, out, err, _ = self.run_main(["list_models.py"], error(401, f"bad key {KEY}"))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("HTTP 401", err)
        self.assertNotIn(KEY, err)

    def test_connection_error_prints_only_its_type(self):
        code, out, err, _ = self.run_main(["list_models.py"], side_effect=requests.ConnectionError(f"boom {KEY}"))
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(err.strip(), "ConnectionError")

    def test_missing_key_is_reported_without_a_call(self):
        del os.environ["LLM_API_KEY"]
        code, _, err, get = self.run_main(["list_models.py"])
        self.assertEqual(code, 1)
        self.assertIn("LLM_API_KEY missing", err)
        get.assert_not_called()

    def test_unknown_provider_is_refused_without_a_call(self):
        code, _, _, get = self.run_main(["list_models.py", "paid-thing"])
        self.assertEqual(code, 2)
        get.assert_not_called()
