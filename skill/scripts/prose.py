#!/usr/bin/env python3
"""
prose.py — the mechanical half of the slop pass.

A style ban stated in a prompt leaks: models told explicitly to avoid em dashes
have been measured still emitting them at 9.1 per thousand words. So the ban-list
in references/house-style.md is not self-enforcing, and this is the post-hoc check
that makes it real.

It reports; it never rewrites. Each hit names the pattern, quotes the line, and
gives file:line so the edit can be the minimum effective one.

Usage:
    prose.py <book-dir> [--only chNN] [--json] [--max-density N]

Exit codes: 0 clean · 1 findings · 2 bad invocation
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

# ── the ban-list, as checkable patterns ──────────────────────────────────────
# Each entry: (id, human name, compiled regex, note shown with the hit).
# Only patterns that can be matched without guessing intent live here; the
# judgement-heavy ones (synonym cycling, fake-profound kickers) stay human.

P = re.compile
PATTERNS: list[tuple[str, str, re.Pattern, str]] = [
    ("binary-contrast", "Binary contrast",
     P(r"\b(?:It'?s|This is|That'?s)\s+not\s+(?:just\s+)?[^.!?]{2,40}[.!?]\s+(?:It'?s|This is|That'?s)\s+",
       re.I), "\"It's not X. It's Y.\" — state the claim once."),
    ("throat-clearing", "Throat-clearing opener",
     P(r"(?m)^\s*(?:Here'?s the thing|Let'?s dive in|Let'?s get started|"
       r"Let'?s start by|Before we begin|Welcome to|In this (?:chapter|section),? we(?:'ll| will))",
       re.I), "Open on the subject, not on the act of opening."),
    ("faux-insight", "Faux-insight setup",
     P(r"\b(?:what most people (?:get wrong|don'?t (?:know|realise|realize))|"
       r"here'?s what (?:nobody|no one) tells you|the (?:dirty )?secret is)\b", re.I),
     "Assert the thing instead of advertising it."),
    ("colon-reveal", "Colon reveal",
     P(r"(?m)^[^:\n]{10,70}:\s+(?:a|an|the)\s+\w+(?:\s+\w+){0,2}\.\s*$", re.I),
     "The theatrical single-noun reveal. Fold it into the sentence."),
    ("trailing-ing", "Trailing -ing analysis",
     P(r",\s+(?:highlighting|showcasing|underscoring|demonstrating|emphasi[sz]ing|"
       r"illustrating|reflecting|revealing|cementing)\s+(?:the|its|their|a|an)\b", re.I),
     "A clause that comments on the sentence instead of continuing it."),
    ("puffery", "Importance puffery",
     P(r"\b(?:stands as a testament|a pivotal moment|game[- ]chang(?:er|ing)|"
       r"revolutionar(?:y|ise|ize)|cutting[- ]edge|state[- ]of[- ]the[- ]art|"
       r"best[- ]in[- ]class|paradigm shift|transformative)\b", re.I),
     "Say what it does; let the reader judge importance."),
    ("weasel-attribution", "Weasel attribution",
     P(r"\b(?:studies (?:show|have shown)|research (?:shows|suggests)|experts agree|"
       r"it'?s (?:widely|generally) (?:known|accepted|agreed)|many believe)\b", re.I),
     "Name the source or drop the claim."),
    ("fake-strong-verb", "Fake-strong verb",
     P(r"\b(?:serves as (?:a|the)|plays a (?:key|crucial|vital|major) role|"
       r"acts as (?:a|the) (?:central|centralized|centralised))\b", re.I),
     "Use the verb that describes the actual action."),
    ("negative-listing", "Negative listing",
     P(r"(?:^|[.!?]\s)Not\s+(?:a|an|just)?\s?[^.!?]{2,30}\.\s+Not\s+", re.I),
     "\"Not A. Not B. C.\" — a rhythm, not an argument."),
    ("rhetorical-setup", "Rhetorical setup",
     P(r"\b(?:what if I told you|here'?s where it gets (?:interesting|weird|fun)|"
       r"but wait,? there'?s more|you might be wondering)\b", re.I),
     "Ask a real question or make the statement."),
    ("summary-recap", "Summary-recap ending",
     P(r"(?m)^\s*(?:In (?:conclusion|summary)|To (?:sum up|summari[sz]e)|"
       r"In this (?:chapter|section),? we (?:saw|learned|covered|explored))\b", re.I),
     "State what is true, not what the chapter did."),
    ("banned-vocab", "Banned vocabulary",
     P(r"\b(?:delve|leverage[sd]?|leveraging|empower(?:s|ed|ing)?|streamline[sd]?|"
       r"robust|seamless(?:ly)?|unlock(?:s|ing)?|harness(?:es|ing)?|utili[sz]e[sd]?|"
       r"facilitate[sd]?|showcase[sd]?|underscore[sd]?|foster(?:s|ed|ing)?|"
       r"elevate[sd]?|embark|realm|tapestry|myriad|plethora)\b", re.I),
     "Plain-word replacements exist for every one of these."),
    ("empty-adverb", "Empty adverb",
     P(r"\b(?:just|simply|literally|honestly|basically|essentially|actually|"
       r"obviously|clearly|of course)\b\s+(?:the|a|an|it|this|that|you|we|is|are)\b", re.I),
     "Filler intensifier. Cut it and read the sentence again."),
    ("empty-phrase", "Empty phrase",
     P(r"\b(?:it'?s worth noting that|at the end of the day|needless to say|"
       r"it is important to (?:note|remember)|as we(?:'ve| have) seen|"
       r"when it comes to|in today'?s [\w\s-]{0,20}world|a wide (?:range|variety) of)\b",
       re.I), "Says nothing. Delete."),
    ("under-the-hood", "Overused metaphor",
     P(r"\b(?:under the hood|think of it as|at its core|the world of)\b", re.I),
     "Allowed sparingly; the density check below counts repeats."),
]

# Patterns above that are style-guide-allowed in small numbers rather than banned.
SOFT = {"under-the-hood"}


# ── craft checks ─────────────────────────────────────────────────────────────
# The ban-list above catches machine tells. These catch bad technical writing --
# the failures a competent editor marks up, which no amount of avoiding "delve"
# will fix. They are advisory counts, not absolutes: one is a choice, ten is a habit.

CRAFT: list[tuple[str, str, re.Pattern, str]] = [
    ("code-narration", "Narrating visible code",
     P(r"\b(?:as you can see|as we can see|what this (?:does|means) is|"
       r"this (?:function|method|loop|line|block|code|snippet) (?:simply |just )?"
       r"(?:does|loops|iterates|returns|takes|creates|defines)|"
       r"here we (?:define|create|call|set|add)|in the (?:above|below) (?:code|example))\b", re.I),
     "The reader can see the code. Explain why it is that way, or what breaks otherwise."),
    ("hedge-stack", "Stacked hedging",
     P(r"\b(?:might|may|could|can)\s+(?:possibly|potentially|sometimes|often|generally|"
       r"typically|usually)\b|\b(?:generally|typically|usually)\s+tends?\s+to\b", re.I),
     "Two hedges in one clause states less than one. Pick the honest degree of certainty."),
    ("nominalisation", "Nominalisation",
     P(r"\b(?:the ability to|make use of|perform (?:a|an|the) \w+ (?:of|on)|"
       r"carry out (?:a|an|the)|provide[sd]? (?:a|an|the) \w+ (?:of|for)|"
       r"is (?:responsible for|capable of))\b", re.I),
     "A verb hidden inside a noun. \"Make use of\" is \"use\"."),
    ("expletive-opener", "Empty opener",
     P(r"(?:^|[.!?]\s+)(?:There (?:is|are|was|were)|It (?:is|was) (?:important|worth|clear|"
       r"possible|necessary))\b"),
     "\"There are three ways\" delays the subject. Name it first."),
    ("passive-agentless", "Agentless passive",
     P(r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?"
       r"(?:called|used|handled|processed|performed|executed|considered|"
       r"implemented|represented|stored|returned|passed|added|created)\b(?!\s+by)", re.I),
     "Fine when the actor truly does not matter; a habit otherwise."),
    ("vague-quantifier", "Vague quantifier",
     P(r"\b(?:a (?:number|variety|range) of|several|various|numerous|quite a few|"
       r"many (?:of the )?(?:cases|times|ways)|some (?:of the )?(?:cases|situations))\b", re.I),
     "Give the number, or say why it is not known."),
    ("intensifier", "Intensifier doing the work",
     P(r"\b(?:very|extremely|incredibly|remarkably|highly|greatly|significantly|"
       r"dramatically|massively|hugely)\s+\w+", re.I),
     "If the noun needs propping up, choose a stronger noun."),
]


def sentence_openers(sents: list[str]) -> list[tuple[str, int]]:
    """First words that recur enough to be a rhythm the reader hears."""
    from collections import Counter
    firsts = Counter(s.split()[0].strip("\"'(").lower() for s in sents if s.split())
    return [(w, n) for w, n in firsts.most_common(6)
            if n >= 4 and w not in {"the", "a", "an", "it", "this", "that"}]


def long_runs(sents: list[str], limit: int = 25, run: int = 3) -> int:
    """Consecutive long sentences -- where readers actually lose the thread."""
    worst = cur = 0
    for s in sents:
        cur = cur + 1 if len(s.split()) > limit else 0
        worst = max(worst, cur)
    return worst if worst >= run else 0


# ── extracting prose ─────────────────────────────────────────────────────────

FENCE = re.compile(r"^\s{0,3}(```+|~~~+)")


TAGS = re.compile(r"<[^>]+>")
SVG_LINE = re.compile(r"^\s*<(?:svg|/svg|g|/g|path|rect|circle|line|polygon|text|"
                      r"marker|defs|/defs|/marker|title)\b", re.I)


def prose_lines(path: Path) -> list[tuple[int, str]]:
    """Every line the reader reads as prose.

    Callouts, orientation boxes, <details> answers and list items are prose even
    though they arrive wrapped in markup, so their text content is included with
    tags stripped. Skipping them was a blind spot that let a whole class of hits
    pass unseen. Fenced code, tables and SVG geometry are genuinely not prose.
    """
    out = []
    inside = False
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(raw):
            inside = not inside
            continue
        if inside:
            continue
        s = raw.strip()
        if not s or s.startswith("|") or SVG_LINE.match(s):
            continue
        # The terms line is a glossary with a mandated "term — definition" shape,
        # not prose, and a <summary> is a label, not a sentence.
        if re.match(r"^\*\*terms introduced", s, re.I):
            continue
        s = re.sub(r"<summary>.*?</summary>", " ", s, flags=re.I | re.S)
        s = re.sub(r"^#{1,6}\s+", "", s)              # heading text still counts
        s = re.sub(r"^[-*+]\s+|^\d+[.)]\s+", "", s)   # so does a list item
        s = re.sub(r"^>\s?", "", s)                   # and a blockquote
        s = TAGS.sub(" ", s).strip()                  # keep the words, drop the markup
        if not s:
            continue
        if "](" in s and len(re.sub(r"\[[^\]]*\]\([^)]*\)", "", s).strip()) < 12:
            continue
        out.append((n, s))
    return out


SENT = re.compile(r"[^.!?]+[.!?]+")


def sentences(text: str) -> list[str]:
    text = re.sub(r"`[^`]*`", "CODE", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return [s.strip() for s in SENT.findall(text) if len(s.split()) >= 3]


# ── the checks ───────────────────────────────────────────────────────────────

def analyse(book: Path, only: str | None) -> dict:
    chapters = sorted(p for p in (book / "src").glob("*.md")
                      if p.stem != "SUMMARY" and not p.name.endswith(".corrected"))
    if only:
        chapters = [p for p in chapters if only in p.stem]

    findings: list[dict] = []
    per_chapter: list[dict] = []
    all_sent_lengths: list[int] = []
    total_words = 0
    total_dashes = 0

    for ch in chapters:
        lines = prose_lines(ch)
        text = " ".join(s for _, s in lines)
        words = len(text.split())
        total_words += words

        for n, line in lines:
            for pid, name, rx, note in PATTERNS + CRAFT:
                for m in rx.finditer(line):
                    findings.append({
                        "chapter": ch.stem, "line": n, "id": pid, "name": name,
                        "hit": m.group(0).strip()[:70], "note": note,
                        "soft": pid in SOFT,
                        "craft": any(pid == c[0] for c in CRAFT),
                        "text": line[:120],
                    })

        dashes = text.count("—")
        total_dashes += dashes
        lens = [len(s.split()) for s in sentences(text)]
        all_sent_lengths += lens
        sents = sentences(text)
        per_chapter.append({
            "chapter": ch.stem, "words": words, "sentences": len(lens),
            "repeated_openers": sentence_openers(sents),
            "long_run": long_runs(sents),
            "em_dash_per_1k": round(dashes / words * 1000, 2) if words else 0,
            "mean_sentence": round(statistics.mean(lens), 1) if lens else 0,
            "stdev_sentence": round(statistics.pstdev(lens), 1) if len(lens) > 1 else 0,
        })

    return {
        "chapters": per_chapter,
        "findings": findings,
        "totals": {
            "words": total_words,
            "em_dash_per_1k": round(total_dashes / total_words * 1000, 2) if total_words else 0,
            "mean_sentence": round(statistics.mean(all_sent_lengths), 1) if all_sent_lengths else 0,
            "stdev_sentence": round(statistics.pstdev(all_sent_lengths), 1)
            if len(all_sent_lengths) > 1 else 0,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", type=Path)
    ap.add_argument("--only")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-density", type=float, default=1.0,
                    help="em dashes per 1000 words before it is flagged (default 1.0)")
    args = ap.parse_args()

    book = args.book.expanduser().resolve()
    if not (book / "src").is_dir():
        print(f"error: {book}/src does not exist", file=sys.stderr)
        return 2

    r = analyse(book, args.only)
    if args.json:
        print(json.dumps(r, indent=2))
        return 1 if r["findings"] else 0

    t = r["totals"]
    print(f"\nProse check · {t['words']:,} words")
    print("─" * 66)
    print(f"  em dashes per 1k words   {t['em_dash_per_1k']:>6}   "
          f"{'over budget' if t['em_dash_per_1k'] > args.max_density else 'ok'}"
          f" (budget {args.max_density})")
    print(f"  mean sentence length     {t['mean_sentence']:>6} words")
    print(f"  sentence-length stdev    {t['stdev_sentence']:>6}   "
          f"{'ROBOTIC — too uniform' if t['stdev_sentence'] < 5 else 'ok'} (want >= 5)")

    if len(r["chapters"]) > 1:
        print("\n  per chapter")
        for c in r["chapters"]:
            print(f"    {c['chapter']:<26} {c['words']:>5}w  "
                  f"dash/1k {c['em_dash_per_1k']:>5}  "
                  f"sent {c['mean_sentence']:>4}±{c['stdev_sentence']}")

    hard = [f for f in r["findings"] if not f["soft"] and not f.get("craft")]
    soft = [f for f in r["findings"] if f["soft"]]
    craft = [f for f in r["findings"] if f.get("craft")]

    if hard:
        print(f"\nBan-list hits ({len(hard)})")
        print("─" * 66)
        by_pattern: dict[str, list] = {}
        for f in hard:
            by_pattern.setdefault(f["name"], []).append(f)
        for name, hits in sorted(by_pattern.items(), key=lambda kv: -len(kv[1])):
            print(f"\n  {name}  ×{len(hits)}")
            print(f"    {hits[0]['note']}")
            for f in hits[:6]:
                print(f"    {f['chapter']}:{f['line']}  “{f['hit']}”")
            if len(hits) > 6:
                print(f"    … and {len(hits) - 6} more")

    if soft:
        print(f"\nUsed sparingly by design ({len(soft)}) — check they haven't accumulated")
        print("─" * 66)
        for f in soft:
            print(f"  {f['chapter']}:{f['line']}  “{f['hit']}”")

    if craft:
        print(f"\nCraft ({len(craft)}) — an editor's marks, not machine tells")
        print("─" * 66)
        by: dict[str, list] = {}
        for f in craft:
            by.setdefault(f["name"], []).append(f)
        for name, hits in sorted(by.items(), key=lambda kv: -len(kv[1])):
            print(f"\n  {name}  ×{len(hits)}")
            print(f"    {hits[0]['note']}")
            for f in hits[:5]:
                print(f"    {f['chapter']}:{f['line']}  “{f['hit']}”")
            if len(hits) > 5:
                print(f"    … and {len(hits) - 5} more")

    rhythm = []
    for c in r["chapters"]:
        for w, n in c.get("repeated_openers", []):
            rhythm.append(f"  {c['chapter']}: {n} sentences open with “{w}”")
        if c.get("long_run"):
            rhythm.append(f"  {c['chapter']}: {c['long_run']} long sentences in a row "
                          f"(over 25 words each)")
    if rhythm:
        print("\nRhythm — what the reader hears without noticing")
        print("─" * 66)
        for line in rhythm:
            print(line)

    over = t["em_dash_per_1k"] > args.max_density
    uniform = t["stdev_sentence"] < 5
    print()
    if hard or craft or over or uniform:
        print("Findings above. Apply the minimum effective edit — change the clause,")
        print("not the paragraph; a heavy rewrite loses the voice and adds fresh slop.")
        return 1
    print("Prose clean against the mechanical checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
