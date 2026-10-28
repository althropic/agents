"""
Health-check script for Ollama API keys.

Reads keys from assets/keys.txt (one per line), sends a minimal
chat completion request to https://ollama.com/v1/chat/completions
for each key, and reports the result.

Requires httpx (not in requirements.txt — scripts-only dependency):
    pip install httpx

Usage (from project root, conda env active):
    python scripts/check_keys.py
    python scripts/check_keys.py --model nemotron-3-ultra
    python scripts/check_keys.py --workers 5
"""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
from pathlib import Path

import httpx

KEYS_FILE = Path(__file__).parent.parent / "assets" / "keys.txt"
ENDPOINT = "https://ollama.com/v1/chat/completions"
DEFAULT_MODEL = "nemotron-3-ultra"
DEFAULT_WORKERS = 8

# Minimal payload — 1 token in, 1 token out, no thinking.
def _payload(model: str) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
        "stream": False,
    }


def check_key(key: str, model: str) -> tuple[str, int, str]:
    """Return (key_prefix, status_code, label)."""
    prefix = key[:12] + "..."
    try:
        r = httpx.post(
            ENDPOINT,
            json=_payload(model),
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        code = r.status_code
        if code == 200:
            label = "OK"
        elif code == 401:
            label = "INVALID (401)"
        elif code == 403:
            label = "FORBIDDEN (403)"
        elif code == 429:
            label = "RATE LIMITED (429)"
        elif code == 404:
            label = "MODEL NOT FOUND (404)"
        else:
            label = f"ERROR ({code})"
        return prefix, code, label
    except httpx.TimeoutException:
        return prefix, 0, "TIMEOUT"
    except Exception as exc:  # noqa: BLE001
        return prefix, 0, f"EXCEPTION: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Ollama API key health")
    parser.add_argument(
        "--file", default=str(KEYS_FILE),
        help="Path to keys file. Supports plain values or 'key_N  <value>' format.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to test against")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel workers")
    args = parser.parse_args()

    keys_path = Path(args.file)
    if not keys_path.exists():
        print(f"Keys file not found: {keys_path}", file=sys.stderr)
        sys.exit(1)

    # Supports both plain-value lines and "key_N  <value>" format.
    keys = []
    for line in keys_path.read_text().splitlines():
        line = line.strip()
        if line:
            keys.append(line.split()[-1])  # last token is always the key value

    print(f"Testing {len(keys)} keys against {ENDPOINT}")
    print(f"Model: {args.model}  |  Workers: {args.workers}\n")

    results: list[tuple[str, int, str]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(check_key, k, args.model): k for k in keys}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            prefix, code, label = future.result()
            results.append((prefix, code, label))
            print(f"  [{i:>3}/{len(keys)}] {prefix}  {label}")

    # Summary
    ok      = [r for r in results if r[1] == 200]
    dead    = [r for r in results if r[1] == 403]
    invalid = [r for r in results if r[1] == 401]
    limited = [r for r in results if r[1] == 429]
    other   = [r for r in results if r[1] not in (200, 401, 403, 429)]

    print(f"\n{'='*50}")
    print(f"  OK            : {len(ok)}")
    print(f"  Rate limited  : {len(limited)}")
    print(f"  Forbidden 403 : {len(dead)}")
    print(f"  Invalid 401   : {len(invalid)}")
    print(f"  Other/timeout : {len(other)}")
    print(f"{'='*50}")

    if ok:
        print(f"\n[PASS] {len(ok)} working key(s) found")
    else:
        print("\n[FAIL] No working keys found")
        sys.exit(1)


if __name__ == "__main__":
    main()
