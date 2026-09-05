# Outline — A Regex Engine From Scratch

Depth: brief. Four chapters, 1,600–2,200 words each, 4–7 verified listings each.
Built bottom-up from `research/notes/`: every key point names the note (B =
backtracking.md, P = parse-and-compile.md, S = simulation-and-engines.md) and
section that backs it. The spine code already exists and runs under
`code/`; chapters embed those files with `file=` and never retype them.

Shared conventions for every writer:
- Listings that are whole files use `file=code/<name>.py` and must match the
  file byte for byte (`verify.py` checks). Demo listings that *use* the files
  are plain `run` blocks that `import` them; `code/` is on the import path.
- Timing listings are `run nondet=output` and show the numbers from the
  author's own run, with machine and Python version stated once in chapter 1.
- Terms line format: `**Terms introduced:** term — definition; term — definition.`
- Cite with a Markdown link on first mention; the URL must be one from the notes.
- Refer to listings by number ("Listing 2-3"), never "the code above".
- Machine for numbers: Apple Silicon Mac, CPython 3.14, single run best-of-three.

---

## Chapter 1 — Matching by Hand

**Job.** Build a working regex matcher in thirty lines, by recursion, and make
the reader *feel* the cliff a backtracking matcher falls off.

**Reader on entry.** Uses regexes weekly; believes a regex is "a string that gets
matched against another string", has never thought about what does the
matching; believes slowness is about input size only.

**Crux.** A pattern can describe a text in more than one way. When the first
way fails, who remembers the others, and how many are there?

**Sections and budgets (total ≈ 1,900 words).**
1. *Hook* (150): Listing 1-1, `code/blowup.py`, `run nondet=output`: Python's
   own `re` on `(a+)+b` against `"a"*n`, time doubling per character (B §4:
   ×1.9–2.0 per char, n=24 ≈ 0.48 s on the researcher's machine; use your own
   numbers). State machine/Python once.
2. *Orientation box* (80) + *Crux* box (60).
3. *The smallest language worth building* (250): literal, `.`, concatenation,
   `*`. Table of the four. Why so few: Kernighan's "95 percent" remark is a
   personal estimate, quote it as such (B §1). Alternation, `+`, `?` and
   groups arrive in chapter 2.
4. *Matching, recursively* (450): Listing 1-2, `file=code/backtrack.py`. Purpose
   sentence before; after: why `match_here` asks only "does the pattern start
   here", why `match_star` tries the longest run first then gives back (note
   honestly: Pike's original tries zero first, "shortest match", B §1; ours
   follows Python's greedy `*`). Annotated list ①②③ keyed to lines. Two `run`
   demos (Listing 1-3) importing `backtrack` and printing results for `a*b`,
   `.*c`, `search`. Predict checkpoint: `match_here("a*a", "aaa")`?
5. *Where the time goes* (400): the timeline of `a*a*a*b` against `aaaa`:
   each star hands back one character at a time; nested loops of give-backs.
   Diagram 1-1: the give-back tree for `a*a*b` on `aaa` (six boxes max).
   Listing 1-4, `run nondet=output`: time `backtrack.match_here("a*a*a*b",
   "a"*n)` for n = 40, 80, 160, 320 (the researcher measured ×8 per doubling:
   cubic). Say plainly: this is polynomial, not exponential. Exponential
   needs a *nested* quantifier, which this language cannot yet express (B §4;
   Davis 2018: star height > 1, B §2).
6. *The incidents* (250): Stack Overflow 2016 (`\s+$`, 20,000 spaces,
   199,990,000 steps, "not classic catastrophic backtracking … O(n²)",
   34 minutes, B §2) and Cloudflare 2019 (`.*.*=.*`, 27 minutes, the post never
   says "exponential", steps 23→555 for 1→20 x's, B §2). Both polynomial. The
   lesson is that quadratic on a hot path is enough. Cite both post-mortems
   (use the Wayback link for Stack Overflow, `urlcheck` shows the live one 403s).
7. *Misconception callout* (100): "the input is short so it is safe" — the
   input length that matters is the failing suffix; `(a+)+b` on 24 a's is
   24 characters. `expect-error` Listing 1-5: `match_here("a"*1500, "a"*1500)`
   raises `RecursionError` (recursion depth = pattern length); real limit of
   the recursive design, and the honest cost of recursion.
8. *Practice* (200): four rungs. (1) fill one blank: add `^` anchor handling to
   `search`. (2) stub: implement `+` for a single character by rewriting `x+`
   as `xx*`. (3) blank slate: count the number of `match_here` calls for
   `a*a*b` on `"a"*n` for n=1..8 and state the growth. (4) transfer: where else
   does "try the longest first, then give back" appear (parsers, allocators)?
9. *Mental model* (120): diagram-free recap, 5 bullets; terms.
10. *One opinion* (80): I think every regex tutorial should start with
    `(a+)+b` and a stopwatch, not with `\d{3}-\d{4}`.
11. *Going deeper* (80, annotated): Kernighan's Beautiful Code chapter (the
    original 30 lines and why they are beautiful); Cox 2007 (the graph); Davis
    et al. 2018 (how common this is: ~1% of regexes in npm/pypi, most
    polynomial).
12. *Next* (30): "The matcher forgets every path it abandoned. Chapter 2
    builds a machine that can hold them all."

**Listings planned.** 1-1 blowup.py (run nondet=output); 1-2 backtrack.py
(file=); 1-3 demos (run); 1-4 timing (run nondet=output); 1-5 RecursionError
(expect-error, expect="RecursionError").
**Spine increment.** `tinyre` gains `backtrack.py`, the reference matcher the
later chapters race against.
**Terms introduced.** backtracking; match_here; give back (of a star); star
height; catastrophic backtracking; polynomial blow-up.

---

## Chapter 2 — From Pattern to Machine

**Job.** Turn the pattern string into a tree, then into a graph of states in
which "either of these" is a first-class thing, and show that the graph has
exactly one state per character of the pattern.

**Reader on entry.** Can write and trace the recursive matcher; believes the
pattern string *is* the program; has no word for "a state that is in two
places at once".

**Crux.** A string can only say one thing at a time. `a|b` needs something that
can say "both, right now". What is the smallest such thing?

**Sections and budgets (total ≈ 2,100 words).**
1. *Hook* (150): the chapter-1 matcher re-reads the pattern on every call and
   cannot express `(ab)*` at all; a real engine compiles once and matches
   many times (P §2: Thompson 1968 compiled to IBM 7094 machine code — quote
   the abstract).
2. *Orientation* (80), *Warm-up* (2 questions on ch. 1: why cubic not
   exponential; what `match_star` gives back) (80), *Crux* (60).
3. *A tree first* (400): the eight constructs; precedence alternation <
   concatenation < repetition, cite POSIX §9.4.8 and Cox's one sentence (P §1).
   Listing 2-1 `file=code/nodes.py` (why one dataclass per construct; why
   `Repeat` carries `min` and `many` instead of three classes). Listing 2-2
   `file=code/parse.py`: recursive descent, one method per precedence level;
   Nystrom's line that recursive descent powers GCC and V8 (P §4). Location
   hints not needed (new files). Listing 2-3 `run`: parse `(a|b)*c` and print
   the tree. Predict: what tree does `ab|c` give, and `a(b|c)`?
   Misconception `expect-error` Listing 2-4: `parse("a(b")` raises
   SyntaxError "missing )". Also mention: a second quantifier is rejected
   ("multiple repeat"), exactly as `re` rejects `a**` — and that `a+?` means
   something else in Python (lazy), which is why we refuse it rather than
   guess (S §7 dialect caveat; chapter 4 shows the test that found this).
4. *The machine* (450): states with one arrow (character) and states with two
   arrows and no character (split). Cox's `struct State` (P §2) and Thompson's
   NNODE/CNODE (P §2). Diagram 2-1: the two kinds of state. Listing 2-5
   `file=code/machine.py`: continuation style, "each node is compiled knowing
   what comes after it, so no dangling pointer is ever patched"; attribute the
   two-endpoint idea to Jules Jacobs' note (P §3) and say the name
   "continuation style" is ours. Walk the five cases; the star case allocates
   the split first because the loop needs it to exist.
5. *Thompson's construction, one operator at a time* (400): Diagram 2-2:
   fragments for `ab`, `a|b`, `a*`, `a+`, `a?` (five small panels or one
   figure). Cox's exact per-operator prose (P §2). Listing 2-6 `run`: compile
   `(a|b)*c`, walk the graph, print each state as `Char('a') -> …`; predict
   checkpoint: how many states for `a*a*a*b`?
6. *The size guarantee* (250): Cox's quote "exactly one state per character or
   metacharacter … excluding parentheses" (P §2). Listing 2-7 `run`: count
   states for six patterns and print alongside the non-paren character count;
   the numbers must show count = chars + 1 (the match state). Why this matters
   in chapter 3: the set of live states can never exceed m.
7. *Aside* (100): Thompson's `a**` loop remark and his two ways out (P §5) —
   the cycle chapter 3 must survive.
8. *Practice* (200): (1) blank: add `Repeat` printing to a tree pretty-printer;
   (2) stub: extend `atom` to accept an escaped character `\.`; (3) blank
   slate: write `count_states` without recursion; (4) transfer: where else is
   "compile once, run many" the reason for a two-stage design?
9. *Mental model* (120): recap + terms.
10. *One opinion* (80): the continuation-style compiler is the version to teach;
    the patch-list version in Cox's C is the version to *read*, because it is
    the one in the 1968 paper.
11. *Going deeper* (80): Thompson 1968 (PDF mirror); Cox regexp1
    (the C, ~200 lines); Matt Might's recursive-descent grammar; Dragon book
    §3.7 for the textbook (2n) bound.
12. *Next* (30).

**Listings.** 2-1 nodes.py; 2-2 parse.py; 2-3 parse demo; 2-4 SyntaxError
(expect-error, expect="missing"); 2-5 machine.py; 2-6 graph walk; 2-7 state
counts.
**Spine increment.** `nodes.py`, `parse.py`, `machine.py`.
**Terms introduced.** abstract syntax tree; recursive descent; precedence
level; state; split state; match state; fragment; Thompson's construction;
continuation style.

---

## Chapter 3 — All Paths at Once

**Job.** Run the machine so that every alternative is explored simultaneously,
prove by measurement that the time is proportional to the input, and show the
one bug this design invites.

**Reader on entry.** Can compile a pattern to states and count them; still
thinks of matching as "try one path, come back".

**Crux.** The pattern has at most m states. If we never hold more than m of
them at once, how can the work per character be anything but bounded?

**Sections and budgets (total ≈ 2,000 words).**
1. *Hook* (150): Thompson 1968: "each character in the text to be searched is
   examined in sequence against a list of all possible current characters"
   (S §1 / B §1). Contrast with chapter 1's forgetting.
2. *Orientation* (80), *Warm-up* (80, back to ch. 1 and 2), *Crux* (60).
3. *Following the split arrows* (400): epsilon closure in plain words: a split
   costs nothing to pass through, so pass through it *now*. Listing 3-1
   `file=code/simulate.py`, annotate `add_state`, `step`, `fullmatch`,
   `search`. Why `seen` is a set of `id(s)`. Cox's `listid` generation trick
   as the C equivalent (S §2). Diagram 3-1, a timeline: the live set of
   `(a|b)*c` over the input `abc`, one row per character (S §1; OSTEP's
   "show behaviour over time").
4. *Why it is linear* (300): Cox's quote "in the worst case the NFA might be in
   every state at each step … constant amount of work independent of the
   length of the string" (S §1); O(n·m). Listing 3-2 `file=code/tinyre.py`, the
   public API. Listing 3-3 `run nondet=output` = `code/bench.py`: the table
   backtrack vs tinyre vs `re` on `a*a*a*b` for n=40…320 (researcher's
   numbers: 855 ms vs 0.31 ms vs 5.1 ms at 320; **use your own**). Say what
   the table does and does not show: `re` is also polynomial here, and tinyre
   beats it at 320 on this one pattern only because `re` backtracks; on `a*b`
   `re` wins by a wide margin (measure it: `a*b` at n=800,000 is 0.6 ms in
   `re`, B §4).
5. *The cycle* (350): `(a*)*b`. Without `seen`, `add_state` follows the split
   back to itself forever. Listing 3-4 `expect-error`: a copy of `add_state`
   with the `seen` check removed, run on `(a*)*b` → RecursionError. Thompson
   saw it in 1968 and rewrote `a**` as `λ|aa*(aa*)*` (P §5); Cox's generation
   marker; RE2 rewrites star-of-nullable as `(a+)?` for priority reasons (P
   §5). Misconception callout: "the set makes duplicates harmless" — true for
   states, and it is also what terminates the cycle; the two are the same fact.
6. *What the set forgets* (250): the set records *which* states are live, not
   *how* they got there. That is exactly why captures need a different design
   (Pike's VM, threads carry saved positions, S §3) and why backreferences
   cannot be done this way at all (NP-complete, Cox's phrasing, S §3). One
   paragraph each; chapter 4 returns to this.
7. *Practice* (200): (1) blank: make `fullmatch` return the number of steps;
   (2) stub: `search` that reports the end position of the first match;
   (3) blank slate: `findall` for non-overlapping matches (leftmost, then
   longest, explain the choice); (4) transfer: where else does "set of live
   states" appear (BFS over a graph, lexer generators).
8. *Mental model* (120): recap + terms.
9. *One opinion* (80): teach the set simulation before the DFA; the DFA is the
   set simulation with memoisation and the reader should see the thing being
   memoised first.
10. *Going deeper* (80): Cox regexp1 §"Caching the NFA to build a DFA"; Cox
    regexp2 (Pike VM, captures); Gallant's regex internals (the engine ladder).
11. *Next* (30).

**Listings.** 3-1 simulate.py; 3-2 tinyre.py; 3-3 bench (run nondet=output,
timeout=120); 3-4 cycle (expect-error, expect="RecursionError"); plus one or
two small `run` demos of `tinyre.fullmatch`/`search`.
**Spine increment.** `simulate.py`, `tinyre.py`, `bench.py`.
**Terms introduced.** live set; epsilon closure; simulation; step; unanchored
search; Pike VM.

---

## Chapter 4 — Making It Trustworthy

**Job.** Test `tinyre` against Python's `re` exhaustively on small cases, show a
real mismatch the test found and how it was resolved, and say honestly what the
engine gave up and where the production engines go from here.

**Reader on entry.** Has a working linear-time engine and a benchmark; believes
"it passed my examples" is evidence.

**Crux.** Two engines that agree on your examples can disagree on the next
pattern. How do you check *every* small pattern, and what do you do when they
disagree about what a pattern means?

**Sections and budgets (total ≈ 2,000 words).**
1. *Hook* (150): RE2's own test strategy: generate every small regex and every
   small string, compare all engines (Cox 2010, S §7, quote). We do the same
   against `re`.
2. *Orientation* (80), *Warm-up* (80), *Crux* (60).
3. *Every small pattern* (400): Listing 4-1 `file=code/difftest.py`: enumerate
   patterns up to length 4 over nine pieces, strings up to length 3 over
   `ab`, skip what either engine rejects. Listing 4-2 `run`: the result, 10,080
   cases, 0 mismatches. Why `fullmatch` and not `search` (leftmost-first vs
   longest, S §3: Cox on Perl vs POSIX; ECMAScript's `/a|ab/` note).
4. *The mismatch the test found* (400): the first version of the parser
   accepted a second quantifier, so `a+?` parsed as `(a+)?` and `a?+` as
   `(a?)+`. Python reads `+?` as *lazy* and `?+` as *possessive* (3.11+, B §3
   What's New): 171 mismatches out of 11,970 cases, all of that shape. The
   resolution was to *refuse* the construct, the way `re` refuses `a**`
   ("multiple repeat"), because a syntax with two meanings is worse than a
   syntax error. Listing 4-3 `expect-error`: `tinyre.compile("a+?")` →
   SyntaxError. Listing 4-4 `run`: inject a bug on purpose (monkeypatch
   `machine.compile_node` for `Repeat` with `many=False` to compile the child
   without the skip arrow) and show the test catching it with the first five
   cases printed. This is the chapter's centrepiece: a real bug, found by
   enumeration, resolved by a decision. Dialect caveat from Çakar et al. 2026
   (S §7).
5. *What we gave up* (350): captures (need Pike's VM, cost of copying
   submatch sets, Cox 2010, S §3), backreferences (NP-complete, S §3;
   RE2 "does not support constructs for which only backtracking solutions
   are known", S §3), lookaround, Unicode, classes. A table: construct ·
   supported by tinyre · by RE2 · by Python `re`.
6. *Where the real engines go* (300): RE2 (linear-time guarantee; lazy DFA as
   a cache that is flushed, S §4), Go `regexp` doc quote (S §4), Rust `regex`
   (O(m·n) worst case; the engine ladder, S §4), .NET 7 NonBacktracking (S
   §5). Which defaults backtrack: Python, Perl, PCRE, Java, JavaScript (S §5),
   with the terminology trap (PCRE calls backtracking "NFA"). Tip box: for
   untrusted input, use an automata engine or a timeout.
7. *Practice* (200): (1) blank: extend `PIECES` with `c` and re-run; (2) stub:
   add `search` to the differential test; (3) blank slate: enumerate strings
   over `abc` up to length 4 and report the case count; (4) transfer: write
   the same enumeration test for `int()` vs your own integer parser.
8. *Mental model* (120): recap + terms.
9. *One opinion* (80): for anything that reads input from the internet, the
   default regex engine of Python, Java, JavaScript and Perl is the wrong
   default.
10. *Going deeper* (80): Cox regexp3 (RE2 design and testing); Gallant's regex
    internals; Davis 2018; the Rust regex TOML test suite.
11. *What this book did not cover* (100): the closing paragraph the book
    promised: Unicode, classes, captures, POSIX semantics, DFAs.

**Listings.** 4-1 difftest.py; 4-2 run difftest; 4-3 expect-error on `a+?`;
4-4 injected-bug run.
**Spine increment.** `difftest.py`; the book's promise that `tinyre` agrees
with `re` on 10,080 cases.
**Terms introduced.** differential testing; exhaustive enumeration; lazy
quantifier; possessive quantifier; leftmost-first; leftmost-longest;
lazy DFA.
