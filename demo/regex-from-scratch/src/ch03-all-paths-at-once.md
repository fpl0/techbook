# Chapter 3: All Paths at Once

<span class="newthought">Chapter 1's matcher</span> committed to one interpretation of
the pattern and unwound when it failed. Chapter 2 built a machine whose `Split` states
say "go both ways" without saying which way first. This chapter takes that literally:
instead of choosing, we keep every possibility alive simultaneously.

<div class="orient">
<h3>What you'll learn</h3>
<ul>
<li>Simulate a state machine on a set of states rather than a single state</li>
<li>Explain why the running time is the product of two bounded quantities</li>
<li>Measure the difference against chapter 1 on the same pathological input</li>
</ul>
<h3>Assumes you know</h3>
<p>Chapter 2's compiler and its state kinds. Chapter 1's timing experiment, which this
chapter repeats for comparison.</p>
<p class="meta">~30 min · 4 exercises</p>
</div>

## Warm-up

<details>
<summary>Chapter 2 measured states against pattern length. What was the relationship?</summary>
<p>One state per pattern character, plus one for <code>match</code>. Linear, and it
does not depend on the input at all.</p>
</details>

<details>
<summary>Chapter 1: why did anchoring a pattern with <code>^</code> make it faster without fixing the real problem?</summary>
<p>It removed the outer loop over starting positions, dividing the work by the input
length. The exponential or high-degree polynomial inside a single starting position
was untouched.</p>
</details>

## The idea

Hold a **set** of states the machine could currently be in. For each input character,
compute the set it could be in next. Accept if the `match` state is ever in the set.

Two rules make it work:

1. A `split` state is not a place you can be. Whenever a split enters the set, replace it with both of its targets, recursively. This is the *closure*.
2. Each input character is consumed once, by every `consume` state in the set at the same time.

Because the set is a set, a state that could be reached by two different paths appears
once. That deduplication is the whole reason the cost collapses: chapter 1 explored
those two paths separately and paid for both.

<figure>
<svg viewBox="0 0 800 224" role="img" aria-labelledby="dia-3-1-title">
  <title id="dia-3-1-title">Two columns of states: backtracking explores paths one at a time, simulation carries a set of states forward through each input character</title>
  <g font-family="var(--font-ui)" font-size="13" fill="var(--dia-muted)">
    <text x="24" y="28">Backtracking: one path at a time, restart on failure</text>
    <text x="24" y="140">Simulation: one set of states, one pass</text>
  </g>
  <g stroke="var(--dia-muted)" stroke-width="1.5" fill="none">
    <path d="M 32 56 L 128 88"/><path d="M 32 56 L 128 56"/><path d="M 32 56 L 128 24"/>
    <path d="M 128 88 L 224 104"/><path d="M 128 88 L 224 72"/>
    <path d="M 128 56 L 224 56"/><path d="M 128 24 L 224 40"/><path d="M 128 24 L 224 8"/>
  </g>
  <g fill="var(--dia-warn)"><circle cx="224" cy="104" r="4"/><circle cx="224" cy="72" r="4"/>
     <circle cx="224" cy="56" r="4"/><circle cx="224" cy="40" r="4"/><circle cx="224" cy="8" r="4"/></g>
  <g fill="var(--dia-fill)" stroke="var(--dia-accent)" stroke-width="2.5">
    <rect x="32" y="160" width="88" height="48" rx="4"/>
    <rect x="200" y="160" width="88" height="48" rx="4"/>
    <rect x="368" y="160" width="88" height="48" rx="4"/>
    <rect x="536" y="160" width="88" height="48" rx="4"/>
  </g>
  <g font-family="var(--font-ui)" font-size="12" fill="var(--dia-fg)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="76" y="184">{0,2,3}</text><text x="244" y="184">{1,2,3}</text>
    <text x="412" y="184">{1,2,3}</text><text x="580" y="184">{0,1}</text>
  </g>
  <g stroke="var(--dia-accent)" stroke-width="2.5" fill="none">
    <path d="M 120 184 L 194 184"/><path d="M 288 184 L 362 184"/><path d="M 456 184 L 530 184"/>
  </g>
  <g font-family="var(--font-code)" font-size="12" fill="var(--dia-muted)" text-anchor="middle">
    <text x="157" y="176">a</text><text x="325" y="176">a</text><text x="493" y="176">b</text>
  </g>
</svg>
<figcaption>Figure 3-1. The lower row visits each input character exactly once. The set
never grows beyond the number of states in the machine.</figcaption>
</figure>

## The simulator

```python run env=engine file=code/simulate.py caption="The complete simulator." highlight=2-9
def add_state(prog, i, current, seen):
    """Add state i to the set, expanding splits so the set holds no split states."""
    if i in seen:
        return
    seen.add(i)
    state = prog.states[i]
    if state["kind"] == SPLIT:
        add_state(prog, state["a"], current, seen)
        add_state(prog, state["b"], current, seen)
    else:
        current.add(i)


def simulate(prog, entry, text):
    current = set()
    add_state(prog, entry, current, set())
    for ch in text:
        nxt, seen = set(), set()
        for i in current:
            state = prog.states[i]
            if state["kind"] == CONSUME and (state["c"] is None or state["c"] == ch):
                add_state(prog, state["next"], nxt, seen)
        current = nxt
        if not current:
            return False
    return any(prog.states[i]["kind"] == MATCH for i in current)


def full_match(pattern, text):
    prog, entry = compile_pattern(pattern)
    return simulate(prog, entry, text)


for p, t in [("a*b", "aaab"), ("a*b", "aaac"), ("a|b", "b"), ("(ab)*", "ababab"),
             ("a.c", "axc"), ("a*", "")]:
    print(f"{p:8} {t!r:10} {full_match(p, t)}")
```

```output
a*b      'aaab'     True
a*b      'aaac'     False
a|b      'b'        True
(ab)*    'ababab'   True
a.c      'axc'      True
a*       ''         True
```

<ol class="annot">
<li><code>seen</code> is a separate set from <code>current</code>, and it is the one that terminates the recursion. It has to be separate, because splits are traversed but never stored.</li>
<li>Splits are expanded on entry, so the set that <code>simulate</code> iterates over contains only <code>consume</code> and <code>match</code> states — no state kind needs handling twice.</li>
<li>A fresh <code>seen</code> per input character, because a state reachable at position 4 may need reaching again at position 5.</li>
<li>An empty set means every path has died. Returning early is an optimisation, not a correctness requirement.</li>
</ol>

<div class="callout">
<div class="title">This trips people up</div>
<p>The obvious implementation checks <code>if i in current</code> and drops the
separate <code>seen</code> set. It passes every test in this chapter, and then
overflows the stack on <code>(a*)*</code>. The reason is that splits are never added
to <code>current</code>, so a cycle that runs <em>through</em> splits is never
detected — and a starred group compiles to exactly that cycle. The set that stops the
recursion must record every state visited, not only the states you keep.</p>
<p>This was a real bug in this chapter's first draft. It was caught because the
build runs <code>(a*)*b</code> against two thousand characters on every pass, and a
book that only ever tested <code>a*b</code> would have shipped it.</p>
</div>

<details>
<summary>Predict: for <code>a*b</code>, how large can <code>current</code> get?</summary>

<p>Three at most, because the machine has four states and one of them is a split that
is never stored. In general the set is bounded by the number of states, which chapter 2
showed is bounded by the pattern length. The input cannot make it bigger — that is the
entire guarantee.</p>

</details>

## The payoff

Chapter 1 took 22 milliseconds on `a*a*a*b` against forty characters, and roughly five
times that at sixty. Here is the same work, same pattern, same machine.

```python run env=engine caption="The simulator on the input that defeated chapter 1."
import time

for n in (10, 20, 40, 60, 400, 4000):
    text = "a" * n
    start = time.perf_counter()
    full_match("a*a*a*b", text)
    print(f"n={n:5}  {(time.perf_counter() - start) * 1000:8.2f} ms")
```

```output
n=   10      0.02 ms
n=   20      0.03 ms
n=   40      0.05 ms
n=   60      0.07 ms
n=  400      0.40 ms
n= 4000      3.76 ms
```

The time is proportional to the input length. Ten times the input costs about ten
times the work, all the way up — where chapter 1 could not reach a hundred characters.

The reason is that the work is bounded by two quantities that are both small: for each
of the *n* input characters, the simulator does work proportional to the number of
states *m*, which chapter 2 fixed at one per pattern character. So the cost is
O(*nm*), and neither factor can surprise you.<label for="sn-3-1" class="margin-toggle sidenote-number"></label>
<input type="checkbox" id="sn-3-1" class="margin-toggle">
<span class="sidenote">Ken Thompson published this construction in 1968, in a paper
about compiling regular expressions to IBM 7094 machine code. The algorithm predates
the backtracking engines that replaced it by about a decade.</span>

Nested quantifiers change nothing, because the machine has no nesting left in it — the
compiler flattened the tree into a list of states.

```python run env=engine caption="The nested-quantifier case from chapter 1, which no backtracker survives."
import time

start = time.perf_counter()
result = full_match("(a*)*b", "a" * 2000)
print(f"matched={result}  in {(time.perf_counter() - start) * 1000:.2f} ms")
```

```output
matched=False  in 1.06 ms
```

## What we gave up

This is not a free win, and a book that pretended otherwise would be lying to you.

| Cost | Detail |
|---|---|
| Capture groups | The simulator knows *whether* it matched, not *where* each group did. Recovering that needs submatch tracking, which is genuinely harder. |
| Backreferences | `(a+)\1` is not a regular language. No finite-state machine can express it, at any speed. |
| Lookaround | Not expressible in this model without extending the machine. |
| Greedy versus lazy | The set-based simulator has no notion of preference between paths, because it does not take paths one at a time. |

Those are the reasons production engines still use backtracking. Go's `regexp`, RE2,
and Rust's `regex` crate made the opposite choice: they drop backreferences and
lookaround in exchange for the guarantee, which for a server parsing untrusted input is
usually the better trade.

## Practice

<div class="exercises">

<div class="exercise">
<span class="label">Exercise</span>
<p>Fill the blank so <code>simulate</code> reports the length of the longest prefix
matched, instead of a boolean.</p>

```python literal why="exercise stub; intentionally incomplete"
longest = -1
for pos, ch in enumerate(text):
    if any(prog.states[i]["kind"] == MATCH for i in current):
        longest = ____
    # ... advance current as before
```

<details><summary>Solution</summary>
<p><code>pos</code>. Record before consuming, because <code>current</code> describes
the machine's state <em>before</em> character <code>pos</code> is read. Off-by-one
errors here are the reason to write the test first.</p>
</details>
</div>

<div class="exercise">
<span class="label">Exercise</span>
<p>Complete the stub so an unanchored search works, by allowing a new start at every
position.</p>

```python literal why="exercise stub; intentionally incomplete"
for ch in text:
    nxt = set()
    add_state(prog, ____, nxt)     # a fresh start, every character
    for i in current:
        ...
```

<details><summary>Solution</summary>
<p><code>entry</code>. This is the standard trick, and it is why unanchored search
costs no more asymptotically than anchored: the extra start states merge into the same
set rather than multiplying the work.</p>
</details>
</div>

<div class="exercise">
<span class="label">Exercise</span>
<p>From scratch: add a <code>?</code> node to the parser, the compiler, and confirm the
simulator needs no change at all. Explain in one sentence why it does not.</p>
</div>

<div class="exercise">
<span class="label">Exercise</span>
<p>Transfer: caching <code>frozenset(current)</code> to the set that follows it, per
input character, converts this simulator into a DFA. Sketch what could go wrong with
that cache on an adversarial pattern, and what you would bound.</p>
</div>

</div>

## What to remember

- A set of states replaces a choice between states, and the set deduplicates the paths backtracking pays for twice
- Splits are expanded on entry, so the stored set contains only states that consume input
- Membership must be checked before recursing, or a star loops forever
- The cost is O(*nm*): input length times machine size, with neither factor able to surprise you
- The guarantee is bought with capture groups, backreferences, and lookaround
- Backreferences are not slow here — they are not expressible, because the language they describe is not regular

**Terms introduced:** closure, simulation, deduplication, DFA, submatch tracking.

## Where to go next

The natural next step is submatch tracking: carrying, alongside each state, the input
positions where each group began. Russ Cox's series on regular expression matching
covers it, along with the history of how backtracking came to dominate despite
Thompson's construction predating it. Go's `regexp` package and the RE2 source are both
readable implementations of everything in this book, at production scale.

What you have built is about two hundred lines and matches the asymptotic behaviour of
those engines on the subset of syntax it supports. The gap between this and RE2 is
features and constant factors, not the idea.
