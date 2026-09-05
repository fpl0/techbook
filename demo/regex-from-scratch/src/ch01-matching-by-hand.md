# Chapter 1: Matching by Hand

<span class="newthought">Here is a regular expression</span> that will hang your
program. Not for a long time — forever, on a modern machine, for an input of about
thirty characters.

```python run env=ch1 file=code/pathological.py caption="Innocent-looking, and catastrophic." highlight=4
import re

pattern = re.compile(r"(a+)+b")
print(pattern.match("aaaaaaaaaaaaaaaaaaaaaab") is not None)
```

```output
True
```

That one returns quickly. Remove the final `b` so the match must fail, and Python's
engine explores every way of splitting the `a`s between the inner and outer group
before it gives up. Each additional `a` doubles the work.

<div class="orient">
<h3>What you'll learn</h3>
<ul>
<li>Match a small regex language by hand, with nothing but recursion</li>
<li>Explain why backtracking engines have a worst case that is exponential</li>
<li>Read a regex as a structure rather than as a string of punctuation</li>
</ul>
<h3>Assumes you know</h3>
<p>Python functions, recursion, and slicing. No automata theory — that arrives in
chapter 2, once you have felt why it is needed.</p>
<p class="meta">~25 min · 4 exercises</p>
</div>

## The smallest language worth building

Real regex syntax is enormous, and almost none of it is interesting. We will
implement four constructs, which is enough to be genuinely useful and small enough to
hold in your head:

| Syntax | Meaning |
|---|---|
| `a` | the literal character `a` |
| `.` | any single character |
| `ab` | concatenation: `a` then `b` |
| `a*` | zero or more `a` |

No alternation yet, no `+`, no character classes. We add alternation in chapter 2,
where it costs almost nothing; here it would double the code for one idea.

## Matching, recursively

The whole matcher is one insight: **`match(pattern, text)` asks whether the pattern
consumes some prefix of the text, and the pattern's first element decides what to try
next.**

Start with the case that has no star in it.

```python run env=ch1 file=code/simple.py caption="Literal and dot matching, without repetition."
def match_here(pattern, text):
    if not pattern:
        return True
    if pattern[0] == "." or (text and pattern[0] == text[0]):
        return match_here(pattern[1:], text[1:])
    return False

print(match_here("a.c", "abc"), match_here("a.c", "axc"), match_here("a.c", "ab"))
```

```output
True True False
```

<ol class="annot">
<li>An empty pattern matches anything, including the empty string. This is the base case, and getting it wrong is the most common bug in a first attempt.</li>
<li><code>text and</code> guards the index: a pattern that still has characters left cannot match text that has run out.</li>
<li>Both branches recurse on <em>both</em> tails, because one pattern element consumed exactly one text character.</li>
</ol>

<details>
<summary>Predict: what does <code>match_here("", "abc")</code> return, and is that right?</summary>

<p><code>True</code>. The empty pattern matched the empty prefix of <code>"abc"</code>
and stopped. That is correct for a <em>prefix</em> matcher, which is what we are
building — it answers "does this pattern start here?", not "does it consume
everything?". Anchoring to the end is exercise 3.</p>

</details>

## Adding the star

`a*` is where the difficulty lives, because it is the first construct that does not
consume a fixed amount of text. The pattern element is now two characters wide, and
it can match any number of characters from zero upward.

The standard move is to try every count. Try zero first, then one, then two, and
return as soon as one of them works.

```python run env=ch1 file=code/star.py caption="The complete matcher. The star case is the whole story." highlight=3-4
def match_here(pattern, text):
    if not pattern:
        return True
    if len(pattern) >= 2 and pattern[1] == "*":
        return match_star(pattern[0], pattern[2:], text)
    if pattern[0] == "." or (text and pattern[0] == text[0]):
        return match_here(pattern[1:], text[1:])
    return False


def match_star(c, pattern, text):
    i = 0
    while True:
        if match_here(pattern, text[i:]):
            return True
        if i < len(text) and (c == "." or text[i] == c):
            i += 1
        else:
            return False


def match(pattern, text):
    return any(match_here(pattern, text[i:]) for i in range(len(text) + 1))


for p, t in [("a*b", "aaab"), ("a*b", "b"), ("a.*z", "abcz"), ("a*b", "aaac")]:
    print(f"{p!r:8} {t!r:8} {match(p, t)}")
```

```output
'a*b'    'aaab'   True
'a*b'    'b'      True
'a.*z'   'abcz'   True
'a*b'    'aaac'   False
```

Note the order inside `match_star`: it tries the *shortest* match first, growing only
when the rest of the pattern fails. That makes this a lazy matcher. Real engines are
greedy by default, which changes which match you get but not whether one exists.

<div class="callout">
<div class="title">This trips people up</div>
<p><code>match_star</code> checks <code>match_here(pattern, ...)</code> — the pattern
<em>after</em> the star, not including it. Passing the full pattern is the classic
error, and it produces infinite recursion rather than a wrong answer, which at least
fails loudly.</p>
</div>

## Why this gets slow

The matcher above is correct and short. It is also, on some inputs, unusable.

Consider `a*a*a*b` against a string of `a`s with no `b`. Every `a` in the text can be
claimed by the first star, the second, or the third. The matcher tries every
assignment before it can conclude failure.

Measure it rather than trusting the claim. The block below doubles the input twice and
prints the cost each time.

```python run env=ch1 caption="Cost against input length, at a fixed three stars."
import time

for n in (10, 20, 40, 60):
    text = "a" * n
    start = time.perf_counter()
    match("a*a*a*b", text)
    print(f"n={n:3}  {(time.perf_counter() - start) * 1000:9.2f} ms")
```

```output
n= 10       0.20 ms
n= 20       1.90 ms
n= 40      22.57 ms
n= 60     104.08 ms
```

Doubling the input from 20 to 40 does not double the time; it multiplies it by
roughly twelve. That is the signature of a polynomial with a degree above one. Add a
fourth star and the same doubling costs about twenty times more, because the degree
of the polynomial is set by *how many stars can compete for the same character*, not
by the length of the input.

<figure>
<svg viewBox="0 0 800 208" role="img" aria-labelledby="dia-1-1-title">
  <title id="dia-1-1-title">Three stars dividing a run of six a-characters, showing the many ways the same input can be split between them</title>
  <g font-family="var(--font-ui)" font-size="13" fill="var(--dia-muted)">
    <text x="24" y="32">One input. Every division of it is a path the matcher must try.</text>
  </g>
  <g font-family="var(--font-code)" font-size="15" fill="var(--dia-fg)">
    <text x="24" y="88">a a a a a a</text>
    <text x="24" y="136">a a a a a a</text>
    <text x="24" y="184">a a a a a a</text>
  </g>
  <g stroke="var(--dia-accent)" stroke-width="2.5" fill="none">
    <path d="M 132 72 L 132 96"/><path d="M 168 72 L 168 96"/>
    <path d="M 60 120 L 60 144"/><path d="M 204 120 L 204 144"/>
    <path d="M 96 168 L 96 192"/><path d="M 132 168 L 132 192"/>
  </g>
  <g font-family="var(--font-ui)" font-size="13" fill="var(--dia-muted)">
    <text x="264" y="88">3 / 1 / 2</text>
    <text x="264" y="136">1 / 4 / 1</text>
    <text x="264" y="184">2 / 1 / 3</text>
    <text x="420" y="136">…and 25 more</text>
  </g>
</svg>
<figcaption>Figure 1-1. With three stars and six characters there are 28 divisions.
The count grows as a polynomial whose degree is the number of competing stars.</figcaption>
</figure>

Our four-construct language cannot do worse than polynomial, because it has no way to
nest one repetition inside another. Real regex syntax can, and that is where the
genuinely exponential case lives — the `(a+)+b` from the opening of this chapter. The
outer `+` repeats a group that itself repeats, so the number of paths doubles with
each added character rather than growing polynomially.<label for="sn-1-1" class="margin-toggle sidenote-number"></label>
<input type="checkbox" id="sn-1-1" class="margin-toggle">
<span class="sidenote">Cloudflare's global outage of 2 July 2019 was caused by a
single regular expression containing nested quantifiers, deployed to their WAF. It
consumed CPU across the fleet.</span>

Both failures share one cause: the matcher explores one candidate division at a time
and, on failure, starts another. Nesting changes how fast the path count grows. It
does not introduce the problem.

## Practice

<div class="exercises">

<div class="exercise">
<span class="label">Exercise</span>
<p>Fill the single blank so <code>match_here</code> also supports <code>?</code>
(zero or one).</p>

```python literal why="exercise stub the reader completes; intentionally incomplete"
if len(pattern) >= 2 and pattern[1] == "?":
    if pattern[0] == "." or (text and pattern[0] == text[0]):
        if match_here(pattern[2:], text[1:]):
            return True
    return ____
```

<details><summary>Solution</summary>
<p><code>match_here(pattern[2:], text)</code> — the zero-occurrence branch. Order
matters: trying the one-occurrence branch first makes <code>?</code> greedy, which is
what every real engine does.</p>
</details>
</div>

<div class="exercise">
<span class="label">Exercise</span>
<p>Add <code>^</code> anchoring. Complete the stub.</p>

```python literal why="exercise stub; intentionally incomplete"
def match(pattern, text):
    if pattern.startswith("^"):
        return ____
    return any(match_here(pattern, text[i:]) for i in range(len(text) + 1))
```

<details><summary>Solution</summary>
<p><code>match_here(pattern[1:], text)</code>. An anchored pattern tries position zero
only, which is why anchoring a slow pattern often makes it fast — it removes the outer
loop over starting positions, though not the inner exponential blowup.</p>
</details>
</div>

<div class="exercise">
<span class="label">Exercise</span>
<p>Write <code>full_match(pattern, text)</code> from scratch: true only if the pattern
consumes the entire text. Do not modify <code>match_here</code>.</p>
</div>

<div class="exercise">
<span class="label">Exercise</span>
<p>Transfer: unmemoized recursive Fibonacci has the same shape as <code>(a+)+</code>,
and counting coin-change combinations has the same shape as <code>a*a*a*</code>. Say
in one sentence what distinguishes the two shapes, before reading chapter 2.</p>
</div>

</div>

## What to remember

- A pattern element decides what to try next; matching is recursion over both the pattern and the text
- An empty pattern matches successfully, and that base case carries the whole recursion
- The star case tries every repetition count, and that is where the cost lives
- Stars competing for the same characters give polynomial cost, with the degree set by how many compete
- Nested repetition, which our language cannot express, is what makes the cost exponential
- Both are properties of the *search strategy*, not of regular expressions themselves

**Terms introduced:** backtracking, anchoring, greedy and lazy matching, nested
quantifier, catastrophic backtracking.

## Next

The exponential cost comes from exploring one path at a time and starting over on
failure. What if the matcher could be in several states at once?
