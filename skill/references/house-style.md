# House style

The voice spec every chapter writer and every editing pass works to. Read it before
writing a word.

## Contents

- [The register](#the-register)
- [Sentences and paragraphs](#sentences-and-paragraphs)
- [Technical precision](#technical-precision)
- [The slop ban-list](#the-slop-ban-list)
- [Words and constructions to avoid](#words-and-constructions-to-avoid)
- [How the slop pass works](#how-the-slop-pass-works)

## The register

Write as a working practitioner explaining something to a competent colleague who
happens not to know this particular thing. Not a lecturer, not a marketer, not a
cheerful docs site.

- **Second person for instructions, first person plural only when genuinely joint work.** "You'll need a lexer" — not "we will now construct a lexer" unless the reader is building it alongside you.
- **The author appears when judgement is involved, and recedes otherwise.** "I'd reach for a hash map here, though a sorted vector wins below about fifty entries" is good. Mechanism description needs no narrator.
- **Uncertainty is registered honestly and specifically.** "This is the part I find genuinely hard to reason about" beats a confident gloss. If the literature disagrees, say so and say who.
- **Assume intelligence, never assume knowledge.** The reader can follow a hard argument. They may not know the jargon. Define terms on first use, in-line, without ceremony.
- **Concrete before abstract, always.** Show the specific failing program, then name the general principle. Never open a section with a definition.

## Sentences and paragraphs

- Vary sentence length deliberately. A run of same-length sentences is the single most recognisable tell of machine prose. Follow a long, qualified sentence with a short one.
- One idea per paragraph. Three to six sentences is the usual range; a one-sentence paragraph is a legitimate emphasis device, used sparingly.
- Prefer the active voice, but use the passive when the actor genuinely doesn't matter: "the buffer is flushed on every newline" is fine.
- Cut every sentence that only announces what the next sentence will do.
- No section may open with a restatement of its own heading.

## Technical precision

This is where technical writing earns its keep, and where the editing passes are
strictest.

- **Terminology is fixed for the whole book.** Pick one name per concept and never vary it for elegance. If you call it a "token stream" in chapter 2, it is a token stream in chapter 9. Synonym cycling reads as sophistication and costs the reader real effort.
- **Preserve degrees of certainty exactly.** "Suggests", "indicates", "is measured at", "is guaranteed to" are different claims. Never upgrade a hedge into a fact because the sentence reads better.
- **Attribute specifically or not at all.** "Studies show" is worthless. Name the paper, the system, or the benchmark, or drop the claim.
- **Exact, neutral verbs.** "The parser rejects the input" — not "the parser struggles with" or "the parser gracefully handles".
- **Every number carries its units and its conditions.** "40% faster" is meaningless without saying than what, on what, measured how.
- **Never describe code the reader can see.** If the listing shows a loop, don't write "this loops over the items". Explain *why* it's a loop, or what breaks if it isn't.

## The slop ban-list

These 21 patterns are the recognisable signature of machine-written prose. They are
drawn from `petergyang/no-ai-slop`, which is the most widely-validated catalogue of
the failure. Every one is banned.

| # | Pattern | Example of the failure |
|---|---|---|
| 1 | Binary contrast | "It's not just a parser. It's a contract." |
| 2 | Throat-clearing opener | "Here's the thing." / "Let's dive in." |
| 3 | Faux-insight setup | "What most people get wrong about closures…" |
| 4 | Colon reveal | "The result: a faster parser." |
| 5 | Trailing `-ing` analysis | "…, highlighting the importance of immutability." |
| 6 | Importance puffery | "stands as a testament to", "a pivotal moment in" |
| 7 | Interpretive metadiscourse | "That matters more than it sounds." |
| 8 | Weasel attribution | "Studies show", "experts agree", "it's widely known" |
| 9 | Fake-strong verbs | "serves as a centralized hub for", "plays a key role in" |
| 10 | Synonym cycling | calling one thing a token, then a lexeme, then a symbol |
| 11 | Negative listing | "Not a framework. Not a library. A philosophy." |
| 12 | Dramatic fragmentation | "And that changes everything." |
| 13 | Robotic rhythm | every sentence 14–18 words |
| 14 | Rhetorical setup | "What if I told you…", "But here's where it gets interesting" |
| 15 | Fake-profound kicker | ending a section on a portentous one-liner |
| 16 | Summary-recap ending | "In conclusion", "To sum up", "In this chapter we saw" |
| 17 | Formatting slop | emoji in headings, mid-sentence bold, a heading over two sentences |
| 18 | Em-dash overuse | more than roughly one per 400 words |
| 19 | Banned vocabulary | see below |
| 20 | Empty adverbs | "just", "simply", "literally", "honestly", "basically" |
| 21 | Empty phrases | "it's worth noting that", "at the end of the day", "needless to say" |

Two clarifications, because over-correction is its own failure:

- **"Simply" and "just" are banned as filler, not as English.** "The scanner simply
  returns the longest match" is filler. "Just the first byte is read" is a real
  quantifier and is fine.
- **A colon before a genuine list or definition is correct punctuation.** Pattern 4
  is about the theatrical single-noun reveal, not about colons.

## Words and constructions to avoid

**Nouns and verbs:** delve, leverage (as a verb), empower, streamline, robust,
seamless, unlock, harness, utilize (say "use"), facilitate, showcase, underscore,
navigate (unless literal), foster, elevate, craft (as a verb), embark, realm,
landscape, tapestry, ecosystem (unless literally biological or a real software
ecosystem), game-changer, paradigm shift, transformative, revolutionary, cutting-edge,
state-of-the-art, best-in-class, powerful (of software), rich (of a feature set).

**Constructions:** "In today's fast-paced world", "As we've seen", "It is important
to note", "One of the most", "plays a crucial role", "a wide range of", "a variety
of", "the world of X", "when it comes to", "at its core", "under the hood" (once per
book at most), "think of it as" (once per chapter at most).

**Openings that are always wrong:** "In this chapter, we will…", "Before we begin,
let's…", "Let's start by…", "Welcome to…".

## What good looks like

Rules describe the floor. These pairs show the target. Every "before" is the kind
of sentence that passes a ban-list check and is still bad writing.

**Explain the why, never the what.** The reader can see the code.

> **Before:** This function loops over the values and adds them to a total, then
> divides by the length of the list to get the average.
>
> **After:** The count is read separately from the sum, so an empty input fails at
> the division rather than at the addition. That is why the traceback points one
> line further down than you would expect.

**Lead with the concrete case, name the principle after.**

> **Before:** Thompson's construction guarantees a linear bound on state count,
> which is what enables efficient simulation over the input.
>
> **After:** `a*a*a*b` is seven characters and compiles to eight states. Add
> another star and you get ten. The machine never grows with the input, only with
> the pattern.

**Give the number.**

> **Before:** This is significantly faster on large inputs.
>
> **After:** At 4,000 characters it finishes in 8.6 ms. Chapter 1's matcher could
> not reach 100.

**Own the judgement instead of hedging it.**

> **Before:** It might be considered somewhat preferable to use a set here in most
> cases.
>
> **After:** Use a set. A list works and turns the inner loop quadratic, which you
> will not notice until the input is real.

**Say what it does, not how important it is.**

> **Before:** The `Split` state is a crucial component that plays a key role in
> enabling the powerful simulation capability.
>
> **After:** `Split` says "both, at once". A pattern string has no way to express
> that, which is the whole reason the machine can do something the string cannot.

**Admit the limit.** A book that only lists wins is not trusted on the wins.

> **Before:** This approach provides excellent performance characteristics for
> regular expression matching.
>
> **After:** You give up capture groups, backreferences and lookaround. For a
> server parsing untrusted input that is usually the right trade; for a text editor
> it usually is not.

**Vary the sentence length deliberately.** A paragraph of 15-word sentences reads
as machine output even when every sentence is true. Follow a long, qualified
sentence with a short flat one. The short one is where the reader breathes.

## Read it aloud

Nystrom's last pass on every chapter of *Crafting Interpreters* was reading it
aloud for cadence. Do the same before handing a chapter to the editor: read the
whole thing, out loud or in an inner voice slow enough to notice. Where you
stumble, the reader will. Where you speed up, you are skimming your own filler.
Fix both.

## How the slop pass works

The slop pass runs `detect` semantics, not rewrite semantics. For each hit:

1. Name the pattern by number.
2. Quote the offending line verbatim.
3. Give a one-line fix.
4. Apply the **minimum effective edit** — change the clause, not the paragraph.

Do not rewrite a passage that has one bad sentence in it. Do not "improve" prose that
merely differs from your taste. The goal is removing a recognisable defect, and a
heavy rewrite loses the chapter's voice while introducing fresh slop of its own.

**A prompt-level ban is not sufficient on its own.** Models under explicit instruction
to avoid em dashes have been measured still emitting them at 9.1 per thousand words.
So this pass is a mechanical re-read of the finished text, not a hope expressed at
drafting time. Run it, and count.

### The checks worth counting

Run these over each drafted chapter and act on what they show:

```bash literal why="the shape of the slop pass; run against a real chapter file"
# em dashes per 1000 words -- flag above ~1
# sentence-length variance -- flag a standard deviation below ~5 words
# banned vocabulary -- exact word-boundary matches from the list above
# terminology drift -- the same concept named two different ways across chapters
```

Uniform sentence length is the check most worth running, because it is invisible when
you read your own draft and obvious to every reader.
