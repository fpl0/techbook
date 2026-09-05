# techbook

techbook is a skill for [Claude Code](https://claude.com/claude-code) that writes a
technical book on a given topic and publishes it as HTML. It interviews the author
about scope, researches the topic with cited notes, plans the chapters, drafts them
one at a time, executes every code listing, and blocks publication until the
listings pass. The result is a set of Markdown chapters, the code they contain as
real files, and a rendered book with one page per chapter.

## Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [What the skill produces](#what-the-skill-produces)
- [Code listings and verification](#code-listings-and-verification)
- [Configuration](#configuration)
- [Scripts](#scripts)
- [How the skill is organised](#how-the-skill-is-organised)
- [Example](#example)
- [Development](#development)
- [Limitations](#limitations)
- [License](#license)

## Overview

The skill has two halves.

The first is an editorial process, defined in `skill/SKILL.md` and its reference
documents, that Claude follows when asked for a book. It separates research from
writing, requires the author to approve the brief and the outline before any prose
exists, drafts chapters sequentially so each one knows what came before, and edits
in staged passes against a written rubric.

The second is a set of Python scripts that check the result mechanically. The most
important is `verify.py`, which extracts every fenced code block from the chapters,
runs it in a sandbox, and compares the real output with the output printed in the
book. Prose style, cross-chapter consistency and citation liveness each have a
checker of their own. The scripts have no dependencies beyond the Python standard
library.

The distinction matters because the scripts can only check what is checkable. Code
either runs or it does not. Whether a chapter is well explained is judged by the
process, not the scripts, and the final report keeps the two apart.

## Requirements

| Requirement | Notes |
|---|---|
| Claude Code | The skill is invoked from a Claude Code session. |
| Python 3.11 or later | The scripts use `tomllib` to read dependency manifests. |
| macOS | Listings run under `sandbox-exec` with network access denied. On other systems `verify.py` runs listings without a sandbox and prints a warning. |
| A toolchain for the book's language | Python, Node, Bash, Rust (`rustc`) and Go (`go`) listings are supported. |
| `uv` and `npm` (optional) | Used to materialise pinned Python and Node environments when listings import third-party packages. |

## Installation

Clone the repository and symlink the `skill` directory into Claude Code's skills
folder:

```sh
git clone https://github.com/fpl0/techbook ~/Code/techbook
ln -sfn ~/Code/techbook/skill ~/.claude/skills/techbook
```

The skill registers at the start of the next Claude Code session. Because the
install is a symlink, changes in the clone take effect without reinstalling.

## Usage

### Starting a book

Ask Claude Code for a book on a technical subject:

```
write me a short book about how B-trees work, with runnable Rust
```

The skill triggers on intent, so "a primer on", "a guide to" and "a handbook for"
work as well. It does not trigger for a single article or a README.

### The interview

Before anything is written, the skill asks one batched round of questions:

- who the reader is and what they already know
- who the book is explicitly not for
- the project that will be built up across the chapters
- the primary programming language
- how deep the book should go
- what the book will deliberately leave out

The answers are recorded in `book.yaml` and treated as fixed for the rest of the
run. The skill does not default them, because every later phase inherits them.

### The pipeline

| Phase | What happens | Output | Gate |
|---|---|---|---|
| 1. Scope | The interview above. A colour palette and typeface are chosen for the topic. | `book.yaml`, `research/brief.md` | Author approves the brief. |
| 2. Research | One subagent per sub-topic, in parallel, each writing notes with citations attached as it reads. Dead, unarchived URLs are removed together with the claims that rest on them. | `research/notes/*.md` | `urlcheck.py` |
| 3. Architect | The outline is written from the notes. Each chapter gets a job, an entry state for the reader, a crux, key points with the note that backs each, planned listings and a per-section word budget. | `outline.md` | Author approves the outline. |
| 4. Draft | One subagent per chapter, in order. Each receives only the notes its outline cites plus a summary of every earlier chapter. It writes the chapter's code first, gets it passing, then writes the prose. | `src/chNN-*.md`, `code/` | |
| 5. Verify | Every listing is executed and its output compared with the book. Failures return to the chapter's writer, for at most three rounds. | `.verify/report.json` | `verify.py` |
| 6. Edit | Six passes in order: structural, line, mechanical style check, rubric scoring per section, continuity, citations. | edited `src/` | `prose.py`, `continuity.py` |
| 7. Render | Front matter and cover art are written, then the HTML is built. | `build/` | `verify.py --strict` |
| 8. Report | Word counts, verification results, unverified blocks with their reasons, dead citations, and anything flagged rather than fixed. | | |

### Depth

| Depth | Chapters | Approximate length |
|---|---|---|
| `brief` | 4 to 5 | 8,000 words |
| `standard` | 6 to 8 | 25,000 words |
| `comprehensive` | 10 to 15 | 55,000 words |

The default is `standard`. "Short" or "quick" in the request selects `brief`;
"thorough" or "complete" selects `comprehensive`.

### Resuming

Progress is recorded in `state.json`. To continue an interrupted run, name the
book's directory:

```
continue the book in ./btrees
```

The skill reads the state file and resumes from the first incomplete step.

## What the skill produces

A book is a directory with this layout:

```
my-book/
├── book.yaml            scope, audience, depth, language, theme
├── outline.md           the approved chapter contracts
├── state.json           phase and per-chapter status
├── research/
│   ├── brief.md
│   └── notes/           cited research notes, one file per sub-topic
├── src/
│   ├── front-matter.md  who the book is for, how to read it
│   ├── cover.svg        cover art
│   ├── ch01-*.md        chapter sources
│   └── SUMMARY.md       generated; lets mdBook build the same sources
├── code/                every listing as a real file, importable by later listings
├── verify/python/       pinned dependency manifest, if the book needs packages
├── .verify/             verification cache and report
└── build/
    ├── index.html       cover, contents, front matter
    ├── chNN-*.html      one page per chapter, with previous and next links
    ├── glossary.html    built from each chapter's terms line
    ├── book.html        the whole book in one self-contained file
    └── assets/          book.css, book.js, search.js
```

The Markdown under `src/` is the source of truth. The HTML is generated from it and
can be rebuilt at any time with `render.py`.

The rendered book has these properties:

- No framework, no web fonts and no network requests when reading. The pages work
  from a local folder and remain readable with JavaScript disabled.
- Syntax highlighting is applied at render time, so it is in the HTML itself and
  survives printing.
- Search works from `file://` because the index ships as a script rather than a
  file to fetch.
- Light and dark colour schemes, following the system by default, with a toggle.
- Print styles produce a usable PDF from the browser's print dialog.
- `book.html` inlines its CSS, JavaScript and search index for offline reading and
  full-book search.

## Code listings and verification

### The block contract

Every fenced code block in a chapter declares how it should be checked. A block
without a declaration is a lint error, and nothing runs until lint errors are fixed.

| Mode | Meaning | Passes when |
|---|---|---|
| `run` | Code the reader could execute. | Exit status 0 and, if an ` ```output ` block follows, the real output matches it. |
| `check` | Code that must compile or parse but prints nothing. | The toolchain exits 0. |
| `expect-error` | A deliberate failure. | The block fails and, if `expect="…"` is given, that text appears in stderr. |
| `norun` | Real code that cannot run here, for example because it needs a GPU or a paid API. | Never. Reported as unverified with the reason given in `why="…"`. |
| `literal` | Not executable: pseudocode, configuration fragments, exercise stubs. | Never. Requires `why="…"`. |

Modifiers refine a block:

| Modifier | Effect |
|---|---|
| `env=NAME` | Share an interpreter session with earlier `run` blocks that name the same environment, in book order. Python, Node and Bash only. |
| `file=path` | The block is that file. `verify.py` requires `code/path` to exist and match the block exactly; `--sync-code` writes it. `code/` is on the import path when listings run. |
| `expect="…"` | Text that must appear in stderr for an `expect-error` block. |
| `timeout=N` | Seconds before the block is killed. Default 30. |
| `net` | Allow network access for this block. |
| `nondet=output` | Run and require exit 0, but never diff the output. For timings and anything else that varies between runs. |
| `nondet=command` | Do not run unless `VERIFY_NONDET=1` is set. |
| `caption="…"` | The listing caption. |
| `highlight=3,7-9` | Lines to emphasise. |

Example:

````markdown
```python run env=scanner file=code/scanner.py
def tokenize(src):
    return src.split()
```

```python run env=scanner
print(tokenize("a b c"))
```

```output
['a', 'b', 'c']
```
````

### How verification runs

1. Chapters are parsed and every block is linted against the contract.
2. Imports in Python and Node blocks are resolved against the standard library and
   the pinned manifests in `verify/python/pyproject.toml` and
   `verify/node/package.json`. An import that is in neither is a failure. The gate
   never installs a package to find out whether it exists.
3. Blocks run under `sandbox-exec` with writes confined to `.verify/work/` and
   network access denied unless the block says `net`.
4. Output is normalised before comparison: temporary paths, timestamps, hex
   addresses, durations and ANSI codes are replaced with placeholders.
5. Results are cached by a hash of the block, its dependencies and the toolchain,
   so unchanged blocks are not rerun.

### Corrections

When a block's real output differs from the book, `verify.py` does not edit the
chapter. It writes `src/chNN-name.md.corrected` and prints a diff. Accepting the
change is a separate step:

```sh
python3 skill/scripts/verify.py ./my-book --promote
```

This keeps the author in control of what the book says, and makes a changed number
visible as a finding rather than a silent update.

## Configuration

`book.yaml` is written during the interview and read by the writers and by
`render.py`. Its keys:

| Key | Used by | Meaning |
|---|---|---|
| `title`, `subtitle` | render, writers | Shown on the cover and in the running head. |
| `author`, `date`, `edition` | render | The byline on the cover. |
| `audience`, `not_for`, `prerequisites` | writers | Who the book is for and what it assumes. |
| `depth` | writers | `brief`, `standard` or `comprehensive`. |
| `language` | render, writers | The primary language; sets the default for highlighting. |
| `spine` | writers | The project built up across chapters. |
| `non_goals` | writers | What the book leaves out. |
| `palette` | render | One of `oxblood`, `indigo`, `forest`, `ochre`, `slate`, `plum`, `teal`, `graphite`. |
| `face` | render | One of `iowan`, `charter`, `georgia`, `baskerville`, `palatino`. |
| `theme_why` | writers | One line on why the palette and face suit the topic. |
| `accent`, `accent_dark`, `jacket` | render | Optional hex overrides for the palette. |

### Themes

Each book has its own colour palette and typeface, chosen during the interview to
suit the subject. All palettes and faces are listed by:

```sh
python3 skill/scripts/render.py --list-themes ./my-book
```

Faces are system font stacks, so no font is downloaded. Every palette passes WCAG AA
contrast on every combination the stylesheet produces, and `render.py` repeats the
check at build time. A custom `accent`, `accent_dark` or `jacket` value that fails
the check stops the build. The rest of the design (measure, type scale, page chrome,
code token colours) is shared by every book.

## Scripts

All scripts take a book directory as their first argument and work outside the skill
on any directory with the layout above.

| Script | Purpose | Options |
|---|---|---|
| `verify.py` | Lint, execute and diff every listing; write `.verify/report.json`. | `--strict` treat `norun` and `literal` blocks as failures too. `--promote` accept `.md.corrected` files. `--only STEM` restrict to chapters whose filename contains the text. `--sync-code` write `file=` listings out to `code/`. `--no-cache` rerun everything. `--setup` materialise language environments and exit. |
| `prose.py` | Report style-ban hits, craft problems, em-dash density, sentence-length variance and repeated openers. Reports only; never rewrites. | `--only STEM`, `--json`, `--max-density N` (em dashes per thousand words, default 1.0). |
| `continuity.py` | Cross-chapter checks: terms used before the chapter that introduces them, numbers attributed to a chapter that does not contain them, references to chapters that do not exist. | `--json` |
| `urlcheck.py` | Check every cited URL, falling back to the Wayback Machine for dead links. | `--timeout N`, `--no-wayback`, `--json` |
| `render.py` | Build the HTML. | `--out DIR` (default `build`), `--no-single` skip `book.html`, `--list-themes`. |
| `highlight.py` | The render-time syntax highlighter. Usable directly as `highlight.py FILE LANG`. | |

Exit codes: 0 clean, 1 findings, 2 invocation or lint errors.

## How the skill is organised

```
skill/
├── SKILL.md                 the process Claude follows, phase by phase
├── references/
│   ├── house-style.md       the voice, and the banned patterns prose.py enforces
│   ├── exemplars.md         devices taken from well-regarded technical books, as writer rules
│   ├── chapter-template.md  the twelve-part chapter shape and the reason for each part
│   ├── rubric.md            the seven-dimension scoring pass used during editing
│   ├── block-tags.md        the code block contract in full
│   ├── svg-kit.md           the constrained primitives for hand-drawn diagrams
│   └── html-spec.md         what render.py accepts and produces, and the design constraints
├── assets/
│   ├── book.css             the stylesheet copied into every build
│   └── book.js              theme toggle, search, copy buttons, keyboard navigation
├── scripts/                 the six scripts above
└── evals/evals.json         prompts and assertions for testing the skill itself
```

Each chapter writer receives the book's `book.yaml` and outline, the reference
documents, the research notes its outline cites, and summaries of the chapters
already written. Editing the references therefore changes every future book.

The repository also contains:

```
fixtures/     small books that exercise the scripts: good, bad, rich
demo/         a complete book generated with the skill
docs/         screenshots used in this file
.critique/    a design review of the rendered output
```

## Example

`demo/regex-from-scratch` is a four-chapter book on building a regular expression
engine in Python, generated end to end with the skill. Open
`demo/regex-from-scratch/build/index.html` to read it.

<p align="center">
  <img src="docs/cover.png" alt="The cover of the sample book: a navy jacket with a state-machine diagram and the title in a bold serif" width="720">
</p>

<p align="center">
  <img src="docs/chapter.png" alt="A chapter page: a single serif column, a numbered listing with syntax highlighting, and a verified tag on its caption" width="720">
</p>

Its verification report:

```
Book verification · 2026-09-05
──────────────────────────────────────────────────────────────
Blocks    31 total   (23 from cache)
  OK             23
  literal         8

All code verified.
```

The eight literal blocks are exercise stubs, which are deliberately incomplete. The
book cites 83 sources, of which 77 resolve directly and 3 through the Wayback
Machine; the remaining 3 are behind publisher access controls. Every timing and
traceback in the text is the output of the listing beside it.

To rerun the gates on the demo:

```sh
python3 skill/scripts/verify.py demo/regex-from-scratch --strict
python3 skill/scripts/prose.py demo/regex-from-scratch
python3 skill/scripts/continuity.py demo/regex-from-scratch
python3 skill/scripts/urlcheck.py demo/regex-from-scratch
python3 skill/scripts/render.py demo/regex-from-scratch
```

## Development

The fixtures under `fixtures/` are the regression suite for the scripts:

```sh
python3 skill/scripts/verify.py fixtures/bad            # exits 2 with eight lint errors
python3 skill/scripts/verify.py fixtures/good --no-cache
python3 skill/scripts/verify.py fixtures/rich --no-cache
python3 skill/scripts/render.py fixtures/rich
```

`fixtures/bad` contains one of every contract violation. `fixtures/rich` exercises
every construct the chapter template calls for, plus the Markdown edge cases the
renderer has been fixed for, and uses a non-default theme.

`skill/evals/evals.json` holds prompts and assertions for evaluating the skill's
behaviour as a whole: run each prompt with and without the skill and check the
assertions against both.

Changes to `skill/references/` alter what chapter writers are told. When proposing
one, say which book or fixture it was tested against.

## Limitations

- Verification covers exit status and standard output. It does not cover memory
  use, concurrency, or anything a test suite would catch that stdout does not show.
- Code is roughly a fifth of a book by word count. The remaining checks (`prose.py`,
  `continuity.py`, the rubric, citation liveness) are weaker than a process exit
  code. "Every listing ran" is the claim the skill can make; "the book is correct"
  is not.
- Durations are normalised before diffing so that timing tables stay stable between
  runs. A hand-typed timing would therefore pass as well. The references instruct
  writers to paste measured output, and nothing enforces it.
- Semantic repetition across chapters is not detected automatically.
- The sandbox depends on `sandbox-exec` and is therefore macOS-only. Elsewhere,
  listings run unsandboxed with network access, and the report says so.
- A `comprehensive` book takes many subagent runs and hours of wall time.

## License

MIT. See [LICENSE](LICENSE).
