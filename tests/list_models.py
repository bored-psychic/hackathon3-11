"""Print the model ids a provider offers right now, one per line. Never prints the key.
Usage (from repo root, venv active):  python tests/list_models.py [groq|openrouter|gemini]
Without an argument it uses the provider the app would use. To see only OpenRouter's free
models:  python tests/list_models.py openrouter | grep ':free$'"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import GEMINI_BASE, OPENAI_COMPATIBLE, LlmConfigError, llm_api_key, llm_provider, scrubbed_error_text  # noqa: E402


def model_ids(provider):
    """Returns (ids, None), or ([], text for stderr) if the provider refused."""
    key = llm_api_key(provider)
    if provider == "gemini":
        base, headers = GEMINI_BASE, {"x-goog-api-key": key}
    else:
        base, headers = OPENAI_COMPATIBLE[provider]["base"], {"Authorization": f"Bearer {key}"}
    r = requests.get(f"{base}/models", headers=headers, timeout=20)
    if r.status_code != 200:
        return [], f"HTTP {r.status_code} {scrubbed_error_text(r)}".strip()
    payload = r.json()
    if provider == "gemini":
        return sorted(m["name"].removeprefix("models/") for m in payload["models"]), None
    return sorted(m["id"] for m in payload["data"] if m.get("active", True)), None


def main(argv):
    provider = argv[1].strip().lower() if len(argv) > 1 else llm_provider()
    if provider != "gemini" and provider not in OPENAI_COMPATIBLE:
        print("provider must be groq, openrouter or gemini", file=sys.stderr)
        return 2
    try:
        ids, problem = model_ids(provider)
    except LlmConfigError as e:
        ids, problem = [], str(e)
    except requests.RequestException as e:
        ids, problem = [], type(e).__name__  # never print a raw requests error
    if problem:
        print(problem, file=sys.stderr)
        return 1
    print("\n".join(ids))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
