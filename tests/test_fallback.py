"""Offline tests for the Groq -> Gemini fallback and the /chat time budget. Every provider call is faked, and
OfflineTestCase keeps the network guard.
Run from the repo root, venv active:  python -m unittest discover -s tests -v"""
import json
import os
import re
import threading
import time
from unittest import mock

import requests
from test_chat import REPO_ROOT, NetworkCallBlocked
from test_provider import GREEN, ProviderTestCase, completion, error, gemini

import app as chat_app
import list_models

GROQ_KEY = "groq-key-for-tests"
GEMINI_KEY = "gemini-key-for-tests"
ERROR_REPLY = {"type": "error", "reply": chat_app.ERR_MSG["en"]}


class Route:
    """Stands in for requests.post. Answers each provider from its own queue, and records every call.
    A queue item is a response, an exception to raise, or a function called with the request's kwargs."""

    def __init__(self, groq=(), gemini=()):
        self.queues = {"groq": list(groq), "gemini": list(gemini)}
        self.calls = {"groq": [], "gemini": []}

    def __call__(self, url, **kwargs):
        provider = "gemini" if "generativelanguage" in url else "groq"
        self.calls[provider].append((url, kwargs))
        if not self.queues[provider]:
            raise NetworkCallBlocked(f"no answer queued for {provider}")
        item = self.queues[provider].pop(0)
        if callable(item):
            item = item(**kwargs)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def hang(self, **kwargs):
        """A request that uses all of its timeout."""
        self.now += kwargs["timeout"]
        return requests.Timeout()


class FallbackTestCase(ProviderTestCase):
    ENV = {"LLM_PROVIDER": "groq", "LLM_API_KEY": GROQ_KEY, "GEMINI_API_KEY": GEMINI_KEY, "GEMINI_MODEL": "gem-one"}

    def chat(self, route, message="I have a cold", **body):
        with mock.patch("requests.post", side_effect=route):
            return self.client.post("/chat", json={"message": message, "language": "en", **body})

    def without_gemini_key(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        del os.environ["GEMINI_API_KEY"]


class GoesToGeminiTests(FallbackTestCase):
    def assert_answered_by_gemini(self, groq_failure):
        route = Route(groq=[groq_failure], gemini=[gemini()])
        with self.assertLogs("app", level="WARNING"):
            body = self.chat(route).get_json()
        self.assertEqual((body["type"], body["level"], body["advice"]), ("final", "GREEN", "rest"))
        self.assertEqual((len(route.calls["groq"]), len(route.calls["gemini"])), (1, 1))

    def test_groq_429_goes_to_gemini_and_succeeds_without_any_wait(self):
        self.assert_answered_by_gemini(error(429, "slow down"))
        self.sleep.assert_not_called()

    def test_each_5xx_goes_to_gemini(self):
        for status in (500, 502, 503, 504):
            with self.subTest(status=status):
                self.assert_answered_by_gemini(error(status, "down"))

    def test_timeouts_and_connection_errors_go_to_gemini(self):
        for failure in (requests.Timeout(), requests.ConnectTimeout(), requests.ReadTimeout(),
                        requests.ConnectionError(), requests.exceptions.SSLError()):
            with self.subTest(failure=type(failure).__name__):
                self.assert_answered_by_gemini(failure)

    def test_a_rejected_groq_key_goes_to_gemini(self):
        self.assert_answered_by_gemini(error(401, "Invalid API Key"))

    def test_other_client_errors_do_not_go_to_gemini(self):
        for status in (400, 402, 403, 404, 422):
            with self.subTest(status=status), self.assertLogs("app", level="ERROR"):
                route = Route(groq=[error(status, "no")])
                self.assertEqual(self.chat(route).get_json(), ERROR_REPLY)
                self.assertEqual(route.calls["gemini"], [])

    def test_an_unreadable_groq_reply_does_not_go_to_gemini(self):
        route = Route(groq=[completion("this is not json")])
        with self.assertLogs("app", level="ERROR"):
            self.assertEqual(self.chat(route).get_json(), ERROR_REPLY)
        self.assertEqual(route.calls["gemini"], [])

    def test_groq_answering_never_touches_gemini(self):
        route = Route(groq=[completion()])
        self.assertEqual(self.chat(route).get_json()["level"], "GREEN")
        self.assertEqual(route.calls["gemini"], [])

    def test_gemini_is_asked_the_same_thing(self):
        history = [{"role": "user", "text": "u1"}, {"role": "bot", "text": "b1"}]
        route = Route(groq=[error(429, "x")], gemini=[gemini()])
        with self.assertLogs("app", level="WARNING"):
            self.chat(route, message="my message", language="hi", history=history, profile={"age": 40})
        groq_body, gemini_body = route.calls["groq"][0][1]["json"], route.calls["gemini"][0][1]["json"]
        groq_messages = groq_body["messages"]
        self.assertEqual(gemini_body["systemInstruction"]["parts"][0]["text"], groq_messages[0]["content"])
        self.assertIn("age 40 years", groq_messages[0]["content"])
        self.assertEqual([c["parts"][0]["text"] for c in gemini_body["contents"]],
                         [m["content"] for m in groq_messages[1:]])
        self.assertEqual([c["role"] for c in gemini_body["contents"]], ["user", "model", "user"])

    def test_the_final_instruction_reaches_gemini_too(self):
        history = [{"role": "user", "text": "a"}, {"role": "bot", "text": "b"}] * 2
        route = Route(groq=[error(503, "x")], gemini=[gemini()])
        with self.assertLogs("app", level="WARNING"):
            self.chat(route, history=history)
        self.assertIn("You must now return type final.",
                      route.calls["gemini"][0][1]["json"]["systemInstruction"]["parts"][0]["text"])

    def test_groq_model_name_is_not_sent_to_gemini(self):
        with mock.patch.dict(os.environ, {"LLM_MODEL": "vendor/groq-model", "GEMINI_MODEL": "gem-a,gem-b"}), \
                self.assertLogs("app", level="WARNING"):
            route = Route(groq=[error(429, "x")], gemini=[error(429, "x"), gemini()])
            self.assertEqual(self.chat(route).get_json()["level"], "GREEN")
        self.assertEqual(route.calls["groq"][0][1]["json"]["model"], "vendor/groq-model")
        urls = [c[0] for c in route.calls["gemini"]]
        self.assertIn("/models/gem-a:", urls[0])
        self.assertIn("/models/gem-b:", urls[1])

    def test_openrouter_also_falls_back(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "openrouter", "LLM_MODEL": "x:free"}), \
                self.assertLogs("app", level="WARNING"):
            route = Route(groq=[error(503, "x")], gemini=[gemini()])
            self.assertEqual(self.chat(route).get_json()["level"], "GREEN")

    def test_missing_groq_settings_do_not_silently_use_gemini(self):
        del os.environ["LLM_API_KEY"]
        route = Route(gemini=[gemini()])
        with self.assertLogs("app", level="ERROR") as logs:
            self.assertEqual(self.chat(route).get_json(), ERROR_REPLY)
        self.assertEqual(route.calls["gemini"], [])
        self.assertIn("LLM_API_KEY missing", "\n".join(logs.output))


class SafetyOnGeminiAnswerTests(FallbackTestCase):
    def answer(self, gemini_text, **body):
        route = Route(groq=[error(429, "x")], gemini=[gemini(gemini_text)])
        with self.assertLogs("app", level="WARNING"):
            return self.chat(route, **body).get_json()

    def test_red_override_applies_to_a_gemini_answer(self):
        body = self.answer(json.dumps({**GREEN, "symptoms_en": ["chest pain"]}))
        self.assertEqual((body["level"], body["matched"]), ("RED", "chest pain"))

    def test_normalisation_applies_to_a_gemini_answer(self):
        body = self.answer(json.dumps({"type": "final", "level": "amber", "advice": ["Rest.", "Drink."]}))
        self.assertEqual((body["level"], body["advice"]), ("AMBER", "Rest. Drink."))
        self.assertEqual(self.answer(json.dumps({"foo": 1})), ERROR_REPLY)

    def test_follow_up_cap_applies_to_a_gemini_answer(self):
        history = [{"role": "user", "text": "a"}, {"role": "bot", "text": "b"}] * 2
        body = self.answer(json.dumps({"type": "question", "reply": "More?"}), history=history)
        self.assertEqual((body["type"], body["level"]), ("final", "AMBER"))

    def test_a_red_flag_message_reaches_no_provider(self):
        route = Route()
        self.assertEqual(self.chat(route, message="chest pain").get_json()["level"], "RED")
        self.assertEqual(route.calls, {"groq": [], "gemini": []})


class NoGeminiKeyTests(FallbackTestCase):
    def setUp(self):
        super().setUp()
        self.without_gemini_key()

    def test_no_gemini_call_on_any_failure(self):
        for failure in (error(500, "x"), error(401, "x"), requests.Timeout(), requests.ConnectionError()):
            with self.subTest(failure=failure), self.assertLogs("app", level="WARNING") as logs:
                route = Route(groq=[failure])
                self.assertEqual(self.chat(route).get_json(), ERROR_REPLY)
                self.assertEqual(route.calls["gemini"], [])
                self.assertEqual(len(route.calls["groq"]), 1)
                self.assertNotIn("gemini", "\n".join(logs.output))  # it is not even attempted
        self.sleep.assert_not_called()

    def test_429_waits_3_seconds_and_tries_groq_once_more(self):
        route = Route(groq=[error(429, "x"), completion()])
        with self.assertLogs("app", level="WARNING"):
            self.assertEqual(self.chat(route).get_json()["level"], "GREEN")
        self.assertEqual(route.calls["gemini"], [])
        self.sleep.assert_called_once_with(3)

    def test_a_second_429_gives_the_error_reply(self):
        route = Route(groq=[error(429, "x"), error(429, "x")])
        with self.assertLogs("app", level="ERROR"):
            self.assertEqual(self.chat(route).get_json(), ERROR_REPLY)
        self.assertEqual(len(route.calls["groq"]), 2)


class BothFailTests(FallbackTestCase):
    def test_after_a_429_and_a_gemini_failure_groq_gets_one_more_try(self):
        route = Route(groq=[error(429, "x"), completion()], gemini=[error(403, "set up billing")])
        with self.assertLogs("app", level="WARNING"):
            self.assertEqual(self.chat(route).get_json()["level"], "GREEN")
        self.sleep.assert_called_once_with(3)

    def test_both_failing_gives_the_error_reply_after_one_more_try(self):
        route = Route(groq=[error(429, "x"), error(429, "x")], gemini=[requests.ConnectionError()])
        with self.assertLogs("app", level="ERROR") as logs:
            self.assertEqual(self.chat(route).get_json(), ERROR_REPLY)
        self.assertEqual((len(route.calls["groq"]), len(route.calls["gemini"])), (2, 1))
        self.sleep.assert_called_once_with(3)
        self.assertIn("status=429", "\n".join(logs.output))

    def test_a_5xx_is_not_retried_after_gemini_fails(self):
        route = Route(groq=[error(503, "x")], gemini=[requests.ConnectionError()])
        with self.assertLogs("app", level="ERROR"):
            self.assertEqual(self.chat(route).get_json(), ERROR_REPLY)
        self.assertEqual(len(route.calls["groq"]), 1)
        self.sleep.assert_not_called()

    def test_an_unreadable_gemini_reply_counts_as_failing(self):
        route = Route(groq=[error(429, "x"), completion()], gemini=[gemini("this is not json")])
        with self.assertLogs("app", level="WARNING"):
            self.assertEqual(self.chat(route).get_json()["level"], "GREEN")

    def test_the_log_says_what_each_provider_did(self):
        route = Route(groq=[error(500, "groq broke")], gemini=[error(403, "set up billing")])
        with self.assertLogs("app", level="WARNING") as logs:
            self.chat(route)
        logged = "\n".join(logs.output)
        self.assertIn("groq failed: HTTPError status=500 groq broke", logged)
        self.assertIn("gemini fallback failed: HTTPError status=403 set up billing", logged)
        self.assertIn("LLM failed: HTTPError status=500", logged)

    def test_gemini_as_chosen_provider_also_gets_one_more_try_after_a_429(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}), self.assertLogs("app", level="WARNING"):
            route = Route(gemini=[error(429, "x"), gemini()])
            self.assertEqual(self.chat(route).get_json()["level"], "GREEN")
        self.assertEqual(route.calls["groq"], [])
        self.sleep.assert_called_once_with(3)


class DeadlineTests(FallbackTestCase):
    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        self.sleep.side_effect = self.clock.sleep
        patcher = mock.patch("time.monotonic", self.clock.monotonic)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.start = self.clock.now

    def elapsed(self):
        return self.clock.now - self.start

    def assert_error_within_budget(self, route):
        with self.assertLogs("app", level="ERROR"):
            self.assertEqual(self.chat(route).get_json(), ERROR_REPLY)
        self.assertLessEqual(self.elapsed(), 35)

    def test_the_budget_leaves_time_before_35_s_and_the_frontend_abort(self):
        self.assertLess(chat_app.CHAT_DEADLINE_SECONDS, 35)
        with open(os.path.join(REPO_ROOT, "static", "app.js"), encoding="utf-8") as f:
            frontend_ms = int(re.search(r"CHAT_TIMEOUT_MS = (\d+)", f.read()).group(1))
        self.assertLess(35 * 1000, frontend_ms)

    def test_groq_and_gemini_both_hanging_stays_within_the_budget(self):
        route = Route(groq=[self.clock.hang], gemini=[self.clock.hang, self.clock.hang])
        self.assert_error_within_budget(route)
        self.assertEqual(route.calls["groq"][0][1]["timeout"], chat_app.OPENAI_TIMEOUT_SECONDS)
        self.assertLessEqual(route.calls["gemini"][0][1]["timeout"], chat_app.CHAT_DEADLINE_SECONDS - 20)

    def test_429_then_everything_hanging_stays_within_the_budget(self):
        route = Route(groq=[error(429, "x"), self.clock.hang], gemini=[self.clock.hang])
        self.assert_error_within_budget(route)
        self.assertEqual(len(route.calls["groq"]), 2)
        self.sleep.assert_called_once_with(3)

    def test_each_model_in_a_long_list_shares_the_same_budget(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini", "GEMINI_MODEL": "a,b,c,d"}):
            def slow_quota(**kwargs):
                self.clock.now += min(15, kwargs["timeout"])
                return error(429, "x")

            route = Route(gemini=[slow_quota] * 4)
            self.assert_error_within_budget(route)
        self.assertEqual(len(route.calls["gemini"]), 3)  # the 4th never starts: no time is left

    def test_no_wait_and_no_retry_when_too_little_time_is_left(self):
        def slow_429(**kwargs):
            self.clock.now += 10
            return error(429, "x")

        route = Route(groq=[slow_429], gemini=[self.clock.hang])
        self.assert_error_within_budget(route)
        self.assertEqual(len(route.calls["groq"]), 1)
        self.sleep.assert_not_called()

    def test_no_retry_pause_on_a_gemini_500_when_no_time_is_left(self):
        def busy_at_the_deadline(**kwargs):
            self.clock.now += kwargs["timeout"] - 0.5
            return error(500, "x")

        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini", "GEMINI_MODEL": "a"}):
            route = Route(gemini=[busy_at_the_deadline, busy_at_the_deadline])
            self.assert_error_within_budget(route)
        self.assertLessEqual(len(route.calls["gemini"]), 2)


class HardDeadlineTests(FallbackTestCase):
    """Real time, with a short budget: request timeouts cannot limit a request that never returns."""

    def test_a_request_that_never_returns_still_gets_the_error_reply(self):
        release = threading.Event()
        threads_before = set(threading.enumerate())

        def never_returns(**kwargs):
            release.wait(5)
            return requests.Timeout()

        route = Route(groq=[never_returns])
        with mock.patch("requests.post", side_effect=route), mock.patch.object(chat_app, "CHAT_DEADLINE_SECONDS", 0.1), \
                self.assertLogs("app", level="ERROR") as logs:
            started = time.monotonic()
            response = self.client.post("/chat", json={"message": "I have a cold", "language": "kn"})
            elapsed = time.monotonic() - started
            self.assertEqual(response.get_json(), {"type": "error", "reply": chat_app.ERR_MSG["kn"]})
            self.assertEqual(response.status_code, 200)
            self.assertLess(elapsed, 2)
            self.assertIn("TimeoutError", "\n".join(logs.output))

            # the abandoned attempt ends without starting a request to Gemini: its deadline has passed
            release.set()
            for thread in set(threading.enumerate()) - threads_before:
                thread.join(5)
        self.assertEqual(route.calls["gemini"], [])


class ProviderLoggingTests(FallbackTestCase):
    def info_log(self, route):
        with self.assertLogs("app", level="INFO") as logs:
            self.chat(route)
        return "\n".join(logs.output)

    def test_groq_answer_logs_groq(self):
        self.assertIn("LLM answered by groq", self.info_log(Route(groq=[completion()])))

    def test_gemini_answer_logs_gemini(self):
        logged = self.info_log(Route(groq=[error(429, "x")], gemini=[gemini()]))
        self.assertIn("LLM answered by gemini", logged)
        self.assertNotIn("LLM answered by groq", logged)

    def test_the_line_holds_the_provider_name_only(self):
        with mock.patch.dict(os.environ, {"GEMINI_MODEL": "secret-model"}):
            logged = self.info_log(Route(groq=[error(429, "x")], gemini=[gemini()]))
        self.assertNotIn("secret-model", logged)
        line = [l for l in logged.splitlines() if "answered by" in l][0]
        self.assertTrue(line.endswith("LLM answered by gemini"), line)

    def test_no_answer_logs_no_provider(self):
        self.assertNotIn("answered by", self.info_log(Route(groq=[error(400, "x")])))

    def test_the_answer_line_is_visible_by_default(self):
        self.assertEqual(chat_app.app.logger.getEffectiveLevel(), 20)


class KeySeparationTests(FallbackTestCase):
    def full_exchange(self):
        """Groq gets the first request and the retry. Gemini gets the fallback. Returns the Route."""
        route = Route(groq=[error(429, "x"), completion()], gemini=[error(503, "x"), error(503, "x")])
        with self.assertLogs("app", level="WARNING"):
            self.chat(route)
        self.assertEqual((len(route.calls["groq"]), len(route.calls["gemini"])), (2, 2))
        return route

    def test_groq_key_is_never_in_any_gemini_request(self):
        for url, kwargs in self.full_exchange().calls["gemini"]:
            self.assertNotIn(GROQ_KEY, url + repr(kwargs))
            self.assertEqual(kwargs["headers"], {"x-goog-api-key": GEMINI_KEY})

    def test_gemini_key_is_never_in_any_groq_request(self):
        for url, kwargs in self.full_exchange().calls["groq"]:
            self.assertNotIn(GEMINI_KEY, url + repr(kwargs))
            self.assertEqual(kwargs["headers"], {"Authorization": f"Bearer {GROQ_KEY}"})

    def test_no_key_is_ever_in_a_url_params_or_body(self):
        route = self.full_exchange()
        for url, kwargs in route.calls["groq"] + route.calls["gemini"]:
            self.assertNotIn("params", kwargs)
            self.assertNotIn(GROQ_KEY, url + json.dumps(kwargs["json"]))
            self.assertNotIn(GEMINI_KEY, url + json.dumps(kwargs["json"]))

    def test_gemini_as_chosen_provider_never_gets_the_groq_key(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}):
            route = Route(gemini=[gemini()])
            self.chat(route)
        self.assertNotIn(GROQ_KEY, repr(route.calls["gemini"]))
        self.assertEqual(route.calls["gemini"][0][1]["headers"], {"x-goog-api-key": GEMINI_KEY})

    def test_list_models_never_sends_the_groq_key_to_google(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = {"models": []}
        with mock.patch("requests.get", return_value=response) as get:
            self.assertEqual(list_models.main(["list_models.py", "gemini"]), 0)
        self.assertNotIn(GROQ_KEY, repr(get.call_args))
        self.assertEqual(get.call_args.kwargs["headers"], {"x-goog-api-key": GEMINI_KEY})

    def test_each_key_echoed_back_is_scrubbed_from_the_logs(self):
        route = Route(groq=[error(500, f"bad {GROQ_KEY}")], gemini=[error(403, f"bad {GEMINI_KEY} and {GROQ_KEY}")])
        with self.assertLogs("app", level="WARNING") as logs:
            response = self.chat(route)
        logged = "\n".join(logs.output)
        for key in (GROQ_KEY, GEMINI_KEY):
            self.assertNotIn(key, logged)
            self.assertNotIn(key, response.get_data(as_text=True))
        self.assertIn("bad ***", logged)

    def test_raw_error_text_from_either_provider_is_never_logged(self):
        route = Route(groq=[requests.ConnectionError(f"boom {GROQ_KEY}")], gemini=[requests.Timeout(f"boom {GEMINI_KEY}")])
        with self.assertLogs("app", level="WARNING") as logs:
            self.chat(route)
        logged = "\n".join(logs.output)
        self.assertNotIn("boom", logged)
        self.assertIn("ConnectionError", logged)
        self.assertIn("Timeout", logged)
