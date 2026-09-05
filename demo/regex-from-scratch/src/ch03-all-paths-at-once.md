# Chapter 3: All Paths at Once

Eight states. That is the whole machine chapter 2 compiled for `a*a*a*b`, and chapter 1 needed 822.2 ms to run the same pattern against 320 a's, because its matcher walked the give-back loops one path at a time and kept nothing from the paths it abandoned. A machine of eight states has nowhere to put a million paths. It can be in at most eight places, and a matcher that tracks *places* instead of paths has no reason to care how long the text is.

Ken Thompson's 1968 paper states the method in two sentences: ["each character in the text to be searched is examined in sequence against a list of all possible current characters. During this examination a new list of all possible next characters is built."](https://www.oilshell.org/archive/Thompson-1968.pdf) The sentence before them describes the matcher you already have. Earlier methods "involve backtracking when a partially successful search path fails", which "necessitates a lot of storage and bookkeeping, and executes slowly". Two lists, one character at a time, no return trips. This chapter writes those lists in four functions, times them against the recursive matcher and against `re`, and then deletes one check to meet the bug the design invites.

<div class="orient">
  <h3>What you'll learn</h3>
  <ul>
    <li>Run chapter 2's machine over a text as a set of live states, one step per character, with no path ever revisited</li>
    <li>Explain why the work per character is bounded by the pattern and cannot grow with the text</li>
    <li>Measure <code>tinyre</code> against chapter 1's matcher and Python's <code>re</code>, and say what the table does and does not show</li>
    <li>Find the split cycle that hangs a careless simulator, and name the one check that stops it</li>
  </ul>
  <h3>Assumes you know</h3>
  <p>Chapter 2's machine: <code>State</code> with <code>ch</code>, <code>out</code>, <code>alt</code> and <code>matched</code>, split states, the match state, and <code>compile_pattern</code>. The timings of chapter 1. Python sets and <code>id()</code>.</p>
  <p class="meta">~45 min · 4 exercises</p>
</div>

<details>
  <summary>Warm-up: chapter 1 timed <code>a*a*a*b</code> against 320 a's at 822.2 ms. Where did the time go, and what did the matcher keep from each rejected attempt?</summary>
  <p>Three stars, three nested give-back loops, about n³ calls to <code>match_here</code>, with each rejected suffix checked again on the next trip round the loop above it. The matcher kept nothing. The only record of a failed attempt is the loop counter of the star that made it.</p>
</details>

<details>
  <summary>Warm-up: a pattern of m non-parenthesis characters compiles to how many states, and what does the machine do when it reaches a split state?</summary>
  <p>m+1, the extra one being the match state, and the text has no say in it because the compiler reads only the tree. At a split the machine takes both arrows without consuming a character, so being in a split state means being in both of its successors.</p>
</details>

<div class="crux">
  <div class="title">The crux</div>
  <p>A pattern of m characters compiles to m+1 states, and a machine cannot be in more states than it has. If the matcher never holds more than m+1 of them at a time, how can the work per character of text be anything but bounded? And what does holding them cost when two paths arrive at the same state?</p>
</div>

## Following the split arrows

Listing 2-6 printed the machine for `(a|b)*c`: `s0` is the star's split, with arrows to `s1` and `s2`; `s1` is the alternation's split, with arrows to `s3` for `a` and `s4` for `b`; `s2` is `c`, leading to the match state `s5`. Before the first character is read, where is the machine? Its entry is `s0`. But `s0` consumes nothing, so being at `s0` is being at `s1` and `s2`, and `s1` consumes nothing either, so being at `s1` is being at `s3` and `s4`. The machine starts in three states, `s3`, `s4` and `s2`, and neither split is among them. Russ Cox puts it in one sentence: the machine ["starts in the start state and all the states reachable from the start state by unlabeled arrows"](https://swtch.com/~rsc/regexp/regexp1.html). The textbooks call that set the **epsilon closure**, epsilon being the empty string a split arrow consumes.

The closure is not a separate pass. In Cox's C, `addstate` "also follows unlabeled arrows: if s is a Split state with two unlabeled arrows to new states, addstate adds those states to the list instead of s". A split costs nothing to pass through, so pass through it at the moment you would otherwise have stored it. The list then only ever holds states that can consume a character, plus the match state, and the function that adds a state after a character is the same one that computes the closure at the start. In Listing 3-1, watch what `add_state` refuses to store, and what `step` builds fresh every time.

```python run file=code/simulate.py caption="The simulator. Four functions, and the machine is never modified."
"""Run the machine over the text, holding every live state at once."""


def add_state(states, s, seen):
    """Add `s`, following split states eagerly; `seen` breaks cycles."""
    if s is None or id(s) in seen:
        return
    seen.add(id(s))
    if s.ch is None and not s.matched:      # a split: take both arms
        add_state(states, s.out, seen)
        add_state(states, s.alt, seen)
    else:
        states.append(s)


def step(current, ch):
    """Every state one character further on. A set, so no path is counted twice."""
    following, seen = [], set()
    for s in current:
        if s.ch is not None and (s.ch == "." or s.ch == ch):
            add_state(following, s.out, seen)
    return following


def fullmatch(start, text):
    current = []
    add_state(current, start, set())
    for ch in text:
        current = step(current, ch)
        if not current:
            return False
    return any(s.matched for s in current)


def search(start, text):
    """Unanchored: re-enter the start state before every character."""
    current, seen = [], set()
    add_state(current, start, seen)
    for ch in text:
        if any(s.matched for s in current):
            return True
        current = step(current, ch)
        add_state(current, start, {id(s) for s in current})
    return any(s.matched for s in current)
```

<ol class="annot">
<li>Lines 4 to 13. A split is followed both ways and never stored, so <code>states</code> holds character states and the match state only. <code>seen</code> holds <code>id(s)</code> rather than <code>s</code>.
The <code>eq=False</code> on <code>State</code> in chapter 2 means a set of states would compare by identity anyway; the ids make that explicit and cost one integer per entry. Cox does the same job without a set: every state carries a <code>lastlist</code> field, each new list gets a fresh generation number, and "if the two are already equal, then s is already on the list being built". Both versions make the check <em>before</em> the recursion. The end of this chapter is about why.</li>
<li>Lines 16 to 21. <code>step</code> builds a new list and a new <code>seen</code> per character and leaves the old list alone, so the machine after a character depends on the machine before it and that one character, nothing else. A state whose character does not match contributes nothing to <code>following</code>. That is how a path dies here: it is not carried forward, and nothing unwinds.</li>
<li>Lines 24 to 31. An empty list means every path is dead and no later character can revive one, which is the only early exit. Success at the end means the text is exhausted <em>and</em> the match state is live.
That is the whole-text question, where chapter 1's <code>match_here</code> asked about a prefix, and the function takes Python's name for it.</li>
<li>Lines 34 to 42. The unanchored search re-enters the start state before every character, which folds the loop over start positions into the same pass. The <code>seen</code> handed to <code>add_state</code> on line 41 is seeded with the ids already live, so re-entry cannot duplicate a state that is there. The check on line 38 comes before the character is consumed, because a match that ended at position i is visible in the set before character i is read. The set does not know where that match started. Hold that thought.</li>
</ol>

Listing 3-2 prints the live set of `(a|b)*c` before any input and after each character of `abc`, labelling each state by the character it consumes.

```python run caption="The live set over `abc`. The split states never appear."
from parse import parse
from machine import compile_pattern
import simulate


def labels(states):
    return ["Match" if s.matched else s.ch for s in states]


current = []
simulate.add_state(current, compile_pattern(parse("(a|b)*c")), set())
print("start  ", labels(current))
for ch in "abc":
    current = simulate.step(current, ch)
    print(f"after {ch}", labels(current))
```

```output
start   ['a', 'b', 'c']
after a ['a', 'b', 'c']
after b ['a', 'b', 'c']
after c ['Match']
```

The set before `a` and the set after it are the same three states, and so is the set after `b`. Every arrow out of `s3` and `s4` leads back to `s0`, and the closure from `s0` is always the same three states, so however many a's and b's the text holds, the machine does the same amount of work for each. This is a **simulation** of the machine: not one path at a time but every path, held as the set of states the paths currently occupy, which the rest of the book calls the **live set**. Figure 3-1 draws the same run as a timeline.

<figure>
<svg viewBox="0 0 800 328" role="img" aria-labelledby="dia-3-1-title">
  <title id="dia-3-1-title">The live set of (a|b)*c is the same three states before a, before b and before c, because each consumed character leads back to s0 and the closure from s0 never changes; after c only the match state is live</title>
  <defs>
    <marker id="arrow-ch3" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--dia-muted)"/>
    </marker>
  </defs>

  <g fill="var(--dia-fill)" stroke="var(--dia-fg)" stroke-width="1.5">
    <rect x="224" y="24"  width="320" height="48" rx="4"/>
    <rect x="224" y="104" width="320" height="48" rx="4"/>
    <rect x="224" y="184" width="320" height="48" rx="4"/>
  </g>
  <g fill="var(--dia-fill)" stroke="var(--dia-accent)" stroke-width="2.5">
    <rect x="224" y="264" width="320" height="48" rx="4"/>
  </g>

  <g font-family="var(--font-ui)" font-size="16" fill="var(--dia-fg)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="384" y="48">live: s3 a, s4 b, s2 c</text>
    <text x="384" y="128">live: s3 a, s4 b, s2 c</text>
    <text x="384" y="208">live: s3 a, s4 b, s2 c</text>
    <text x="384" y="288" fill="var(--dia-accent)">live: s5 Match</text>
  </g>
  <g font-family="var(--font-ui)" font-size="16" fill="var(--dia-fg)"
     text-anchor="start" dominant-baseline="middle">
    <text x="24" y="48">before reading a</text>
    <text x="24" y="128">before reading b</text>
    <text x="24" y="208">before reading c</text>
    <text x="24" y="288">text exhausted</text>
  </g>
  <g font-family="var(--font-ui)" font-size="15" fill="var(--dia-accent)"
     text-anchor="start" dominant-baseline="middle">
    <text x="400" y="88">read a</text>
    <text x="400" y="168">read b</text>
    <text x="400" y="248">read c</text>
  </g>
  <g font-family="var(--font-ui)" font-size="15" fill="var(--dia-muted)"
     text-anchor="start" dominant-baseline="middle">
    <text x="576" y="40">closure from s0: s0 and s1</text>
    <text x="576" y="58">consume nothing, so skipped</text>
    <text x="576" y="120">s3 took the a, back to s0,</text>
    <text x="576" y="138">same closure again</text>
    <text x="576" y="200">s4 took the b, back to s0,</text>
    <text x="576" y="218">same closure again</text>
    <text x="576" y="280">s2 took the c; s3 and s4</text>
    <text x="576" y="298">had no arrow for c and died</text>
  </g>

  <g stroke="var(--dia-muted)" stroke-width="1.5" fill="none" marker-end="url(#arrow-ch3)">
    <path d="M 384 72 L 384 104"/>
    <path d="M 384 152 L 384 184"/>
    <path d="M 384 232 L 384 264"/>
  </g>
</svg>
<figcaption>Figure 3-1. Each row is the set of states that could consume the next character. A state that cannot consume it is dropped, a state that can is replaced by the closure of its successor, and the set never has to remember which row it came from.</figcaption>
</figure>

<details>
  <summary>Predict: run <code>a*a*a*b</code> against a string of a's. How many states are live after each <code>a</code>, and does the number depend on how many a's there are?</summary>
  <p>Four, always: the three <code>a</code> states and the <code>b</code>. Of the machine's eight states, three are splits that are never stored and one is the match state, which only goes live after a <code>b</code>. After each <code>a</code> every <code>a</code> state leads back through its own split and the splits after it, and the closure is the same four states it was before. The recursive matcher had about n³ pending attempts on this input; the live set has four entries whatever n is.</p>
</details>

## Why it is linear

The bound is two sentences of arithmetic. Before each character the live set holds at most m+1 states, because the machine has no more than that and `seen` refuses a second copy of any of them. Following one state's arrow costs one call to `add_state`, which touches each state at most once per character for the same reason. So the work per character is at most a small multiple of m+1, a number fixed when the pattern was compiled, and the total for a text of n characters is at most a multiple of n·(m+1). Cox: ["in the worst case, the NFA might be in every state at each step, but this results in at worst a constant amount of work independent of the length of the string"](https://swtch.com/~rsc/regexp/regexp1.html), so the input can be as long as you like and the time stays linear in it. With both variables named, "for a regular expression of length m run on text of length n, the Thompson NFA requires O(mn) time".<label for="sn-3-1" class="margin-toggle sidenote-number"></label><input type="checkbox" id="sn-3-1" class="margin-toggle"><span class="sidenote">Cox swaps the letters between articles. In the 2009 piece n is the program size and m the input length, so read the bound in whichever article you are holding before quoting it.</span>
The give-back loops of chapter 1 had no such number; their pending alternatives grew with the text.

The four functions of Listing 3-1 take a start state, and a reader of the library should not have to compile one. Listing 3-3 is the whole public face of `tinyre`, with the names Python's `re` uses.

```python run file=code/tinyre.py caption="The public API. Compile once in `Pattern`, or once per call through the module functions."
"""The public face of the engine: compile once, match many times."""
from parse import parse
from machine import compile_pattern
import simulate


class Pattern:
    def __init__(self, source):
        self.source = source
        self.start = compile_pattern(parse(source))

    def fullmatch(self, text):
        return simulate.fullmatch(self.start, text)

    def search(self, text):
        return simulate.search(self.start, text)


def compile(source):
    return Pattern(source)


def fullmatch(source, text):
    return Pattern(source).fullmatch(text)


def search(source, text):
    return Pattern(source).search(text)
```

The module functions recompile on every call, which is the convenience `re.fullmatch` offers too; the `Pattern` object is for the loop that runs one pattern over many texts, and the benchmark below uses it so that the parse is not in the timing. Nothing here has the name `match`. The prefix question chapter 1's `match_here` answered is put to the two functions that do exist on the third and fourth lines of Listing 3-4.

```python run caption="`fullmatch` and `search` on the inputs chapter 1 used, plus the pattern chapter 1 could not finish."
import tinyre

print(tinyre.fullmatch("(a|b)*c", "abbac"))
print(tinyre.search("(a|b)*c", "xxc"))
print(tinyre.fullmatch("a*b", "ba"))
print(tinyre.search("a*b", "ba"))
pattern = tinyre.compile("a*a*a*b")
print(pattern.fullmatch("a" * 320))
```

```output
True
True
False
True
False
```

Zero a's and one `b` fit the front of `ba`, which is why chapter 1's `match_here` said `True` to it. `fullmatch` says `False` because the text is not exhausted when the match state goes live, and `search` says `True` because it may stop early. The last line is the 822.2 ms case, and Listing 3-5 times it. It runs `code/bench.py`, which takes the best of three runs of each matcher with `time.perf_counter`, on the grounds the `timeit` documentation gives: the minimum "gives a lower bound for how fast your machine can run the given code snippet", and higher values ["are typically not caused by variability in Python's speed, but by other processes interfering with your timing accuracy"](https://docs.python.org/3/library/timeit.html). Read the columns as curves, not as a ranking.

```python run nondet=output timeout=120 file=code/bench.py caption="Three matchers on `a*a*a*b`, best of three. Same machine and interpreter as chapter 1."
"""Time the three matchers on the same family of inputs. Best of three runs."""
import re
import time
import backtrack
import tinyre


def timed(fn, repeats=3):
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best * 1000


if __name__ == "__main__":
    pattern = "a*a*a*b"
    compiled = tinyre.compile(pattern)
    print(f"{'n':>6} {'backtrack':>10} {'tinyre':>10} {'re':>10}")
    for n in (40, 80, 160, 320):
        text = "a" * n
        row = (timed(lambda: backtrack.match_here(pattern, text)),
               timed(lambda: compiled.fullmatch(text)),
               timed(lambda: re.fullmatch(pattern, text)))
        print(f"{n:>6} {row[0]:>8.1f}ms {row[1]:>8.2f}ms {row[2]:>8.3f}ms")
```

```output
     n  backtrack     tinyre         re
    40      1.9ms     0.04ms    0.015ms
    80     13.7ms     0.07ms    0.095ms
   160    106.6ms     0.15ms    0.674ms
   320    825.3ms     0.29ms    4.937ms
```

Doubling the input multiplies the first column by about eight and the second by about two. The third column is the one to look at twice. Python's `re` multiplies by six to seven per doubling on this pattern, the same cubic shape as the recursive matcher with a much smaller constant, because `re` backtracks and three adjacent stars cost it three nested loops as well. At n=320 `tinyre` is seventeen times faster than `re`, and it would be a mistake to read that as `tinyre` being fast. It wins here because this one pattern makes `re` do cubic work, and a Python simulator doing linear work overtakes a C backtracker doing cubic work somewhere between n=40 and n=80. Listing 3-6 chooses a pattern on which both are linear.

```python run nondet=output caption="`a*b` against 800,000 a's, the pattern on which `re` has nothing to backtrack over."
import re
import time
import tinyre

n = 800_000
text = "a" * n


def timed(fn, repeats=3):
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best * 1000


compiled = tinyre.compile("a*b")
print(f"a*b against {n:,} a's, best of three")
print(f"re      {timed(lambda: re.fullmatch('a*b', text)):8.1f} ms")
print(f"tinyre  {timed(lambda: compiled.fullmatch(text)):8.1f} ms")
```

```output
a*b against 800,000 a's, best of three
re           0.7 ms
tinyre     315.8 ms
```

On `a*b`, `re` is about 450 times faster than `tinyre`. Both are linear; `re` runs a C loop over a run of a's, and `tinyre` builds a Python list and a Python set per character.
The claim this chapter can support is the shape of the curve, not its height, and the shape was the whole problem in both outages of chapter 1. Cox's 2007 article reports Perl taking over sixty seconds on a 29-character string where his C simulator took twenty microseconds. The article does not say what machine ran it, and the numbers are two decades old. That is why this book measures instead of quoting.

## The cycle

The parser of chapter 2 rejects `a**` and accepts `(a*)*b`. The parentheses make the inner star an atom, and the outer star quantifies that atom. Compiled, the outer split's `out` arrow leads to the inner split, and the inner split's `alt` arrow leads back to the outer split. No character state sits between them. Two splits point at each other. An `add_state` with no memory walks outer, inner, stores `a`, takes the inner split's second arm back to outer, and goes round again until Python stops it. Listing 3-7 is Listing 3-1's `add_state` with the `seen` check removed and the two arms folded into one loop, so that the traceback collapses to a single repeated line. Read it from the bottom.

```python expect-error expect="RecursionError" caption="`add_state` without `seen`, on the one shape of machine that has a cycle with no character in it."
from parse import parse
from machine import compile_pattern


def add_state(states, s):
    """Listing 3-1's add_state with the `seen` check removed."""
    if s is None:
        return
    if s.ch is None and not s.matched:
        for arm in (s.out, s.alt):              # a split: take both arms
            add_state(states, arm)
    else:
        states.append(s)


add_state([], compile_pattern(parse("(a*)*b")))
```

```output
Traceback (most recent call last):
  File "snippet.py", line 16, in <module>
    add_state([], compile_pattern(parse("(a*)*b")))
    ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "snippet.py", line 11, in add_state
    add_state(states, arm)
    ~~~~~~~~~^^^^^^^^^^^^^
  File "snippet.py", line 11, in add_state
    add_state(states, arm)
    ~~~~~~~~~^^^^^^^^^^^^^
  File "snippet.py", line 11, in add_state
    add_state(states, arm)
    ~~~~~~~~~^^^^^^^^^^^^^
  [Previous line repeated 996 more times]
RecursionError: maximum recursion depth exceeded
```

A thousand frames, one line, and no character consumed in any of them. Thompson met this in 1968. "Code compiled for a** will go into a loop due to the closure operator on an operand containing the null regular expression", his closing notes say, and he offers two ways out: refuse the expression at "the syntax sieve", since "in most practical applications, this would not be a serious restriction", or recognise the empty string as its own operand, so that ["a** is compiled as λ|aa*(aa*)*"](https://www.oilshell.org/archive/Thompson-1968.pdf). The parser took the first way out for `a**` and left `(a*)*` alone, on purpose, because the same notes contain a third way that rewrites nothing. A state entered twice leads to a redundant search, Thompson observes: "Such redundant searches can be easily terminated by having NNODE (CNODE) search NLIST (CLIST) for a matching entry before it puts an entry in the list. This now gives a maximum size on the number of entries that can be in the lists." That is `seen`. Cox's generation number is the same check in constant time, and because both check *before* recursing, a cycle of splits ends on its second visit to the first split.<label for="sn-3-2" class="margin-toggle sidenote-number"></label><input type="checkbox" id="sn-3-2" class="margin-toggle"><span class="sidenote">RE2 rewrites a star over a subexpression that can match the empty string as <code>(a+)?</code> at compile time, and its <a href="https://raw.githubusercontent.com/google/re2/main/re2/compile.cc">source comment</a> gives a reason that is not termination: "one Alt isn't enough to guarantee correct priority ordering within the transitive closure". Which of two matches an engine prefers is a question this book's yes-or-no matcher never has to answer.</span>

<div class="callout">
  <div class="title">This trips people up</div>
  <p>"The <code>seen</code> set is an optimisation that stops a state being counted twice, and the cycle is a separate bug that needs a separate guard." Both halves are wrong in the same way. A state reached twice in one step by two different paths is one state, and dropping the second arrival is what keeps the live set at m+1 entries. A state reached twice by the same path going round a cycle is also one state, and dropping the second arrival is what ends the walk. One check, two consequences, and Thompson wrote both into the same closing notes. Remove it and you lose the bound and the termination together.</p>
</div>

<details>
  <summary>Predict: with <code>seen</code> in place, what does <code>tinyre.fullmatch("(a*)*b", "aaab")</code> return, and how many states are live after each <code>a</code>?</summary>
  <p><code>True</code>, with two states live after every <code>a</code>: the <code>a</code> state and the <code>b</code> state. The closure from the outer split visits both splits once each, stores <code>a</code>, follows the outer split's second arm to <code>b</code>, and refuses to enter either split again. The pattern that hangs a careless simulator costs this one exactly as much per character as <code>a*b</code> does.</p>
</details>

## What the set forgets

Listing 3-2 printed the same three states after `a` and after `b`, and the two sets are not merely equal in content. The machine cannot tell them apart. Nothing in the second records that `s4` consumed the `b`, or that `s3` consumed the `a` before it, or that the text so far was `ab` rather than `ba`. The live set records *which* states are live and not *how* each became live, and for a yes-or-no matcher that is the right thing to forget, because it is what holds the set to m+1 entries.

A capture group needs the *how*. To report what `(a|b)*` last matched, an engine has to know where in the text each path was when it entered the group and when it left, and two paths in the same state can have entered at different places. Rob Pike's answer, in the text editor `sam` in 1987, was to make each entry in the list a thread carrying its own saved positions. Cox's account of that design explains why one entry per state still suffices: ["the saved pointers do not influence future execution: they only record past execution. Two threads with the same PC will execute identically even if they have different saved pointers; thus only one thread per PC needs to be kept"](https://swtch.com/~rsc/regexp/regexp2.html). That design is the **Pike VM**, and the bound survives it. What does not survive unchanged is the constant. The engine has to copy submatch sets from thread to thread, and Cox says of RE2's version that ["it can be slower in common cases than a backtracker like PCRE"](https://swtch.com/~rsc/regexp/regexp3.html).

A backreference needs the *how* to decide the future, and that is the line this design cannot cross. The pattern `(a|b)*\1` has to match whatever the group matched, so two threads in the same state with different captures will behave differently from here on, and the argument for keeping one of them fails: "an implementation has to keep both threads, a potentially exponential blowup in state". No one knows how to do better. Matching with backreferences is NP-complete, in Cox's phrasing, so "if someone did find an efficient implementation, that would be major news to computer scientists". Chapter 4 lists everything `tinyre` gave up in exchange for its bound, and what the engines that made the same trade do about it.

## Practice

<div class="exercises">
  <div class="exercise">
    <span class="label">Exercise 1</span>
    <p>Make <code>fullmatch</code> report how many steps it took as well as whether it matched. Fill in the blank.</p>

```python literal why="exercise stub"
def fullmatch_counting(start, text):
    current, steps = [], 0
    add_state(current, start, set())
    for ch in text:
        current = step(current, ch)
        ________
        if not current:
            return False, steps
    return any(s.matched for s in current), steps
```

    <details><summary>Solution</summary><p><code>steps += 1</code>. The count is at most <code>len(text)</code>, and equals it whenever the set never empties. Compare exercise 3 of chapter 1, where the count of calls for <code>a*a*b</code> was (n+2)(n+3)/2: that number counted paths, and this one counts characters. The number of paths never appears anywhere in the simulator, which is why it never pays for them.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 2</span>
    <p>Listing 3-1's <code>search</code> says whether a match exists. Finish this version so that it returns the index just past the end of the earliest-ending match, or <code>None</code>.</p>

```python literal why="exercise stub"
def search_end(start, text):
    current, seen = [], set()
    add_state(current, start, seen)
    for i, ch in enumerate(text):
        ...
    ...
```

    <details><summary>Solution</summary><p>Inside the loop, return <code>i</code> if any live state is the match state, then step and re-enter the start state as <code>search</code> does. After the loop, return <code>len(text)</code> if the match state is live and <code>None</code> otherwise. Notice what you cannot return: the start of that match. The set does not record where a path began, so this is the earliest end, which is neither the leftmost match nor the longest.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 3</span>
    <p>Write <code>findall(start, text)</code> returning the spans of non-overlapping matches, leftmost first and, among matches starting at the same place, longest. Say why you chose longest.</p>
    <details><summary>Solution</summary><p>Try each start position from the left. From a start, run the anchored simulation without re-entering the start state, record the last position at which the match state was live, and stop when the set empties. If a match was recorded, emit the span and continue from its end, or from end+1 when the match was empty; otherwise move the start one character on. Longest is the choice the set can make: it does not know which alternative arrived first, so it cannot prefer <code>a</code> over <code>ab</code> in <code>a|ab</code>, but it can see the last position at which anything matched. Cox notes that POSIX defines its matches that way and Perl does not. The cost is up to n starts of up to n steps each, which is the O(m·n²) worst case the Rust <code>regex</code> documentation gives for its iterators.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 4</span>
    <p>"A set of live states, advanced one input at a time, with a visited set to stop double counting" is not a regex idea. Name two other places where the same structure appears, and say what plays the part of the character.</p>
    <details><summary>Solution</summary><p>Breadth-first search over a graph: the frontier is the live set, the visited set is <code>seen</code>, and the layer number is the character position. A lexer generator such as <code>lex</code> builds its tables from exactly these sets of states, one per input character, giving each distinct set a number; the set is what a table entry names. An event-driven state machine that can be in more than one state at once, a protocol handler or a game controller, is the same thing with a wider alphabet. Each time, the cost per input is bounded by the number of distinct states, not by the number of ways to reach them.</p></details>
  </div>
</div>

## Mental model

- The machine is run as a set of live states. Each character maps the set before it to the set after it, and the old set is discarded.
- The simulator passes through a split at the moment it would otherwise store it, so the live set holds only character states and the match state.
- The `seen` check refuses a state that is already in the list. That bounds the list at m+1 entries and terminates a cycle of splits; it is one check with two consequences.
- Work per character is bounded by the pattern, so a text of n characters costs at most a multiple of n·(m+1). The number of paths never appears in the cost.
- Unanchored search re-enters the start state before every character, inside the same bound.
- The set records which states are live, not how they became live. Captures need threads that carry positions; backreferences need more than any known bound allows.

**Terms introduced:** live set — the set of states the machine occupies before reading the next character, holding only states that can consume a character plus the match state; epsilon closure — every state reachable from a given state along split arrows, without consuming a character; simulation — running the machine over the text by advancing every live state together, rather than one path at a time; step — the function from the live set before a character to the live set after it; unanchored search — matching that may begin at any position, done here by re-entering the start state before every character; Pike VM — Rob Pike's form of the simulation in which each live state is a thread carrying its saved positions, so that captures can be reported.

## One opinion

I think the set simulation should be taught before the DFA, and usually it is taught after, if at all. The section of Cox's article headed ["Caching the NFA to build a DFA"](https://swtch.com/~rsc/regexp/regexp1.html) says what a DFA state is: a set of NFA states, computed once and kept. A reader who has run Listing 3-2 by hand already knows the function being memoised, and the DFA arrives as a cache in front of it. Taught the other way round, the DFA is a table that fell from the sky, the subset construction is a proof about it, and the reader never sees the thing the table was saving them from computing.

## Going deeper

- Cox, ["Regular Expression Matching Can Be Simple And Fast"](https://swtch.com/~rsc/regexp/regexp1.html) (2007), second half. The C simulator this chapter's Python follows, the `listid` trick, and the section on caching the sets into a DFA, including the note that the cache can be thrown away when it grows too large.
- Cox, ["Regular Expression Matching: the Virtual Machine Approach"](https://swtch.com/~rsc/regexp/regexp2.html) (2009). The Pike VM: threads, saved positions, and why one thread per state is still enough. Read it before adding captures to `tinyre`.
- Gallant, ["Regex engine internals as a library"](https://burntsushi.net/regex-internals/) (2023). How Rust's `regex` crate stacks a Pike VM, a bounded backtracker, a one-pass DFA and a lazy DFA behind one interface, and why "only the PikeVM is required".

On every example in this chapter, `tinyre` agrees with `re`. Chapter 4 asks whether it agrees on every pattern of up to four characters, and the first version did not.
