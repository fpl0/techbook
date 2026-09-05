#!/usr/bin/env python3
"""
urlcheck.py — citation liveness for a techbook project.

Deep-research agents fabricate 3-13% of the URLs they cite, and 5-18% more do not
resolve; agents that cite more hallucinate at higher rates. Self-correction with a
liveness check has been measured to cut non-resolving URLs by 6-79x, to under 1%.
So every URL the book cites gets checked before publish.

A URL that 404s may still be a real source that moved, so a failure is checked
against the Wayback Machine: archived means "stale, find the new address",
never archived means "this source may never have existed".

Usage:
    urlcheck.py <book-dir> [--json] [--timeout 12] [--no-wayback]

Exit codes: 0 all live · 1 dead or unarchived URLs found · 2 bad invocation
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"

URL_RE = re.compile(r"https?://[^\s\)\]\}<>\"'`,]+")
TRAILING = ".,;:!?"


def collect(book: Path) -> dict[str, list[str]]:
    """url -> list of "file:line" where it appears."""
    found: dict[str, list[str]] = {}
    roots = [book / "src", book / "research"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() not in (".md", ".json", ".yaml", ".yml"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                for m in URL_RE.finditer(line):
                    url = m.group(0).rstrip(TRAILING)
                    found.setdefault(url, []).append(f"{path.relative_to(book)}:{n}")
    return found


def probe(url: str, timeout: int) -> tuple[int | None, str]:
    """HEAD, falling back to a ranged GET -- plenty of hosts reject HEAD."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={
            "User-Agent": UA,
            "Accept": "*/*",
            **({"Range": "bytes=0-2048"} if method == "GET" else {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, ""
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 406) and method == "HEAD":
                continue                      # try GET
            return e.code, e.reason or ""
        except urllib.error.URLError as e:
            return None, str(e.reason)
        except Exception as e:                # noqa: BLE001 - report, never crash
            return None, type(e).__name__
    return None, "unreachable"


def wayback(url: str, timeout: int) -> str | None:
    api = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    try:
        req = urllib.request.Request(api, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        snap = data.get("archived_snapshots", {}).get("closest", {})
        return snap.get("url") if snap.get("available") else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", type=Path)
    ap.add_argument("--timeout", type=int, default=12)
    ap.add_argument("--no-wayback", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    book = args.book.expanduser().resolve()
    if not book.is_dir():
        print(f"error: {book} is not a directory", file=sys.stderr)
        return 2

    urls = collect(book)
    if not urls:
        print("No URLs cited.")
        return 0

    print(f"Checking {len(urls)} cited URL(s)…\n")
    results: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(probe, u, args.timeout): u for u in urls}
        for fut in cf.as_completed(futures):
            u = futures[fut]
            status, detail = fut.result()
            ok = status is not None and 200 <= status < 400
            results[u] = {"status": status, "detail": detail, "ok": ok,
                          "where": urls[u], "archived": None}

    dead = [u for u, r in results.items() if not r["ok"]]
    if dead and not args.no_wayback:
        with cf.ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(wayback, u, args.timeout): u for u in dead}
            for fut in cf.as_completed(futures):
                results[futures[fut]]["archived"] = fut.result()

    live = [u for u, r in results.items() if r["ok"]]
    stale = [u for u in dead if results[u]["archived"]]
    ghost = [u for u in dead if not results[u]["archived"]]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"  live      {len(live):>4}")
        print(f"  stale     {len(stale):>4}  (dead now, but the archive has it)")
        print(f"  unfound   {len(ghost):>4}  (dead, and never archived)")
        if stale:
            print("\nStale — the source is real but the address moved. Replace the link.")
            print("─" * 66)
            for u in stale:
                r = results[u]
                print(f"  {u}\n      {r['status'] or r['detail']} · cited at {r['where'][0]}")
                print(f"      archived: {r['archived']}")
        if ghost:
            print("\nUnfound — dead and no archive record. Treat as possibly fabricated:")
            print("verify the source exists before citing it, or remove the claim.")
            print("─" * 66)
            for u in ghost:
                r = results[u]
                print(f"  {u}\n      {r['status'] or r['detail']} · cited at "
                      f"{', '.join(r['where'][:3])}")

    out = book / ".verify"
    out.mkdir(exist_ok=True)
    (out / "urls.json").write_text(json.dumps(results, indent=2))
    print()
    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())
