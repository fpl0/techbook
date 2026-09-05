# Editorial rubric

`prose.py` catches tells. It cannot tell you whether a chapter is any good. This is
the scored read that can, and the editing pass in phase 5 runs it per chapter.

Score each dimension 1–5. **A chapter ships at 4 or above on every dimension.** A 3
anywhere means another pass; a 2 means the chapter needs restructuring, not editing.

Score honestly. A rubric everything passes measures nothing, and the point of a
number is that it can go down.

## The dimensions

### 1. Does the chapter do its stated job?

Read the chapter's contract in `outline.md` first, then the chapter. Does a reader
who arrives in the stated entry state leave able to do the stated thing?

- **5** — does its job, and nothing outside it
- **3** — does its job plus material belonging to another chapter
- **1** — the contract describes a chapter that was not written

### 2. Is the explanation load-bearing?

Every paragraph should carry weight the reader needs. The failure is prose that
restates the code, restates the heading, or announces what comes next.

- **5** — cut any paragraph and something is lost
- **3** — two or three paragraphs could go with no loss
- **1** — the chapter is code with narration between the listings

### 3. Concrete before abstract

Does each concept arrive as a specific case the reader can hold, with the general
principle named afterwards? Opening a section with a definition is the failure.

### 4. Are the claims earned?

Every number traced to real output. Every external fact cited. Every degree of
certainty matching what the source supports. **Any claim the chapter cannot back
should be cut or attributed, not softened into a hedge.**

- **5** — every factual claim is demonstrated or cited
- **3** — one or two asserted claims a reader would want a source for
- **1** — confident statements about history, benchmarks or other systems, uncited

### 5. Is the difficulty honest?

Does the chapter admit what is genuinely hard, what it is skipping, and what it
gave up? A chapter that makes everything sound easy fails the first reader who
finds it hard, and they conclude the fault is theirs.

### 6. Voice

Does it read as one person who has done this explaining it to a colleague? Or as
prose assembled to be inoffensive? Uniform sentence rhythm, hedged judgements, and
absent opinions all point the same way.

- **5** — a specific person is present, with judgements they own
- **3** — competent and anonymous
- **1** — could have come from any tool, on any topic

### 7. Would a reader do the exercises?

Are they a ladder with real reasoning in the solutions, or four restatements of the
listing? An exercise whose answer is "type the code again" is not an exercise.

## Output format

```text
Chapter 3 — All Paths at Once
  1 job              4  covers the simulator and stops there
  2 load-bearing     3  the "what we gave up" table repeats the prose above it
  3 concrete-first   5
  4 claims earned    2  Thompson 1968, the Cloudflare outage and RE2's design are
                        all asserted with no source
  5 honest           4
  6 voice            3  every judgement is hedged; no opinion is owned
  7 exercises        4
  → 2 dimensions below 4. Not shippable.
```

Then list the specific edits, each with `file:line`, and apply the **minimum
effective edit**: change the clause, not the paragraph. A heavy rewrite loses the
chapter's voice and introduces fresh slop of its own, which is how a scored loop
makes prose worse while the score goes up.

## What this pass may not do

- Invent evidence for a claim that lacks it. Cut it, attribute it, or flag it.
- Rewrite a claim to sound more certain than its source supports.
- Prioritise elegance over precision.
- Make a change that spans chapters. Flag those for the user instead.
