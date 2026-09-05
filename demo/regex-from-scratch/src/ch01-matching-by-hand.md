# Chapter 1: Matching by Hand

Seven characters of pattern, twenty-four characters of text, and Python's own regular expression engine needs half a second to answer "no". Listing 1-1 asks `(a+)+b` to match a string of a's that contains no `b`, adds one `a` per row, and prints the ratio between each row and the one before it. Watch the last column.

```python run nondet=output file=code/blowup.py caption="Python's `re` on `(a+)+b` against a string of a's, one more per row."
"""How long does a failing match take as the input grows by one character?"""
import re
import time


def seconds(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


if __name__ == "__main__":
    pattern = re.compile(r"(a+)+b")
    previous = None
    for n in range(18, 25):
        text = "a" * n
        t = seconds(lambda: pattern.fullmatch(text))
        ratio = f"{t / previous:4.1f}x" if previous else "    "
        print(f"n={n}  {t * 1000:8.1f} ms  {ratio}")
        previous = t
```

```output
n=18       8.7 ms      
n=19      16.4 ms   1.9x
n=20      30.3 ms   1.8x
n=21      58.4 ms   1.9x
n=22     116.7 ms   2.0x
n=23     233.0 ms   2.0x
n=24     465.4 ms   2.0x
```

Every extra character doubles the time. Thirty characters would cost about half a minute and forty would run for most of a day. The machine is an Apple Silicon Mac running CPython 3.14, and every timing in this book comes from it, single run, unless the listing says otherwise. This is not a Python quirk. Russ Cox measured the same doubling in Perl in 2007 and listed [Perl, PCRE, Python, Ruby and Java](https://swtch.com/~rsc/regexp/regexp1.html) as engines built the same way. To see where the doubling comes from, build the matcher yourself. It takes thirty lines.

<div class="orient">
  <h3>What you'll learn</h3>
  <ul>
    <li>Write a recursive matcher for literals, <code>.</code>, concatenation and <code>*</code> from nothing</li>
    <li>Trace by hand which alternatives a star tries, and in what order</li>
    <li>Predict whether a pattern's failing case grows linearly, polynomially or exponentially with the input</li>
    <li>Read a regex post-mortem and name the kind of blow-up it describes</li>
  </ul>
  <h3>Assumes you know</h3>
  <p>Python functions, recursion and string slicing. Nothing about automata, and nothing about how <code>re</code> works inside.</p>
  <p class="meta">~40 min · 4 exercises</p>
</div>

<div class="crux">
  <div class="title">The crux</div>
  <p>A pattern can describe a text in more than one way. <code>a*a*</code> can account for <code>aaa</code> in four ways, and <code>a*a*b</code> in none, but the matcher cannot know that until it has tried all four. When the first way fails, who remembers the others, and how many are there?</p>
</div>

## The smallest language worth building

The pattern language for this chapter fits in a four-row table.

| Construct | Written | Matches |
|---|---|---|
| literal | `a` | that one character |
| dot | `.` | any one character |
| concatenation | `ab` | `a` and then `b`, adjacent |
| star | `a*` | zero or more of the character before it |

Everything you use daily is missing: `+`, `?`, alternation, parentheses, classes, anchors. That is deliberate, and the precedent is old. When Brian Kernighan needed a matcher small enough to teach from, Rob Pike wrote one for literal, dot, star and the two anchors, and Kernighan later wrote that in his own day-to-day use this class ["easily accounts for 95 percent of all instances"](https://www.cs.princeton.edu/courses/archive/spr09/cos333/beautiful.html). That is one experienced person's estimate, not a measurement, and it is enough to justify the cut.<label for="sn-1-1" class="margin-toggle sidenote-number"></label><input type="checkbox" id="sn-1-1" class="margin-toggle"><span class="sidenote">Kernighan's account of how long the thirty lines took is hedged in the original: Pike reappeared "at least as I remember it now" within "an hour or two". The hedge is part of the story.</span>

The star is the only construct here that can match in more than one way, so the star is where every interesting question in this chapter comes from. `+`, `?`, alternation and groups arrive in chapter 2, when there is a machine to hold them.

## Matching, recursively

In Listing 1-2, watch which function consumes pattern and which consumes text. They advance separately, and a star can advance the text by any amount while advancing the pattern by two.

```python run file=code/backtrack.py caption="The whole matcher. Three functions, no state outside the call stack."
"""A backtracking matcher for literals, dot and star, in the style of Pike's."""


def match_here(pattern, text):
    """Does `pattern` match at the very start of `text`?"""
    if pattern == "":
        return True
    if len(pattern) > 1 and pattern[1] == "*":
        return match_star(pattern[0], pattern[2:], text)
    if text and pattern[0] in (".", text[0]):
        return match_here(pattern[1:], text[1:])
    return False


def match_star(ch, rest, text):
    """Match zero or more `ch`, then `rest`. Longest run first, then give back."""
    i = 0
    while i < len(text) and (ch == "." or text[i] == ch):
        i += 1
    while i >= 0:
        if match_here(rest, text[i:]):
            return True
        i -= 1
    return False


def search(pattern, text):
    """Does `pattern` match anywhere in `text`?"""
    for start in range(len(text) + 1):
        if match_here(pattern, text[start:]):
            return True
    return False
```

<ol class="annot">
<li>Lines 6 and 7. The base case is an empty <em>pattern</em>, not an empty text. <code>a*</code> has to match <code>""</code>, and a pattern that has run out has nothing left to demand. Because every recursive call strips one construct off the pattern, this is the only place a <code>True</code> can originate.</li>
<li>The star test at lines 8 and 9 peeks one character ahead before the current character gets a say. A star is a property of a <em>pair</em>. If this test came after the literal test, <code>a*</code> would consume an <code>a</code> and never see the star at all.</li>
<li>Lines 17 to 24. <code>match_star</code> takes the longest run it can, then <strong>gives back</strong> one character at a time, asking <code>match_here</code> about the remainder after each. Pike's original starts at zero repetitions and counts up, which Kernighan calls a "shortest match". Ours follows Python's <code>re</code>, which repeats as often as it can and then ["will back up and try again with fewer repetitions"](https://docs.python.org/3/howto/regex.html). Same alternatives, opposite order, same worst case.</li>
<li><code>search</code>, lines 29 to 32, tries every start position, including the one past the last character. That is not off by one: <code>a*</code> matches the empty tail, and so does the empty pattern. Kernighan's C carries the comment "must look even if string is empty" for the same reason.</li>
</ol>

The anchored question composes and the unanchored one does not, which is why `match_here` asks only whether the pattern matches *at the start* of the text. Any suffix can be handed to it for a meaningful answer, so `match_star` does exactly that, and `search` is one loop on top. This is **backtracking**. Each choice point holds its remaining alternatives on the call stack, and a failure below returns control to the nearest choice that still has one. If you have written a recursive-descent parser or a sudoku solver, you have met it. In Listing 1-3 the fourth line is the one to notice.

```python run caption="The matcher on inputs that succeed, fail, and succeed for a reason you might not expect."
import backtrack

print(backtrack.match_here("a*b", "aaab"))
print(backtrack.match_here("a*b", "b"))
print(backtrack.match_here(".*c", "abc"))
print(backtrack.match_here("a*b", "ba"))
print(backtrack.search("a*b", "xxab"))
print(backtrack.search("a*b", "xxa"))
```

```output
True
True
True
True
True
False
```

The text `ba` matches `a*b` at its start because zero a's is a run, and the `a` after the `b` is never examined. **`match_here`** answers a question about a prefix and says nothing about what follows. If you want the whole text consumed, check that the text is empty when the pattern is; Python's engine calls that distinction `match` versus `fullmatch`.

<details>
  <summary>Predict: what does <code>match_here("a*a", "aaa")</code> return, and how many characters does the star end up keeping?</summary>
  <p><code>True</code>, with the star keeping two. It first takes all three, then asks whether <code>a</code> matches the empty string, which it does not. It gives one back, the remainder is <code>a</code>, the literal matches, and the call returns. A star that never gave anything back would return <code>False</code> here. Giving back is what makes the answer correct, not an optimisation on top of it.</p>
</details>

## Where the time goes

Run `a*a*a*b` against `aaaa` in your head. The first star takes all four a's, the second and third find nothing and keep zero, and `b` meets the empty string and fails. Now the unwinding starts, innermost first. The third star has nothing to give back, nor has the second, so the first gives back one `a`. The second star takes it, the third takes none, `b` fails again. The second gives its `a` back, the third takes it, `b` fails. And so on, until the first star has surrendered all four and every way of splitting four a's across three stars has been tried and rejected.

Each star is a loop over how many characters it keeps, and each loop sits inside the one before it. Three stars make three nested loops over an input of length n, which is about n³ calls. Figure 1-1 draws the two-star case on a three-character input, where the count is small enough to check by hand.

<figure>
<svg viewBox="0 0 800 328" role="img" aria-labelledby="dia-1-1-title">
  <title id="dia-1-1-title">The first star of a*a*b takes all three a's, then gives them back one at a time; each give-back restarts the second star, which fails b on every suffix</title>
  <defs>
    <marker id="arrow-ch1" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--dia-muted)"/>
    </marker>
  </defs>

  <g fill="var(--dia-fill)" stroke="var(--dia-fg)" stroke-width="1.5">
    <rect x="272" y="16" width="256" height="56" rx="4"/>
    <rect x="16"  y="144" width="176" height="56" rx="4"/>
    <rect x="208" y="144" width="176" height="56" rx="4"/>
    <rect x="400" y="144" width="176" height="56" rx="4"/>
    <rect x="592" y="144" width="192" height="56" rx="4"/>
  </g>
  <g fill="var(--dia-fill)" stroke="var(--dia-warn)" stroke-width="2.5">
    <rect x="208" y="264" width="384" height="48" rx="4"/>
  </g>

  <g font-family="var(--font-ui)" font-size="16" fill="var(--dia-fg)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="400" y="36">match_star('a', 'a*b', 'aaa')</text>
    <text x="400" y="56" fill="var(--dia-muted)">first star keeps 3, then gives back</text>
    <text x="104" y="164">a*b vs ''</text>
    <text x="104" y="184" fill="var(--dia-muted)">second star keeps 0</text>
    <text x="296" y="164">a*b vs 'a'</text>
    <text x="296" y="184" fill="var(--dia-muted)">keeps 1, gives back 1</text>
    <text x="488" y="164">a*b vs 'aa'</text>
    <text x="488" y="184" fill="var(--dia-muted)">keeps 2, gives back 2</text>
    <text x="688" y="164">a*b vs 'aaa'</text>
    <text x="688" y="184" fill="var(--dia-muted)">keeps 3, gives back 3</text>
    <text x="400" y="288" fill="var(--dia-warn)">match_here('b', suffix) fails 1 + 2 + 3 + 4 = 10 times</text>
  </g>

  <g font-family="var(--font-ui)" font-size="15" fill="var(--dia-accent)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="216" y="104">keep 3</text>
    <text x="328" y="104">give back 1</text>
    <text x="472" y="104">give back 2</text>
    <text x="600" y="104">give back 3</text>
  </g>

  <g stroke="var(--dia-muted)" stroke-width="1.5" fill="none" marker-end="url(#arrow-ch1)">
    <path d="M 336 72 L 128 136"/>
    <path d="M 368 72 L 304 136"/>
    <path d="M 432 72 L 480 136"/>
    <path d="M 464 72 L 672 136"/>
    <path d="M 104 200 L 232 256"/>
    <path d="M 296 200 L 336 256"/>
    <path d="M 488 200 L 456 256"/>
    <path d="M 688 200 L 568 256"/>
  </g>
</svg>
<figcaption>Figure 1-1. Every give-back by the outer star restarts the inner star from scratch, and the inner star re-checks suffixes the previous round already rejected. Nothing remembers a failure.</figcaption>
</figure>

Nothing in the tree remembers that `b` already failed against `aa`; the next round of the inner star checks it again, and the round after that checks it a third time. Listing 1-4 doubles the input to the three-star pattern and prints the ratio between rows. The ratio is the claim; the milliseconds are not.

```python run nondet=output caption="Doubling the input to `a*a*a*b`, with the ratio between rows."
import time
import backtrack

pattern = "a*a*a*b"
previous = None
for n in (40, 80, 160, 320):
    text = "a" * n
    t0 = time.perf_counter()
    backtrack.match_here(pattern, text)
    t = time.perf_counter() - t0
    ratio = f"{t / previous:4.1f}x" if previous else "    "
    print(f"n={n:<4} {t * 1000:8.1f} ms  {ratio}")
    previous = t
```

```output
n=40        2.2 ms      
n=80       15.5 ms   7.1x
n=160     106.1 ms   6.8x
n=320     822.2 ms   7.7x
```

Doubling the input multiplies the time by about eight, which is what n³ predicts. This is a **polynomial blow-up**: bad, but bounded by a power of the input length, and not the doubling per character of Listing 1-1. Exponential cost needs a quantifier *inside* a quantifier, so that each character multiplies the number of ways to split the text instead of adding one loop level. The standard example is `(a+)+b`. Davis and colleagues name the shape [star height greater than one](https://davisjam.github.io/files/publications/DavisCoghlanServantLee-EcosystemREDOS-ESECFSE18.pdf); **star height** is the deepest nesting of stars or pluses in a pattern. This chapter's language cannot reach star height two, because a star can only follow a single character. Exponential blow-up is the one failure its matcher is structurally incapable of.

<details>
  <summary>Predict: <code>a*b</code> has one star. Does its failing case grow linearly, quadratically or cubically?</summary>
  <p>Linearly. One star means one loop: it keeps all n a's, then gives back one at a time, and each give-back costs one <code>match_here("b", ...)</code> call, which fails in constant time. About n calls in all. Add a second star and each of those calls becomes a loop of its own. Each star multiplies by n; it is the count of stars that sets the exponent.</p>
</details>

## The incidents

Neither of the two regex outages below was exponential. On 20 July 2016, Stack Overflow was down for [34 minutes](http://web.archive.org/web/20221011090116/https://www.stackstatus.net/post/147710624694/outage-postmortem-july-20-2016) because a comment held roughly 20,000 consecutive spaces and the home page trimmed trailing whitespace with a pattern that simplifies to `\s+$`. The engine took the whole run, found a non-space after it, gave the spaces back one at a time, then moved one start position along and did it all again: 20,000 + 19,999 + 19,998 and so on down to 1, which is 199,990,000 steps. The post-mortem's own words are that "this is not classic catastrophic backtracking", since the cost is O(n²) rather than exponential, "but it was enough". The fix was a substring function.

On 2 July 2019, Cloudflare had a global outage of [about 27 minutes](https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/) after a firewall rule containing `.*(?:.*=.*)` reached production. The post reduces the culprit to `.*.*=.*` and counts the engine's steps: 23 for `x=x`, 33 for `x=xx`, 45 for `x=xxx`, and 555 for `x=` followed by twenty x's. The post says of those numbers only "that's not linear". It never uses the word exponential, and the series grows like a square: two adjacent stars, one give-back loop inside another, run on every request through the firewall.<label for="sn-1-2" class="margin-toggle sidenote-number"></label><input type="checkbox" id="sn-1-2" class="margin-toggle"><span class="sidenote">Cloudflare's post credits the fix to a 1968 paper by Ken Thompson and names RE2 and Rust's regex crate as engines with run-time guarantees. Chapter 3 builds Thompson's idea.</span>

Both patterns look harmless, both are polynomial, and both took a large service down. The term **catastrophic backtracking** usually means the exponential case, and Davis and colleagues use it that way, but the practical lesson is the smaller one. Quadratic on a hot path is enough.

<div class="callout">
  <div class="title">This trips people up</div>
  <p>"Our inputs are short, so we are safe." The length that matters is the part the pattern fails on, and Listing 1-1 needs 24 characters to reach half a second. A form field, a header, a URL path: all of them are longer than that, and an attacker chooses the content. The safe question is not how long the input is but how many distinct splits of it the pattern can try.</p>
</div>

Recursion has a limit of its own, and the real error is worth meeting once. Listing 1-5 matches a 1,500-character pattern against an identical text, which succeeds in principle and fails in practice.

```python expect-error expect="RecursionError" caption="Every literal consumed is one more frame. The pattern is the recursion depth."
import backtrack

print(backtrack.match_here("a" * 1500, "a" * 1500))
```

```output
Traceback (most recent call last):
  File "snippet.py", line 3, in <module>
    print(backtrack.match_here("a" * 1500, "a" * 1500))
          ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "code/backtrack.py", line 11, in match_here
    return match_here(pattern[1:], text[1:])
  File "code/backtrack.py", line 11, in match_here
    return match_here(pattern[1:], text[1:])
  File "code/backtrack.py", line 11, in match_here
    return match_here(pattern[1:], text[1:])
  [Previous line repeated 996 more times]
RecursionError: maximum recursion depth exceeded
```

The three frames shown, the 996 repeats and the caller make a thousand, the default limit CPython ships with. The pattern sets the depth, not the text, because a star consumes any amount of text in one frame while each literal costs a frame of its own. Pike's C version has the same shape and relies on the C stack being deep enough. Recursion bought thirty lines and a matcher you can hold in your head; the price is a hard limit on pattern length, and a matcher in which no abandoned path leaves any trace behind.

## Practice

<div class="exercises">
  <div class="exercise">
    <span class="label">Exercise 1</span>
    <p>Pike's matcher supports <code>^</code>. Fill in the blank so that a pattern beginning with <code>^</code> is tried at position 0 only.</p>

```python literal why="exercise stub"
def search(pattern, text):
    if pattern.startswith("^"):
        return match_here(________, text)
    for start in range(len(text) + 1):
        if match_here(pattern, text[start:]):
            return True
    return False
```

    <details><summary>Solution</summary><p><code>pattern[1:]</code>. The anchor is not a character to match but an instruction to <code>search</code> about which start positions are allowed, so <code>match_here</code> never sees it. Kernighan handles it in the same place.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 2</span>
    <p>Add <code>+</code> for a single character by rewriting. Complete the stub so that <code>x+</code> means <code>x</code> followed by <code>x*</code>.</p>

```python literal why="exercise stub"
def match_here(pattern, text):
    if pattern == "":
        return True
    if len(pattern) > 1 and pattern[1] == "+":
        return match_here(________, text)
    ...
```

    <details><summary>Solution</summary><p><code>pattern[0] + pattern[0] + "*" + pattern[2:]</code>. The ordinary literal case matches the one mandatory character on the next call and the star does the rest, at the cost of one extra frame and no new logic. It also shows why <code>+</code> does not change the blow-up class: <code>a+a+b</code> is <code>aa*aa*b</code>, two stars, quadratic.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 3</span>
    <p>Wrap <code>match_here</code> in a counting function and record how many calls it receives for <code>a*a*b</code> against <code>"a" * n</code>, for n from 1 to 8. Describe the growth.</p>
    <details><summary>Solution</summary><p>A wrapper that increments a counter and then calls the original gives 6, 10, 15, 21, 28, 36, 45, 55. The differences are 4, 5, 6, 7, 8, 9, 10, so the count is (n+2)(n+3)/2: quadratic, two stars, two nested loops. The wrapper must replace <code>backtrack.match_here</code> itself rather than a local name, because <code>match_star</code> looks the function up in the module at call time.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 4</span>
    <p>"Take the most you can, then give back until something downstream is satisfied" is not a regex idea. Name two other places in systems you have used where the same strategy appears, and say what plays the role of the star.</p>
    <details><summary>Solution</summary><p>A lexer with maximal munch reads the longest token it can and, in some designs, backs up when the parser rejects it; the token boundary is the star. A backtracking parser for an ambiguous grammar tries the longest production first. A first-fit allocator that splits a block and later coalesces it is a weaker cousin. In every case the cost question is the same: how many alternatives does each choice point hold, and how many choice points are nested.</p></details>
  </div>
</div>

## Mental model

- A backtracking matcher is a recursive function that asks whether the pattern matches at the start of the text, plus a loop that tries every start.
- A star keeps the longest run it can and gives back one character per failed attempt. The alternatives live on the call stack and nowhere else.
- A star is a loop over how many characters it keeps. Adjacent stars nest their loops, so k stars cost about n^k on a failing input.
- Exponential cost needs a quantifier inside a quantifier. Star height one caps this matcher at polynomial.
- Recursion depth equals the number of literals in the pattern, so a long pattern fails before a long text does.

**Terms introduced:** backtracking — a search strategy in which each choice point keeps its untried alternatives and a failure returns control to the nearest one that still has some; match_here — the recursive core of the matcher, which asks only whether the pattern matches at the start of the text; give back — a star surrendering one character of its run so the rest of the pattern can try again; star height — the deepest nesting of stars or pluses in a pattern; catastrophic backtracking — the failing case of a backtracking matcher whose cost grows exponentially with the input; polynomial blow-up — the failing case of adjacent quantifiers, whose cost grows as a power of the input equal to the number of quantifiers.

## One opinion

I think every regex tutorial should open with `(a+)+b` and a stopwatch, not with `\d{3}-\d{4}`. The syntax tutorials teach that a pattern is a description, and a description sounds free. A stopwatch on Listing 1-1 teaches that a pattern is a program with loops in it, whose running time is decided by input the author never sees. Twenty minutes with a stopwatch does more for a working programmer than a chapter on lookbehind.

## Going deeper

- Kernighan, ["A Regular Expression Matcher"](https://www.cs.princeton.edu/courses/archive/spr09/cos333/beautiful.html), chapter 1 of *Beautiful Code* (2007). The original thirty lines of C and the argument that recursion is what makes them short; read it for the shortest-match `matchstar`, the other order.
- Cox, ["Regular Expression Matching Can Be Simple And Fast"](https://swtch.com/~rsc/regexp/regexp1.html) (2007). The graph of Perl against Thompson's algorithm on `a?ⁿaⁿ`, and the clearest account of why the doubling happens; chapters 2 and 3 follow its second half.
- Davis, Coghlan, Servant and Lee, ["The Impact of Regular Expression Denial of Service in Practice"](https://davisjam.github.io/files/publications/DavisCoghlanServantLee-EcosystemREDOS-ESECFSE18.pdf) (2018). Measures how common this is: about 1% of unique regexes in npm and PyPI were super-linear, most of them polynomial. Read it before deciding the problem is rare.

The matcher forgets every path it abandons. Chapter 2 builds a machine that can hold them all.
