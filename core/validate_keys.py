#!/usr/bin/env python3
"""
validate_keys.py
Deep key validation — tells you WHY each key failed and how to fix it.
"""

import os
import sys
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / "core" / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=str(env_path), override=True)
    print(f"[Validator] Loaded .env from: {env_path}")
except ImportError:
    pass


def check_key_format(name, key, expected_prefix):
    """Check if key has the correct prefix format."""
    if not key:
        return False, "Key is empty"
    if not key.startswith(expected_prefix):
        return False, f"Wrong prefix. Expected to start with '{expected_prefix}', got '{key[:10]}...'"
    if len(key) < 20:
        return False, f"Key too short ({len(key)} chars). Real keys are 30-60 chars."
    return True, "Format looks valid"


def test_groq_detailed():
    key = os.getenv("GROQ_API_KEY")
    print("\n" + "="*50)
    print("GROQ API")
    print("="*50)
    print(f"Key found: {'YES' if key else 'NO'}")
    if not key:
        return False

    ok, msg = check_key_format("Groq", key, "gsk_")
    print(f"Format check: {msg}")
    if not ok:
        print("FIX: Get a new key from https://console.groq.com/keys")
        print("     Keys start with 'gsk_' and are ~50 chars")
        return False

    try:
        payload = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5
        }).encode("utf-8")
        req = Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST"
        )
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ SUCCESS: {data['choices'][0]['message']['content'].strip()}")
            return True
    except HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}")
        if e.code == 401:
            print("   → Key is invalid or revoked. Generate a new one.")
        elif e.code == 403:
            print("   → Rate limit exceeded or key lacks permissions.")
            print("   → Free tier: check your usage at https://console.groq.com/")
        elif e.code == 429:
            print("   → Too many requests. Wait 1 minute and retry.")
        return False
    except Exception as e:
        print(f"❌ Network error: {e}")
        return False


def test_openrouter_detailed():
    key = os.getenv("OPENROUTER_API_KEY")
    print("\n" + "="*50)
    print("OPENROUTER API")
    print("="*50)
    print(f"Key found: {'YES' if key else 'NO'}")
    if not key:
        return False

    ok, msg = check_key_format("OpenRouter", key, "sk-or-")
    print(f"Format check: {msg}")
    if not ok:
        print("FIX: Get a new key from https://openrouter.ai/keys")
        print("     Keys start with 'sk-or-' and are ~60 chars")
        return False

    try:
        payload = json.dumps({
            "model": "deepseek/deepseek-r1:free",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5
        }).encode("utf-8")
        req = Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://neobrain.local",
                "X-Title": "NeoBrain"
            },
            method="POST"
        )
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ SUCCESS: {data['choices'][0]['message']['content'].strip()}")
            return True
    except HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}")
        if e.code == 401:
            print("   → Key is invalid or expired.")
            print("   → Go to https://openrouter.ai/keys and create a new one.")
            print("   → Make sure you're copying the KEY, not the KEY ID.")
        elif e.code == 402:
            print("   → Out of credits. Free tier gives $5-10 initial credit.")
            print("   → Check balance at https://openrouter.ai/credits")
        elif e.code == 429:
            print("   → Rate limited (20 req/min on free tier). Wait and retry.")
        return False
    except Exception as e:
        print(f"❌ Network error: {e}")
        return False


def test_moonshot_detailed():
    key = os.getenv("MOONSHOT_API_KEY")
    print("\n" + "="*50)
    print("MOONSHOT (KIMI) API")
    print("="*50)
    print(f"Key found: {'YES' if key else 'NO'}")
    if not key:
        return False

    ok, msg = check_key_format("Moonshot", key, "sk-")
    print(f"Format check: {msg}")
    if not ok:
        print("FIX: Get a new key from https://platform.moonshot.cn/")
        return False

    try:
        payload = json.dumps({
            "model": "moonshot-v1-8k",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5
        }).encode("utf-8")
        req = Request(
            "https://api.moonshot.cn/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST"
        )
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ SUCCESS: {data['choices'][0]['message']['content'].strip()}")
            return True
    except HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}")
        if e.code == 401:
            print("   → Key is invalid or expired.")
            print("   → Chinese platform: make sure account is verified.")
            print("   → Generate new key at https://platform.moonshot.cn/")
        return False
    except Exception as e:
        print(f"❌ Network error: {e}")
        return False


def test_serpapi_detailed():
    key = os.getenv("SERPAPI_API_KEY")
    print("\n" + "="*50)
    print("SERPAPI")
    print("="*50)
    print(f"Key found: {'YES' if key else 'NO'}")
    if not key:
        return False

    if len(key) < 20:
        print(f"❌ Key too short ({len(key)} chars)")
        print("FIX: Get key from https://serpapi.com/")
        return False

    try:
        url = f"https://serpapi.com/search.json?q=test&api_key={key}&num=1"
        req = Request(url, method="GET")
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            has_results = "organic_results" in data
            print(f"✅ SUCCESS: results={'YES' if has_results else 'NO'}")
            return True
    except HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}")
        if e.code == 401:
            print("   → Key is invalid.")
            print("   → Free tier: 100 searches/month. Check at https://serpapi.com/")
        return False
    except Exception as e:
        print(f"❌ Network error: {e}")
        return False


def main():
    print("="*60)
    print("  NEO API KEY VALIDATOR")
    print("  Deep diagnostics for failed keys")
    print("="*60)

    results = {
        "Groq": test_groq_detailed(),
        "OpenRouter": test_openrouter_detailed(),
        "Moonshot": test_moonshot_detailed(),
        "SerpAPI": test_serpapi_detailed(),
    }

    print("\n" + "="*60)
    print("  FINAL SUMMARY")
    print("="*60)

    for name, ok in results.items():
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")

    working = sum(results.values())
    print(f"\n  Working: {working}/{len(results)}")

    if working < len(results):
        print("\n  ACTION REQUIRED:")
        print("  1. Visit each failed service's key page")
        print("  2. Generate a BRAND NEW key (don't reuse old ones)")
        print("  3. Copy the FULL key (no extra spaces)")
        print("  4. Paste into core/.env (where your .env lives)")
        print("  5. Save and rerun this validator")

    print("\n" + "="*60)
    return working == len(results)


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)