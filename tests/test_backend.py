"""Offline backend tests: the LLM call is faked, so no API key or network is needed.
Usage (from repo root):  python -m unittest tests.test_backend -v"""
import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as backend
from redflags import find_red_flag


def post(client, message, language="en", history=None):
    return client.post("/chat", json={"message": message, "language": language, "history": history or []})


class RedFlagTests(unittest.TestCase):
    def test_hits(self):
        for t in ["My father has chest pain", "having fever rashes and bloody colour urine",
                  "urine has blood", "bleeding gums and fever", "पेशाब में खून आ रहा है",
                  "ಮೂತ್ರದಲ್ಲಿ ರಕ್ತ ಬರುತ್ತಿದೆ", "मेरी माँ को सीने में दर्द हो रहा है"]:
            self.assertIsNotNone(find_red_flag(t), t)

    def test_no_false_positives(self):
        for t in ["I have a mild cough", "blood test was normal", "I gave blood yesterday, urine is fine",
                  "blood pressure and urine test done"]:
            self.assertIsNone(find_red_flag(t), t)


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.c = backend.app.test_client()

    def test_empty_message_is_400(self):
        r = post(self.c, "   ")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json(), {"error": "empty"})

    def test_red_flag_skips_llm(self):
        with mock.patch.object(backend, "call_llm") as llm:
            o = post(self.c, "My father has chest pain").get_json()
        llm.assert_not_called()
        self.assertEqual((o["type"], o["level"]), ("final", "RED"))
        self.assertEqual((o["specialty"], o["facility"]), ("emergency", "district_hospital"))

    def test_red_flag_in_history(self):
        with mock.patch.object(backend, "call_llm") as llm:
            o = post(self.c, "yes", history=[{"role": "user", "text": "chest pain since morning"},
                                             {"role": "bot", "text": "How old?"}]).get_json()
        llm.assert_not_called()
        self.assertEqual(o["level"], "RED")

    def test_question_passthrough(self):
        fake = {"type": "question", "reply": "How many days?", "level": None, "symptoms_en": ["fever"]}
        with mock.patch.object(backend, "call_llm", return_value=fake):
            o = post(self.c, "I have fever").get_json()
        self.assertEqual(o, {"type": "question", "reply": "How many days?", "level": None, "symptoms_en": ["fever"],
                             "language": "en"})

    def test_detected_language_and_specialty(self):
        fake = {"type": "final", "level": "AMBER", "reply": "x", "reason": "r", "advice": "a",
                "specialty": "Eye", "facility": "chc", "language": "hi"}
        with mock.patch.object(backend, "call_llm", return_value=fake):
            o = post(self.c, "aankh mein dard hai", "en").get_json()
        self.assertEqual((o["specialty"], o["facility"], o["language"]), ("eye", "chc", "hi"))

    def test_bad_specialty_and_facility_get_defaults(self):
        fake = {"type": "final", "level": "RED", "reply": "x", "reason": "r", "advice": "a",
                "specialty": "astrology", "facility": "phc", "language": "xx"}
        with mock.patch.object(backend, "call_llm", return_value=fake):
            o = post(self.c, "very unwell", "kn").get_json()
        # RED never sends people to a PHC; unknown values fall back
        self.assertEqual((o["specialty"], o["facility"], o["language"]), ("emergency", "district_hospital", "kn"))

    def test_final_bad_level_becomes_amber(self):
        fake = {"type": "final", "reply": "See PHC", "level": "yellow", "reason": "r", "advice": "a"}
        with mock.patch.object(backend, "call_llm", return_value=fake):
            o = post(self.c, "fever 3 days").get_json()
        self.assertEqual((o["type"], o["level"], o["symptoms_en"]), ("final", "AMBER", []))

    def test_llm_symptoms_trigger_red_override(self):
        fake = {"type": "final", "level": "GREEN", "reply": "ಸರಿ", "reason": "r", "advice": "a",
                "symptoms_en": ["blood in urine", "fever"]}
        with mock.patch.object(backend, "call_llm", return_value=fake):
            o = post(self.c, "ಜ್ವರ ಮತ್ತು ಕೆಂಪು ಮೂತ್ರ", "kn").get_json()
        self.assertEqual(o["level"], "RED")
        self.assertEqual(o["reply"], backend.RED_MSG["kn"])

    def test_garbage_llm_output_is_error(self):
        for fake in [{"type": "question", "reply": ""}, {"foo": 1}, ["x"]]:
            with mock.patch.object(backend, "call_llm", return_value=fake):
                o = post(self.c, "मुझे थकान है", "en").get_json()  # error text follows the typed language
            self.assertEqual(o, {"type": "error", "reply": backend.ERR_MSG["hi"]}, fake)

    def test_llm_exception_is_error(self):
        with mock.patch.object(backend, "call_llm", side_effect=RuntimeError("GEMINI_API_KEY missing")):
            o = post(self.c, "I feel tired", "ta").get_json()  # English typed -> English error
        self.assertEqual(o, {"type": "error", "reply": backend.ERR_MSG["en"]})

    def test_bad_history_and_language_are_tolerated(self):
        fake = {"type": "question", "reply": "?", "level": None}
        with mock.patch.object(backend, "call_llm", return_value=fake) as llm:
            r = self.c.post("/chat", json={"message": "hi", "language": "xx", "history": "oops"})
            self.assertEqual(r.status_code, 200)
            r = self.c.post("/chat", json={"message": "hi", "history": [1, None, {"role": "x"}, {"role": "user", "text": "a"}]})
            self.assertEqual(r.status_code, 200)
        self.assertEqual(llm.call_args.args[0], [{"role": "user", "text": "a"}])
        self.assertEqual(llm.call_args.args[2], "en")

    def test_non_json_body(self):
        r = self.c.post("/chat", data="not json", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_force_final_after_two_followups(self):
        fake = {"type": "final", "level": "GREEN", "reply": "rest", "reason": "r", "advice": "a"}
        hist = [{"role": "user", "text": "cold"}, {"role": "bot", "text": "Fever?"},
                {"role": "user", "text": "no"}, {"role": "bot", "text": "Cough?"}]
        with mock.patch.object(backend, "call_llm", return_value=fake) as llm:
            post(self.c, "little", history=hist[:2])
            self.assertFalse(llm.call_args.kwargs["force_final"])
            post(self.c, "little", history=hist)
            self.assertTrue(llm.call_args.kwargs["force_final"])

    def test_fenced_json_is_parsed(self):
        resp = mock.Mock()
        resp.json.return_value = {"candidates": [{"content": {"parts": [
            {"text": '```json\n{"type":"question","reply":"Age?"}\n```'}]}}]}
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), \
             mock.patch.object(backend.requests, "post", return_value=resp):
            out = backend.call_llm([], "fever", "en")
        self.assertEqual(out, {"type": "question", "reply": "Age?"})


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.c = backend.app.test_client()

    def test_script_lang(self):
        self.assertEqual(backend.script_lang("I have fever"), "latin")
        self.assertEqual(backend.script_lang("मुझे बुखार है"), "hi")
        self.assertEqual(backend.script_lang("ಜ್ವರ ಇದೆ"), "kn")
        self.assertIsNone(backend.script_lang("3"))

    def test_english_input_gets_english_red_message_even_if_kannada_selected(self):
        o = post(self.c, "My father has chest pain", "kn").get_json()
        self.assertEqual((o["reply"], o["language"]), (backend.RED_MSG["en"], "en"))

    def test_hindi_input_tells_llm_to_reply_in_hindi(self):
        fake = {"type": "question", "reply": "कितने दिन?", "symptoms_en": ["fever"]}
        with mock.patch.object(backend, "call_llm", return_value=fake) as llm:
            o = post(self.c, "मुझे बुखार है", "kn").get_json()
        self.assertIn("Reply ONLY in Hindi", llm.call_args.kwargs["rule"])
        self.assertEqual(o["language"], "hi")

    def test_english_input_rule_and_language_follow_the_reply(self):
        fake = {"type": "question", "reply": "How many days?", "symptoms_en": ["fever"], "language": "kn"}
        with mock.patch.object(backend, "call_llm", return_value=fake) as llm:
            o = post(self.c, "I have fever and headache", "kn").get_json()
        self.assertIn("reply ONLY in English", llm.call_args.kwargs["rule"])
        self.assertEqual(o["language"], "en")  # reply is English, so the UI must not stay on Kannada

    def test_short_answer_keeps_conversation_language(self):
        lang, rule = backend.reply_rule("yes", "hi")
        self.assertEqual(lang, "hi")
        self.assertIn("continue in Hindi", rule)


class ModelFallbackTests(unittest.TestCase):
    def test_quota_429_falls_through_to_next_model(self):
        def resp(code):
            r = mock.Mock(status_code=code)
            r.json.return_value = {"candidates": [{"content": {"parts": [{"text": '{"type":"question","reply":"Age?"}'}]}}]}
            r.raise_for_status.side_effect = None if code == 200 else RuntimeError(str(code))
            return r
        backend.EXHAUSTED.clear()
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), \
             mock.patch.object(backend, "MODELS", ["big", "lite"]), \
             mock.patch.object(backend.requests, "post", side_effect=[resp(429), resp(200), resp(200)]) as post:
            self.assertEqual(backend.call_llm([], "fever", "en")["reply"], "Age?")
            self.assertIn("/big:", post.call_args_list[0].args[0])
            self.assertIn("/lite:", post.call_args_list[1].args[0])
            backend.call_llm([], "fever", "en")  # 'big' is now skipped during its cooldown
            self.assertIn("/lite:", post.call_args_list[2].args[0])
        backend.EXHAUSTED.clear()

    def test_all_models_limited_raises(self):
        r = mock.Mock(status_code=429)
        r.raise_for_status.side_effect = RuntimeError("429")
        backend.EXHAUSTED.clear()
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), \
             mock.patch.object(backend, "MODELS", ["a", "b"]), \
             mock.patch.object(backend.requests, "post", return_value=r):
            with self.assertRaises(RuntimeError):
                backend.call_llm([], "fever", "en")
        backend.EXHAUSTED.clear()


class ProfileTests(unittest.TestCase):
    def test_summary_keeps_medical_facts_only(self):
        s = backend.profile_summary({"age": 64, "sex": "male", "conditions": ["diabetes", "high blood pressure"],
                                     "allergies": "penicillin", "medicines": "metformin", "name": "Appa", "phone": "98"})
        self.assertEqual(s, "age 64 years; sex male; long-term conditions: diabetes, high blood pressure; "
                            "allergies: penicillin; regular medicines: metformin")
        self.assertNotIn("Appa", s)

    def test_summary_rejects_junk(self):
        self.assertEqual(backend.profile_summary("x"), "")
        self.assertEqual(backend.profile_summary({"age": 999, "sex": "robot", "pregnant": "yes", "conditions": "x"}), "")
        self.assertEqual(backend.profile_summary({"pregnant": True, "sex": "female"}), "sex female; currently pregnant")

    def test_profile_reaches_llm_prompt(self):
        fake = {"type": "question", "reply": "?", "level": None}
        with mock.patch.object(backend, "call_llm", return_value=fake) as llm:
            self.c = backend.app.test_client()
            self.c.post("/chat", json={"message": "headache", "profile": {"age": 28, "sex": "female", "pregnant": True}})
        self.assertEqual(llm.call_args.kwargs["profile"], "age 28 years; sex female; currently pregnant")


class PlacesTests(unittest.TestCase):
    def test_place_specialties(self):
        self.assertEqual(backend.place_specialties({"name": "Sri Netra Eye Hospital"}), ["eye"])
        self.assertEqual(backend.place_specialties({"name": "Govt Hospital", "emergency": "yes",
                                                    "healthcare:speciality": "paediatrics;gynaecology"}),
                         ["child", "maternity", "emergency"])
        for n in ["Parent Care Center", "Resident Student Accident Clinic", "\u0ca8\u0cb0\u0cb8\u0cbf\u0c82\u0cb9 Hospital"]:
            self.assertEqual(backend.place_specialties({"name": n}), [], n)

    def test_classify(self):
        c = backend.classify_place
        self.assertEqual(c({"amenity": "hospital", "name": "Taluk General Hospital"}), ("govt", "govt_hospital"))
        self.assertEqual(c({"healthcare": "centre", "name": "Shivanahalli Primary Health Centre"}), ("govt", "phc"))
        self.assertEqual(c({"amenity": "clinic", "name": "CHC Pandavapura"}), ("govt", "chc"))
        self.assertEqual(c({"amenity": "hospital", "name": "Sri Nidhi Hospital"}), ("hospital", "hospital"))
        self.assertEqual(c({"amenity": "clinic", "name": "Tara Clinic"}), ("clinic", "clinic"))
        self.assertEqual(c({"amenity": "hospital", "name": "Mission Hospital", "operator:type": "charitable"}),
                         ("ngo", "charity_hospital"))
        self.assertEqual(c({"office": "ngo", "name": "Arogya Seva Trust"}), ("ngo", "ngo"))
        self.assertIsNone(c({"office": "ngo", "name": "Farmers Union"}))  # not health related

    def test_build_places_sorts_dedupes_and_skips_unnamed(self):
        els = [{"lat": 12.60, "lon": 76.90, "tags": {"amenity": "clinic", "name": "Far Clinic"}},
               {"lat": 12.52, "lon": 76.90, "tags": {"amenity": "hospital", "name": "Near Hospital", "phone": "0823"}},
               {"lat": 12.52, "lon": 76.90, "tags": {"amenity": "hospital", "name": "Near Hospital"}},
               {"type": "way", "center": {"lat": 12.53, "lon": 76.90}, "tags": {"amenity": "hospital"}}]
        out = backend.build_places(els, 12.52, 76.90)
        self.assertEqual([p["name"] for p in out], ["Near Hospital", "Far Clinic"])
        self.assertEqual(out[0]["distance_km"], 0.0)
        self.assertEqual(out[0]["phone"], "0823")

    def test_places_endpoint(self):
        c = backend.app.test_client()
        self.assertEqual(c.get("/places?lat=abc&lon=1").status_code, 400)
        self.assertEqual(c.get("/places?lat=95&lon=1").status_code, 400)
        backend.PLACES_CACHE.clear()
        found = [{"name": "PHC", "kind": "govt", "sub": "phc", "distance_km": 1.0}]
        with mock.patch.object(backend, "find_places", return_value=(found, 13)) as fp:
            r1 = c.get("/places?lat=12.52&lon=76.9").get_json()
            r2 = c.get("/places?lat=12.521&lon=76.901").get_json()  # same ~1 km cell -> cached
        self.assertEqual(r1, {"places": found, "radius_km": 13, "source": "OpenStreetMap"})
        self.assertEqual(r1, r2)
        self.assertEqual(fp.call_count, 1)
        with mock.patch.object(backend, "find_places", side_effect=RuntimeError("down")):
            self.assertEqual(c.get("/places?lat=13&lon=77").status_code, 502)

    def test_reverse(self):
        c = backend.app.test_client()
        self.assertEqual(c.get("/reverse?lat=x&lon=1").status_code, 400)
        resp = mock.Mock()
        resp.json.return_value = {"display_name": "long", "address": {
            "suburb": "Rajarajeshwari Nagar", "city": "Bengaluru", "state": "Karnataka"}}
        with mock.patch.object(backend.requests, "get", return_value=resp):
            self.assertEqual(c.get("/reverse?lat=12.9&lon=77.5").get_json(), {"name": "Rajarajeshwari Nagar, Bengaluru"})
        with mock.patch.object(backend.requests, "get", side_effect=RuntimeError("down")):
            self.assertEqual(c.get("/reverse?lat=12.9&lon=77.5").status_code, 502)

    def test_falls_back_to_nominatim(self):
        nom = [{"lat": 12.53, "lon": 76.9, "tags": {"healthcare": "centre", "name": "Urban Primary Health Centre"}}] * 1
        with mock.patch.object(backend, "overpass", side_effect=RuntimeError("timeout")), \
             mock.patch.object(backend, "nominatim_places", return_value=nom):
            found, km = backend.find_places(12.52, 76.9)
        self.assertEqual(found[0]["sub"], "phc")
        self.assertEqual(km, 33)  # fewer than 8 results -> widened


if __name__ == "__main__":
    unittest.main()
