# Chapter template

The shape every chapter follows, and the reason each part is there. The reasons
matter: a writer who knows *why* the warm-up exists will write a good one, and a
writer who doesn't will write a quiz.

## Contents

- [The shape](#the-shape)
- [Part by part](#part-by-part)
- [The named effects behind it](#the-named-effects-behind-it)
- [Book-level scaffolding](#book-level-scaffolding)
- [Budgets](#budgets)
- [HTML for each part](#html-for-each-part)

## The shape

```text
1.  HOOK                 A concrete broken thing, or a real question. 1-2 paragraphs.
2.  ORIENTATION BOX      What you'll learn · Assumes you know · time · exercise count
3.  WARM-UP              2-3 retrieval questions reaching back 1-3 chapters
4.  SECTIONS (3-7)       concept -> worked example -> predict checkpoint -> variation
5.  MISCONCEPTIONS       Inline, where they bite. Wrong code + its real error.
6.  PRACTICE             A faded ladder of 3-4 exercises, solutions in <details>
7.  MAKE                 One build that advances the spine project
8.  MENTAL MODEL         A diagram, a 5-8 bullet recap, the terms introduced
9.  GOING DEEPER         Clearly optional. Papers, source, specs.
10. NEXT                 One sentence of forward tension.
```

Parts 3, 7 and 9 are droppable for a `brief`-depth book. Parts 1, 2, 4, 6 and 8 are
not droppable at any depth.

## Part by part

### 1. Hook

Open with something concrete: a program that misbehaves, a measurement that surprises,
a question with a non-obvious answer. **Never open with what the chapter will cover** —
the orientation box does that, immediately below, in a form the reader can skim.

### 2. Orientation box

Three things, in a bordered box: what the reader will be able to do afterwards (3–5
bullets, each starting with a verb), what the chapter assumes (linked to the chapters
that taught it), and a time and exercise count.

The "assumes you know" list is load-bearing. It is what lets a reader who already
knows the material skip the chapter honestly, and what lets a lost reader find the
chapter they actually needed.

### 3. Warm-up

Two or three short questions on **earlier** chapters, answers hidden in `<details>`.
Reach back one to three chapters, not only the immediately preceding one.

This is retrieval practice and interleaving, and it is the cheapest real learning
gain available in a book. It is not a summary of the previous chapter — a question
the reader has to *answer* does the work; a recap they can read passively does not.

### 4. Sections

Three to seven per chapter. Each one runs:

**a. Concept in prose.** Under ~500 words before the first line of code. Concrete
example first, abstraction named afterwards.

**b. A complete worked example.** Runnable, `run`-tagged, with real captured output.
Complete is the operative word: novices learn more from studying a full solution than
from being asked to produce a partial one. Annotate it with numbered markers keyed to
a list underneath, so the explanation sits *with* the code rather than three
paragraphs away.

**c. A predict checkpoint.** One `<details>`: "what does this print?", "which of these
two is faster?", "why must this be `&mut`?". The reader commits before revealing.

**d. A variation, an edge case, or a misconception.** What changes if an input is
empty, if the list is huge, if two threads do it at once.

**Keep new-concept listings to about seven lines.** Working memory holds a handful of
chunks; an experienced reader chunks a 30-line function into three ideas, a learner
reads thirty lines. Grow listings incrementally across a section rather than
presenting the finished thing.

### 5. Misconception callouts

Place them where the mistake actually happens, not in a lump at the end. Each shows
the wrong code, **its real error output** (an `expect-error` block, so the error is
genuine and stays genuine), and the diagnosis.

Showing real compiler and interpreter errors is one of the strongest teaching devices
available, because it trains the reader to read the error rather than fear it.

### 6. Practice — a faded ladder

Four exercises, each less scaffolded than the last:

1. **Completion.** A working solution with one blank.
2. **Partial.** The same shape with several blanks, or a stub to finish.
3. **Blank slate.** Same problem class, nothing given.
4. **Transfer.** The same idea in a different context.

Exercise stubs are `literal why="exercise stub"` — they are deliberately incomplete
and must not be executed. Solutions go in `<details>`, and a solution gives the
**reasoning**, not just the code.

### 7. Make

One 30–60 minute build that advances the book's spine project. This is what turns a
sequence of chapters into a book: the reader finishes holding something they built.

### 8. Mental model

A diagram, a 5–8 bullet recap, and the terms introduced in this chapter. The recap
states *what is true*, not what the chapter did. "`sum` of an empty sequence is 0" —
never "we learned about the sum function".

### 9. Going deeper

Papers, specifications, source code. Explicitly optional and visibly skippable, so
an expert can follow it and a beginner can ignore it without anxiety.

### 10. Next

One sentence that creates a reason to continue. A question the next chapter answers.

## The named effects behind it

Worth knowing, because they tell you when to break the template.

| Effect | What it says | What it changes here |
|---|---|---|
| Worked-example effect | novices learn more from studying complete solutions than from solving | every concept gets a full example before any exercise |
| Expertise reversal | scaffolding that helps novices actively *hurts* experts | the orientation box and "going deeper" give experts a fast path around the middle |
| Split-attention | splitting related information across space costs working memory | annotations sit in the listing, not in a distant paragraph |
| Faded worked examples | support should be withdrawn gradually, not all at once | the four-rung exercise ladder |
| PRIMM | predict → run → investigate → modify → make outperforms write-first | the section shape, and the chapter shape |
| Testing effect | retrieving is far stronger than re-reading | the warm-up, and every `<details>` checkpoint |
| Interleaving and spacing | mixed, spaced retrieval beats blocked | warm-ups reach back several chapters |
| Chunking limits | working memory holds only a few chunks | ≤7-line listings for new concepts; name each chunk in prose |
| Coherence principle | decorative extras reduce learning | no stock imagery, no emoji, no jokes that don't teach |
| Concreteness fading | concrete grounding first, abstraction after | example before definition, everywhere |

## Book-level scaffolding

Do not skip these; they are what makes a set of chapters a book.

- **Front matter:** who this is for, **who it is not for**, how to read it, prerequisites, and the typographic conventions used.
- **A spine project** carried across chapters. The single highest-value structural decision available.
- **Glossary** of every term introduced, linked from first use.
- **A closing chapter** that says honestly what the book did not cover and where to go next.

## Budgets

| Depth | Chapters | Words/chapter | Listings/chapter | Total |
|---|---|---|---|---|
| `brief` | 4–5 | 1,200–2,000 | 3–6 | 6k–10k |
| `standard` | 6–8 | 2,500–4,000 | 5–10 | 18k–30k |
| `comprehensive` | 10–15 | 3,500–5,000 | 8–14 | 45k–70k |

Every chapter gets at least one diagram, at least two `<details>` checkpoints, and a
mental-model recap, at every depth.

A chapter running well past its budget is a chapter that should be split. Say so in
the drift report rather than silently writing 8,000 words.

## HTML for each part

Emit these classes; `book.css` styles them.

```html literal why="markup reference for chapter writers; not executable"
<div class="orient">
  <h3>What you'll learn</h3>
  <ul><li>…</li></ul>
  <h3>Assumes you know</h3>
  <p>…</p>
  <p class="meta">~35 min · 4 exercises</p>
</div>

<div class="callout">
  <div class="title">This trips people up</div>
  <p>…</p>
</div>

<details>
  <summary>Predict: what does this print?</summary>
  <p>…</p>
</details>

<div class="exercises">
  <div class="exercise">
    <span class="label">Exercise</span>
    <p>…</p>
    <details><summary>Solution</summary><p>…</p></details>
  </div>
</div>

Sidenote:<label for="sn-3" class="margin-toggle sidenote-number"></label>
<input type="checkbox" id="sn-3" class="margin-toggle">
<span class="sidenote">Marginal aside. Never put load-bearing content here.</span>

<ol class="annot"><li>First annotated point.</li><li>Second.</li></ol>
```

Sidenote ids must be unique across the whole book, because the single-file build
concatenates every chapter into one document. Use `sn-<chapter>-<n>`.
