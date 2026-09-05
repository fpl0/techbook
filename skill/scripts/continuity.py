#!/usr/bin/env python3
"""
continuity.py — deterministic cross-chapter checks.

Long-range consistency is what language models are worst at, and it is not
fixable by prompting: chapter 1's details are diluted by the time chapter 8 is
written even when they are technically still in the context window. So this
checks the book against itself, mechanically, over metadata rather than prose --
which is what makes the result reproducible rather than another opinion.

What it catches:
  · a term used in prose before the chapter that introduces it
  · the same term introduced twice, in two different chapters
  · a reference to a chapter that does not exist
  · a number attributed to another chapter that does not appear there
  · a forward promise ("we add X in chapter 5") that chapter 5 never delivers

Usage:
    continuity.py <book-dir> [--json]

Exit codes: 0 clean · 1 findings · 2 bad invocation
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

FENCE = re.compile(r"^\s{0,3}(```+|~~~+)")
TAGS = re.compile(r"<[^>]+>")
TERMS_LINE = re.compile(r"\*\*Terms introduced:?\*\*\s*(.+)", re.I | re.S)
CHAPTER_REF = re.compile(r"\bchapter\s+(\d+)\b", re.I)
NUMBER = re.compile(r"\b(\d+(?:[.,]\d+)?)\b")

# Words that look like terms but carry no meaning as glossary entries.
STOP = {"the", "a", "an", "and", "or", "of", "in", "to", "for", "with", "this", "that"}


@dataclass
class Chapter:
    stem: str
    number: int
    title: str
    prose: str
    lines: list = field(default_factory=list)     # (lineno, text)
    outputs: str = ""
    terms: list = field(default_factory=list)


def load(book: Path) -> list[Chapter]:
    chapters = []
    for path in sorted((book / "src").glob("*.md")):
        if path.stem == "SUMMARY" or path.name.endswith(".corrected"):
            continue
        raw = path.read_text(encoding="utf-8")
        nm = re.match(r"^ch(\d+)", path.stem)
        number = int(nm.group(1)) if nm else len(chapters) + 1
        tm = re.search(r"^#\s+(.*)$", raw, re.M)
        title = re.sub(r"^Chapter\s+\d+[:.]?\s*", "", tm.group(1).strip()) if tm else path.stem

        prose_lines, outputs, inside, lang = [], [], False, ""
        for n, ln in enumerate(raw.splitlines(), 1):
            f = FENCE.match(ln)
            if f:
                if not inside:
                    lang = ln.strip().lstrip("`~").strip()
                inside = not inside
                continue
            if inside:
                if lang.startswith("output"):
                    outputs.append(ln)
                continue
            s = TAGS.sub(" ", ln).strip()
            if s:
                prose_lines.append((n, s))

        terms: list[str] = []
        m = TERMS_LINE.search(raw)
        if m:
            chunk = TAGS.sub(" ", m.group(1)).split("**")[0]
            for t in re.split(r",|;", chunk):
                t = t.strip().strip(".").strip()
                t = re.sub(r"^and\s+", "", t, flags=re.I)
                if t and len(t) > 2 and t.lower() not in STOP:
                    terms.append(t)

        chapters.append(Chapter(path.stem, number, title,
                                " ".join(s for _, s in prose_lines),
                                prose_lines, "\n".join(outputs), terms))
    return sorted(chapters, key=lambda c: c.number)


def check(chapters: list[Chapter]) -> list[dict]:
    findings: list[dict] = []
    by_number = {c.number: c for c in chapters}
    max_ch = max(by_number) if by_number else 0

    # ── terminology ──────────────────────────────────────────────────────────
    introduced: dict[str, Chapter] = {}
    for ch in chapters:
        for t in ch.terms:
            key = t.lower()
            if key in introduced and introduced[key].number != ch.number:
                findings.append({
                    "kind": "term-introduced-twice", "chapter": ch.stem, "line": 0,
                    "detail": f"“{t}” is listed as introduced in both "
                              f"{introduced[key].stem} and {ch.stem}. One of them is "
                              f"re-teaching a term the reader already has.",
                })
            introduced.setdefault(key, ch)

    for term, owner in introduced.items():
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.I)
        for ch in chapters:
            if ch.number >= owner.number:
                continue
            for n, line in ch.lines:
                if "Terms introduced" in line:
                    continue
                if pattern.search(line):
                    findings.append({
                        "kind": "term-used-before-introduced", "chapter": ch.stem,
                        "line": n,
                        "detail": f"“{term}” is used here, but {owner.stem} is the "
                                  f"chapter that introduces it. Either define it on "
                                  f"first use or move the term.",
                    })
                    break

    # ── chapter references ───────────────────────────────────────────────────
    for ch in chapters:
        for n, line in ch.lines:
            for m in CHAPTER_REF.finditer(line):
                target = int(m.group(1))
                if target not in by_number:
                    findings.append({
                        "kind": "dangling-chapter-ref", "chapter": ch.stem, "line": n,
                        "detail": f"refers to chapter {target}, but the book has "
                                  f"{max_ch} chapters.",
                    })
                    continue

                # A number attributed to another chapter has to appear there.
                if target != ch.number:
                    other = by_number[target]
                    haystack = other.prose + "\n" + other.outputs
                    for num in NUMBER.finditer(line):
                        v = num.group(1)
                        if v == m.group(1) or len(v) < 2:
                            continue
                        if v not in haystack:
                            findings.append({
                                "kind": "cross-chapter-number", "chapter": ch.stem,
                                "line": n,
                                "detail": f"attributes “{v}” to chapter {target}, but "
                                          f"{v} does not appear in {other.stem}. "
                                          f"Recompute it from that chapter's real output.",
                            })

                # A forward reference is a promise. Check the target mentions it.
                if target > ch.number:
                    subject = [w for w in re.findall(r"\b[a-z]{5,}\b", line.lower())
                               if w not in {"chapter", "which", "where", "there",
                                            "these", "those", "about", "after",
                                            "before", "again", "still", "until"}]
                    other = by_number[target]
                    hay = other.prose.lower()
                    if subject and not any(w in hay for w in subject[:6]):
                        findings.append({
                            "kind": "unkept-promise", "chapter": ch.stem, "line": n,
                            "detail": f"promises something of chapter {target}, but "
                                      f"{other.stem} does not mention any of "
                                      f"{', '.join(subject[:4])}.",
                        })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    book = args.book.expanduser().resolve()
    if not (book / "src").is_dir():
        print(f"error: {book}/src does not exist", file=sys.stderr)
        return 2

    chapters = load(book)
    if not chapters:
        print("error: no chapters found", file=sys.stderr)
        return 2
    findings = check(chapters)

    if args.json:
        print(json.dumps({"chapters": [c.stem for c in chapters],
                          "findings": findings}, indent=2))
        return 1 if findings else 0

    print(f"\nContinuity · {len(chapters)} chapters, "
          f"{sum(len(c.terms) for c in chapters)} terms declared")
    print("─" * 66)
    for c in chapters:
        print(f"  {c.number:>2}  {c.title:<32} {len(c.terms):>2} terms")

    if not findings:
        print("\nNo cross-chapter inconsistencies found.")
        return 0

    order = ["cross-chapter-number", "term-used-before-introduced",
             "dangling-chapter-ref", "term-introduced-twice", "unkept-promise"]
    LABEL = {
        "cross-chapter-number": "Numbers attributed to another chapter",
        "term-used-before-introduced": "Terms used before they are introduced",
        "dangling-chapter-ref": "References to chapters that do not exist",
        "term-introduced-twice": "Terms introduced twice",
        "unkept-promise": "Promises the target chapter may not keep",
    }
    for kind in order:
        hits = [f for f in findings if f["kind"] == kind]
        if not hits:
            continue
        print(f"\n{LABEL[kind]} ({len(hits)})")
        print("─" * 66)
        for f in hits[:10]:
            where = f"{f['chapter']}:{f['line']}" if f["line"] else f["chapter"]
            print(f"  {where}  {f['detail']}")
        if len(hits) > 10:
            print(f"  … and {len(hits) - 10} more")

    print("\nThe last category is advisory — a promise can be kept in words the")
    print("checker cannot match. The first three are not.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
