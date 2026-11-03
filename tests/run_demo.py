"""Run the demo sentences through /chat and compare with expected level.
Usage (from repo root, venv active):  python tests/run_demo.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

c = app.test_client()
ok = 0
rows = [l for l in open("tests/demo_sentences.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
for line in rows:
    exp, lang, sentence = [p.strip() for p in line.split("|", 2)]
    r = c.post("/chat", json={"message": sentence, "language": lang, "history": []}).get_json()
    got = r.get("level") or ("QUESTION" if r.get("type") == "question" else r.get("type", "?").upper())
    # a first-turn follow-up question is acceptable for AMBER/GREEN cases
    good = got == exp or (exp != "RED" and got == "QUESTION")
    ok += good
    print(("PASS" if good else "FAIL"), f"exp={exp:5} got={got:8} [{lang}] {sentence}")
print(f"\n{ok}/{len(rows)} ok")
