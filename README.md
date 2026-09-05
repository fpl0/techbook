# techbook

A Claude Code skill that turns a technical topic into a book: researched, structured
for teaching, written to a house style, and published as HTML in which **every code
example has actually been executed**.

The differentiator is the last part. Any model can produce plausible-looking code in a
book. This one refuses to publish a book whose examples have not run.

## Layout

```
skill/                 the skill itself; symlinked into ~/.claude/skills/techbook
├── SKILL.md           the orchestrator: phases, gates, resumability
├── references/        house style, chapter template, block contract, HTML spec, diagram kit
├── assets/            book.css and book.js, shipped verbatim into every book
├── scripts/           verify.py, render.py, urlcheck.py
└── evals/evals.json   4 evals, 15 assertions
fixtures/              good / bad / rich — regression fixtures for the scripts
demo/regex-from-scratch/   a real 3-chapter book built with the skill
```

## Install

```bash
ln -sfn ~/Code/techbook/skill ~/.claude/skills/techbook
```

The symlink means edits here take effect immediately, with no copy step.

## The scripts

All three are dependency-free Python 3.10+, and run on a machine with nothing
installed beyond a language toolchain for whatever the book's examples are written in.

```bash
python3 skill/scripts/verify.py   <book>            # lint, execute, diff, report
python3 skill/scripts/verify.py   <book> --promote  # accept output corrections
python3 skill/scripts/verify.py   <book> --strict   # publish gate
python3 skill/scripts/render.py   <book>            # markdown -> HTML
python3 skill/scripts/urlcheck.py <book>            # citation liveness
```

### verify.py

Every fenced block declares a mode — `run`, `check`, `expect-error`, `norun`,
`literal` — and an undeclared code block is a hard lint error rather than a silent
skip. Blocks execute under `sandbox-exec` with network denied and writes confined to
the book's scratch directory. Imports are resolved against a pinned manifest *before*
anything runs, because roughly a fifth of package names that language models suggest
do not exist, and installing to find out is the attack.

When real output differs from what the book claims, nothing is edited in place: a
`.md.corrected` file is written alongside the chapter with a diff, and `--promote` is
the separate step that accepts it.

### render.py

A focused Markdown parser and static site generator. Emits per-chapter pages plus a
single self-contained `book.html` that inlines its CSS, JS and search index, so it
works offline and prints to a decent PDF. No framework, no web fonts, no build step,
no network at read time, and the book stays readable with JavaScript disabled.

## Does it work?

The demo book was written using the skill, and the gate caught four real defects that
would otherwise have shipped:

| What the gate caught | Why it mattered |
|---|---|
| Prose claimed the backtracking matcher's cost doubled per character | Measured growth was polynomial. Exponential blowup needs *nested* quantifiers, which the book's toy language cannot express. The claim was wrong. |
| A hand-written traceback in an error demo | Real output had frames the book omitted. The demo now shows a clean, verified message instead. |
| `(a*)*b` overflowed the stack in the chapter 3 simulator | A genuine bug: split states are never stored, so a cycle running *through* splits went undetected. The fix, and the trap, are now the chapter's misconception callout. |
| Chapters 2 and 3 were in separate execution sessions | Chapter 3's code referenced chapter 2's compiler and could not have run for a reader. |

Two of those are factual errors in prose and one is a real bug. None would have been
caught by reading the draft.

It also found a hole in its own design: durations normalise to `<DUR>` so diffs stay
stable across runs, which means a hand-invented benchmark passes the gate exactly as a
measured one does. That hazard is now documented in `references/block-tags.md` — paste
measured output, never write it.

## What it does not do

- Semantic cross-chapter repetition detection. No good solution exists in the literature.
- Automatic "through-line" measurement. The structural editing pass is a partial mitigation; the final read is human.
- Capture-group-level verification of anything but exit status and output text.

## Design notes

The architecture follows what the research actually supports, which in several places
is the opposite of the obvious choice:

- **Research runs in parallel, writing runs in series.** LangChain shipped parallel section-writers and pivoted away — the sections did not know about each other.
- **No book toolchain.** Every technical book people praise for its HTML uses a custom pipeline; mdBook, Quarto and Docusaurus all produce a recognisable docs-site look and all fail the fresh-machine test. Markdown sources plus `SUMMARY.md` are still emitted, so adopting mdBook later costs one command.
- **A detailed per-chapter contract before drafting.** Outline granularity buys more coherence than any amount of later editing.
- **State on disk, not in context.** Chapter 1's details are diluted by the time chapter 8 is written, even when they are technically still in the window.
