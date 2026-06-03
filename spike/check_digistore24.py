"""Verify the live Digistore24 API contract before building against it.

Read-only. Confirms: auth works, listMarketplaceEntries returns products,
and dumps the REAL field names (commission, earnings, auto-approve flag,
product id, promolink) so the engine maps to actual fields, not guesses.

SKIPs cleanly when the key is absent. Run:
    PYTHONPATH=.venv-libs:. python3 spike/check_digistore24.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

API_BASE = "https://www.digistore24.com/api/call"


def _load_key() -> str | None:
    # Read config/.env directly — don't import src.config (it validates other vars).
    env_path = Path(__file__).parent.parent / "config" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() in ("DIGISTORE", "DIGISTORE24_API_KEY"):
                return value.strip().strip('"').strip("'")
    return os.getenv("DIGISTORE") or os.getenv("DIGISTORE24_API_KEY")


def _call(key: str, function: str, **params) -> dict:
    headers = {"X-DS-API-KEY": key, "Accept": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(f"{API_BASE}/{function}", headers=headers, params=params)
    print(f"  HTTP {resp.status_code}  {resp.url}")
    try:
        return resp.json()
    except Exception:
        print("  (non-JSON response)")
        print("  " + resp.text[:500])
        return {}


def _dump_keys(obj, label: str) -> None:
    if isinstance(obj, dict):
        print(f"  {label} keys: {sorted(obj.keys())}")
    elif isinstance(obj, list) and obj:
        print(f"  {label} is a list of {len(obj)}; first item keys: "
              f"{sorted(obj[0].keys()) if isinstance(obj[0], dict) else type(obj[0])}")


def main() -> int:
    key = _load_key()
    if not key:
        print("SKIP: no Digistore24 key in config/.env (DIGISTORE=...)")
        return 0

    print(f"Key loaded: {key[:10]}…{key[-4:]}")

    # 1) Auth check via ping
    print("\n[1] ping (auth check)")
    ping = _call(key, "ping")
    print("  " + json.dumps(ping)[:300])
    if ping.get("result") != "success":
        print("  !! Auth failed — check the key / permissions.")
        # keep going; listMarketplaceEntries may still tell us something

    # 2) Marketplace discovery
    print("\n[2] listMarketplaceEntries (page_size=5)")
    mp = _call(key, "listMarketplaceEntries", page_size=5, page_no=1)
    print("  top-level: " + json.dumps({k: (v if not isinstance(v, (list, dict)) else f"<{type(v).__name__}>") for k, v in mp.items()}))
    data = mp.get("data", mp)
    # data may be {"marketplace_entries":[...]} or a list
    entries = None
    if isinstance(data, dict):
        _dump_keys(data, "data")
        for k, v in data.items():
            if isinstance(v, list) and v:
                entries = v
                print(f"  -> entries under data['{k}']")
                break
    elif isinstance(data, list):
        entries = data

    if entries:
        first = entries[0]
        print(f"\n  --- FIRST ENTRY ({len(entries)} returned) ---")
        print(json.dumps(first, indent=2)[:2500])
        if isinstance(first, dict):
            print("\n  FIELD NAMES present:", sorted(first.keys()))
            # Hunt for the fields we care about
            wanted = ("commission", "earn", "epc", "approv", "affiliate", "promo",
                      "product_id", "id", "name", "currency", "language", "price")
            hits = {k: first[k] for k in first if any(w in k.lower() for w in wanted)}
            print("\n  RELEVANT fields (commission/earnings/approve/promo/id/etc.):")
            print(json.dumps(hits, indent=2)[:1500])
    else:
        print("  !! No entries parsed — dumping raw response for inspection:")
        print(json.dumps(mp, indent=2)[:2000])

    print("\nDone. Inspect the field names above to finalize the engine mapping.")
    return 0


def probe():
    """Throwaway: try param variations + check what the key can see."""
    key = _load_key()
    if not key:
        print("SKIP")
        return
    print("\n=== getUserInfo (what is this account / permissions) ===")
    print(json.dumps(_call(key, "getUserInfo"), indent=2)[:1200])

    variations = [
        {"language": "en"},
        {"currency": "USD"},
        {"language": "en", "currency": "USD", "page_size": 5},
        {"sort_by": "commission_rate", "page_size": 5},
        {"data_index": 0, "page_size": 5},
        {"search_term": "", "page_size": 5},
    ]
    for v in variations:
        print(f"\n=== listMarketplaceEntries {v} ===")
        r = _call(key, "listMarketplaceEntries", **v)
        d = r.get("data", {})
        cnt = d.get("count") if isinstance(d, dict) else "?"
        n = len(d.get("entries", [])) if isinstance(d, dict) else 0
        print(f"  result={r.get('result')} count={cnt} entries_returned={n}")
        if n:
            print("  FIELDS:", sorted(d["entries"][0].keys()))
            break


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        sys.exit(main())
