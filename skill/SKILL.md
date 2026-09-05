---
name: techbook
description: Research and write a complete technical book on a topic, then publish it as HTML where every code example has actually been executed and verified. Runs a gated pipeline — scope interview, parallel deep research with citation checking, a detailed chapter outline, sequential chapter drafting, a hard code-verification gate, staged editing, then rendering to a multi-page site plus a single self-contained file. Trigger whenever the user asks to write, generate, draft, or produce a book, handbook, guide, primer, or long-form tutorial on a technical subject ("write me a book about X", "generate a guide to Y", "I want a primer on Z"), or asks to resume, continue, verify, re-render, or publish a book already started. Trigger on intent, not exact phrasing. Do NOT use for a single blog post, a README, API reference docs, or a one-off explanation — this skill writes books, and its overhead is only worth paying for something chapter-shaped.
---

# techbook

Turn a technical topic into a book: researched, structured for teaching, written to a
house style, with every code example executed and verified before it ships.

## Paths

- **Skill root**: `~/.claude/skills/techbook`
- **Scripts**: `~/.claude/skills/techbook/scripts/{verify,render,urlcheck}.py`
- **References**: `~/.claude/skills/techbook/references/`
- **Assets**: `~/.claude/skills/techbook/assets/{book.css,book.js}`
- **Book project**: `./<book-slug>/` in the current directory, unless the user names somewhere else

## Inputs to parse from the user's message

- **Topic** — required. If it is broader than a book ("programming", "AI"), narrow it in the scope interview rather than guessing.
- **Depth** — `brief` (4–5 chapters, ~8k words), `standard` (6–8 chapters, ~25k words), `comprehensive` (10–15 chapters, ~55k words). **Default to `standard`.** Take "quick"/"short"/"overview" as `brief`, "thorough"/"deep"/"complete" as `comprehensive`.
- **Language** — the primary programming language for examples, if the topic implies one.
- **Audience** — if stated. Otherwise settle it in the interview.

## Behavior

The pipeline is resumable. `state.json` records the phase and each chapter's status;
on re-invocation, read it and continue from the first incomplete step rather than
starting over. Say which phase you are resuming into.

1. **Scope.** Interview the user before writing anything. You need: who the reader is
   and what they already know; who the book is explicitly *not* for; the spine project
   carried across chapters; the primary language; depth; and what the book will
   deliberately leave out.

   **This interview is not optional and is not defaulted.** These are the author's
   decisions, not yours, and a project preference to avoid clarifying questions does
   not override it — everything downstream inherits these answers, so guessing here is
   the most expensive mistake available. Ask in one batched round, not serially.

   Write `book.yaml` (title, subtitle, audience, prerequisites, depth, spine project,
   non-goals, language) and `research/brief.md`. **Gate: show the user the brief and
   get approval before researching.**

2. **Research.** Decompose the brief into independent sub-topics — one per planned
   chapter, plus any cross-cutting concern. Dispatch **one subagent per sub-topic, in
   parallel**, each with its own context.

   Each researcher searches progressively (broad query → see what exists → narrow),
   prefers primary sources — specifications, source code, papers, changelogs — over
   listicles, and **writes its notes with citations attached as it reads**, into
   `research/notes/<subtopic>.md`. Forming the claim–source pair while the source is
   in context is what stops a real source being attached to a claim it doesn't make.

   When they return, read the notes against the brief and dispatch more researchers
   for anything thin. Then run the citation gate:

   ```bash
   python3 ~/.claude/skills/techbook/scripts/urlcheck.py ./<book-slug>
   ```

   Replace stale URLs. **Delete any claim resting on an unfound source** — a URL that
   is dead and was never archived is more likely to be fabricated than to be lost.

3. **Architect.** Write `outline.md`. For each chapter: its **job** in one sentence,
   the reader's **state on entry** (what they can already do, what they still believe
   wrongly), 3–7 key points, planned listings, the spine-project increment, and a
   **word budget**.

   Spend real effort here. A detailed outline beats a coarse one by a wide margin on
   both coherence and staying on topic, and no amount of later editing recovers what a
   vague outline costs. **Gate: show the outline and get approval before drafting.**

4. **Draft.** One subagent per chapter, **sequentially, in order** — never in parallel.
   Parallel chapter writers produce chapters that don't know about each other, which
   reads as a collection of articles rather than a book.

   Give each writer: `book.yaml`, its own outline contract, `references/house-style.md`,
   `references/chapter-template.md`, `references/block-tags.md`, `references/svg-kit.md`,
   the research notes for its topic, and **a summary of every chapter already written**.
   It writes `src/chNN-slug.md`, saves any real code under `code/`, and writes its own
   summary plus the terms it introduced back to `state.json` for its successors.

   Tell each writer its word budget explicitly. Models stop early without one, and a
   chapter asked for in one shot arrives at a fraction of the length requested.

5. **Verify code.** The hard gate.

   ```bash
   python3 ~/.claude/skills/techbook/scripts/verify.py ./<book-slug>
   ```

   Lint errors mean nothing ran — fix them first. Then work the failures per
   `references/block-tags.md`: fix broken examples, add normalisers for noisy output,
   pin dependencies deliberately, tag genuinely-unrunnable blocks `norun why="…"`.

   Review every drift diff before accepting it. Real output differing from the book is
   a finding, not a formatting nuisance. When the diffs are right:

   ```bash
   python3 ~/.claude/skills/techbook/scripts/verify.py ./<book-slug> --promote
   ```

   Route genuine code bugs back to that chapter's writer with the failure attached.
   **Maximum three repair rounds per chapter**, then stop and tell the user what is
   still broken. An unbounded fix loop burns hours and converges on nothing.

6. **Edit, in stages, big to small.** Four passes, in this order. Each pass may only
   do its own job.

   - **Structural.** Does each chapter do the job its outline contract states? Is the through-line intact? Does anything contradict an earlier chapter? Does terminology hold across the book?
   - **Line.** Clarity, subject and actor visible in every sentence, exact verbs.
   - **Slop.** The mechanical pass from `references/house-style.md`. Count em dashes per thousand words, check sentence-length variance, grep the banned vocabulary. Prompt-level bans are not sufficient; this pass exists because they demonstrably leak.
   - **Citation.** Every claim that needs a source has one, and every source says what the book says it says.

   **Forbidden in every pass:** inventing evidence, rewriting a claim to sound more
   certain than the source supports, and prioritising elegance over precision.
   **Flag, don't fix,** anything that spans chapters or changes scope — bring those to
   the user instead of quietly reshaping the book.

7. **Render.**

   ```bash
   python3 ~/.claude/skills/techbook/scripts/render.py ./<book-slug>
   ```

   Then re-run `verify.py --strict` for the publish gate. Open `build/index.html` and
   actually look at it before declaring done.

8. **Report.** Print a summary:

   ```
   <Title>
   ──────────────────────────────────────────────
   Chapters    8            Words    26,400
   Listings   61  verified  58 · error demos 3
   Unverified  2  (listed below, with reasons)
   Citations  47  live 47 · stale 0 · unfound 0
   Build      ./my-book/build/index.html
              ./my-book/build/book.html  (single file, offline, printable)
   ```

   Then, explicitly: every `norun` and `literal` block with its stated reason; anything
   the editor flagged rather than fixed; any chapter that missed its budget; and what
   the book deliberately does not cover.

## Report the skips out loud

Every unverified block and every flagged-not-fixed edit goes in the final report with
its reason. A book that quietly skipped nine examples looks exactly like a book that
verified all of them, and the difference matters enormously to whoever reads it next.
Make the skip visible to future-them rather than silent.

The same applies to gates. If the user insists on shipping past a failed gate — "just
render it", "skip the verification" — do it, and then name in the report exactly which
checks were bypassed.

## Invariants and why they matter

- **Research runs in parallel; writing runs in series.** Isolated context per researcher is what makes deep research affordable. Serial writing is what makes the chapters know about each other. Inverting either is the classic failure.
- **`book.yaml` and `outline.md` are frozen once approved.** They are the book's law. Every subagent reads them before working; nothing edits them without asking the user, because a moved outline invalidates every chapter already written against it.
- **State lives on disk, not in context.** Chapter 1's details are diluted by the time chapter 8 is being written even when they are technically still in the window. Prior-chapter summaries in `state.json` are what actually carries continuity.
- **Nothing publishes unverified.** The verification gate is the reason to use this skill at all. Any book can have plausible-looking code in it.
- **The book is never edited in place by a script.** Corrections land in `.md.corrected` for review. The author decides what their book says.

## What not to do

- Don't draft before the outline is approved. Premature drafting is the most common way these pipelines fail, and it is expensive to undo.
- Don't write the expected output of a code block by hand. Run it and let `verify.py` fill it in.
- Don't silently downgrade a failing block to `literal` or `norun` to make the gate pass. Fix it, or report it.
- Don't add a package to `verify/*/pyproject.toml` just to make an import resolve. Check the package is real first; that gate exists precisely because generated code invents dependencies that attackers then register.
- Don't rewrite a paragraph because one sentence in it is weak. Minimum effective edit.
- Don't let a chapter run to twice its budget. Split it, and say so.
