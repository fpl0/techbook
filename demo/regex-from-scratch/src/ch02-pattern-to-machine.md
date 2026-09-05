# Chapter 2: From Pattern to Machine

<span class="newthought">The matcher in chapter 1</span> re-read the pattern string on
every recursive call, deciding afresh each time whether it was looking at a literal, a
dot, or a star. That is wasteful, but the real cost is structural: a string has no
room to record *where else the matcher could be*. This chapter converts the pattern
into something that does.

<div class="orient">
<h3>What you'll learn</h3>
<ul>
<li>Parse the four-construct language into a tree</li>
<li>Compile that tree into a state machine using Thompson's construction</li>
<li>Explain why the machine has at most one state per pattern character</li>
</ul>
<h3>Assumes you know</h3>
<p>Chapter 1's matcher and why it slows down. Python dataclasses and dictionaries.
Still no automata theory.</p>
<p class="meta">~30 min · 3 exercises</p>
</div>

## Warm-up

<details>
<summary>In chapter 1, what determined the <em>degree</em> of the polynomial — the length of the input, or something about the pattern?</summary>
<p>Something about the pattern: the number of stars competing for the same characters.
The input length is the base, the pattern supplies the exponent.</p>
</details>

<details>
<summary>Why did <code>match_star</code> pass <code>pattern[2:]</code> rather than the whole pattern?</summary>
<p>Because <code>pattern[0]</code> and the <code>*</code> have both been accounted for
by <code>match_star</code> itself. Passing the whole pattern recurses on the same
input forever.</p>
</details>

## Parsing, in one pass

Our language has four constructs and one precedence rule: `*` binds tighter than
concatenation. That is small enough for a recursive descent parser of about thirty
lines. We add alternation with `|`, which binds loosest, because it costs one function.

```python run env=engine file=code/parse.py caption="A recursive descent parser producing a small tree."
from dataclasses import dataclass


@dataclass
class Char:  c: str
@dataclass
class Dot:   pass
@dataclass
class Star:  inner: object
@dataclass
class Cat:   left: object; right: object
@dataclass
class Alt:   left: object; right: object


class Parser:
    def __init__(self, src):
        self.src, self.i = src, 0

    def peek(self):
        return self.src[self.i] if self.i < len(self.src) else None

    def parse(self):
        node = self.alternation()
        if self.i != len(self.src):
            raise SyntaxError(f"unexpected {self.peek()!r} at {self.i}")
        return node

    def alternation(self):
        node = self.concatenation()
        while self.peek() == "|":
            self.i += 1
            node = Alt(node, self.concatenation())
        return node

    def concatenation(self):
        node = None
        while self.peek() not in (None, "|", ")"):
            atom = self.repeat()
            node = atom if node is None else Cat(node, atom)
        return node

    def repeat(self):
        node = self.atom()
        while self.peek() == "*":
            self.i += 1
            node = Star(node)
        return node

    def atom(self):
        c = self.peek()
        if c == "(":
            self.i += 1
            node = self.alternation()
            if self.peek() != ")":
                raise SyntaxError("unclosed (")
            self.i += 1
            return node
        self.i += 1
        return Dot() if c == "." else Char(c)


print(Parser("a*b").parse())
print(Parser("a|b").parse())
```

```output
Cat(left=Star(inner=Char(c='a')), right=Char(c='b'))
Alt(left=Char(c='a'), right=Char(c='b'))
```

<ol class="annot">
<li>Each precedence level is one method, calling the level below it. Alternation calls concatenation, which calls repeat, which calls atom. The call stack <em>is</em> the precedence table.</li>
<li><code>concatenation</code> stops at <code>|</code> and <code>)</code> because those belong to a level above it, not to itself.</li>
<li><code>repeat</code> loops rather than recursing, so <code>a**</code> parses without nesting the stack.</li>
</ol>

An empty alternative parses to `None`, which is the correct representation of "matches
the empty string" and will compile to a machine that consumes nothing.

<div class="callout">
<div class="title">This trips people up</div>
<p>Parsing <code>*</code> inside <code>atom</code> rather than in its own level makes
<code>ab*</code> mean <code>(ab)*</code>. Precedence bugs of this kind produce a parser
that works on every example you happen to try and is wrong on the fifth one a reader
tries. Test <code>ab*</code> against <code>"abbb"</code> and <code>"abab"</code>.</p>
</div>

## The machine

A state machine, for our purposes, is a set of numbered states. Each state is one of
three things:

| State kind | Meaning |
|---|---|
| `Consume(c, next)` | if the current input character is `c` (or anything, for a dot), move to `next` |
| `Split(a, b)` | move to **both** `a` and `b`, without consuming input |
| `Match` | success |

`Split` is the entire idea. It is what a string pattern could not express: the
representation now has a way to say "the matcher is in two places at once", which is
what chapter 3 will exploit.

<figure>
<svg viewBox="0 0 800 176" role="img" aria-labelledby="dia-2-1-title">
  <title id="dia-2-1-title">The machine for a-star-b: a split state leading either into a loop consuming a, or forward to consume b</title>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--dia-muted)"/>
    </marker>
  </defs>
  <g fill="var(--dia-fill)" stroke="var(--dia-fg)" stroke-width="1.5">
    <circle cx="120" cy="104" r="26"/>
    <circle cx="360" cy="104" r="26"/>
    <circle cx="600" cy="104" r="26"/>
  </g>
  <g font-family="var(--font-ui)" font-size="13" fill="var(--dia-fg)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="120" y="104">split</text>
    <text x="360" y="104">'a'</text>
    <text x="600" y="104">'b'</text>
    <text x="712" y="104">match</text>
  </g>
  <g stroke="var(--dia-muted)" stroke-width="1.5" fill="none" marker-end="url(#arrow)">
    <path d="M 146 104 L 330 104"/>
    <path d="M 146 116 L 570 116"/>
    <path d="M 626 104 L 676 104"/>
    <path d="M 360 78 C 360 32, 120 32, 120 76"/>
  </g>
  <g font-family="var(--font-ui)" font-size="12" fill="var(--dia-muted)" text-anchor="middle">
    <text x="240" y="96">take one more</text>
    <text x="300" y="134">or stop here</text>
  </g>
</svg>
<figcaption>Figure 2-1. The machine for <code>a*b</code>. The split has no input
condition: both of its arrows are always available.</figcaption>
</figure>

## Thompson's construction

Compiling the tree is one function per node type, and each one returns a fragment: a
start state, plus a list of dangling arrows waiting to be pointed somewhere.

```python run env=engine file=code/compile.py caption="Compiling the tree into a flat list of states."
CONSUME, SPLIT, MATCH = "consume", "split", "match"


class Program:
    def __init__(self):
        self.states = []

    def emit(self, kind, **kw):
        self.states.append({"kind": kind, **kw})
        return len(self.states) - 1

    def __len__(self):
        return len(self.states)


def compile_node(node, prog, cont):
    """Emit states for `node`, continuing to state index `cont`. Returns the entry."""
    if node is None:
        return cont
    if isinstance(node, Char):
        return prog.emit(CONSUME, c=node.c, next=cont)
    if isinstance(node, Dot):
        return prog.emit(CONSUME, c=None, next=cont)
    if isinstance(node, Cat):
        right = compile_node(node.right, prog, cont)
        return compile_node(node.left, prog, right)
    if isinstance(node, Alt):
        a = compile_node(node.left, prog, cont)
        b = compile_node(node.right, prog, cont)
        return prog.emit(SPLIT, a=a, b=b)
    if isinstance(node, Star):
        split = prog.emit(SPLIT, a=cont, b=cont)      # placeholder, patched below
        body = compile_node(node.inner, prog, split)
        prog.states[split]["a"] = body
        prog.states[split]["b"] = cont
        return split
    raise TypeError(node)


def compile_pattern(src):
    prog = Program()
    match_state = prog.emit(MATCH)
    entry = compile_node(Parser(src).parse(), prog, match_state)
    return prog, entry


prog, entry = compile_pattern("a*b")
for i, s in enumerate(prog.states):
    print(i, s, "<-- entry" if i == entry else "")
```

```output
0 {'kind': 'match'} 
1 {'kind': 'consume', 'c': 'b', 'next': 0} 
2 {'kind': 'split', 'a': 3, 'b': 1} <-- entry
3 {'kind': 'consume', 'c': 'a', 'next': 2} 
```

Read state 2: it offers state 3 (consume an `a`, then come back to the split) or state
1 (consume the `b` and finish). That is `a*b`, and it is four states.

<details>
<summary>Predict: how many states does <code>a*a*a*b</code> compile to?</summary>

<p>Seven: one <code>match</code>, one <code>consume</code> for the <code>b</code>, and
a split plus a consume for each of the three stars. Compare that with chapter 1, where
the same pattern produced a search tree with tens of thousands of nodes. The machine
does not grow with the input at all.</p>

</details>

Compiling backwards — passing in the continuation and returning the entry — is what
avoids the dangling-arrow bookkeeping that Thompson's original formulation needs. The
star case still needs one patch, because its body must loop back to a state that does
not exist until the body has been compiled.

## The size guarantee

The property that matters for chapter 3:

```python run env=engine caption="State count against pattern length, for a family of patterns."
for stars in range(1, 7):
    src = "a*" * stars + "b"
    prog, _ = compile_pattern(src)
    print(f"{src:16} {len(src):>3} chars -> {len(prog):>3} states")
```

```output
a*b                3 chars ->   4 states
a*a*b              5 chars ->   6 states
a*a*a*b            7 chars ->   8 states
a*a*a*a*b          9 chars ->  10 states
a*a*a*a*a*b       11 chars ->  12 states
a*a*a*a*a*a*b     13 chars ->  14 states
```

One state per pattern character, plus one. Thompson's construction has this property
for every pattern in the language, and it is what makes the next chapter's simulation
possible: a set of active states can never be larger than the pattern.

## An error the parser should reject

```python expect-error env=engine expect="unclosed" caption="An unclosed group is rejected, and stays rejected."
Parser("(ab").parse()
```

The block above is checked on every build: it must fail, and its message must still
mention the unclosed group. Here is that message on its own, without the traceback.

```python run env=engine caption="The error a caller actually sees."
for bad in ["(ab", "a)b", "a**"]:
    try:
        Parser(bad).parse()
        print(f"{bad!r:6} accepted")
    except SyntaxError as e:
        print(f"{bad!r:6} rejected: {e}")
```

```output
'(ab'  rejected: unclosed (
'a)b'  rejected: unexpected ')' at 1
'a**'  accepted
```

Failing here is worth some care. A matcher that accepts a malformed pattern and
silently treats `(` as a literal will produce wrong answers on correct-looking input,
which is far harder to debug than a parse error.

## Practice

<div class="exercises">

<div class="exercise">
<span class="label">Exercise</span>
<p>Fill the blank so <code>+</code> (one or more) compiles correctly, reusing what you
already have.</p>

```python literal why="exercise stub; intentionally incomplete"
if isinstance(node, Plus):
    return compile_node(____, prog, cont)
```

<details><summary>Solution</summary>
<p><code>Cat(node.inner, Star(node.inner))</code>. Desugaring in the compiler rather
than adding a state kind keeps the simulator in chapter 3 unchanged — the fewer state
kinds it has to know about, the simpler it stays.</p>
</details>
</div>

<div class="exercise">
<span class="label">Exercise</span>
<p>Add <code>?</code> to the parser and compiler. Two lines each.</p>
</div>

<div class="exercise">
<span class="label">Exercise</span>
<p>Transfer: <code>compile_node</code> takes a continuation and returns an entry
point. Name one other place you have seen that shape.</p>

<details><summary>One answer</summary>
<p>Continuation-passing style generally; also the way a code generator emits a jump
target before the code that jumps to it. Both share the trick of deciding "where do I
go when I'm done" before emitting the work.</p>
</details>
</div>

</div>

## What to remember

- A recursive descent parser encodes precedence in its call stack: one method per level
- `Split` is the construct a pattern string cannot express, and it is why the machine is more powerful than the string
- Compiling backwards, with the continuation passed in, removes most of the arrow-patching
- Only the star case needs a patch, because its body loops back to itself
- The machine has one state per pattern character, and that bound holds for every pattern

**Terms introduced:** recursive descent, precedence level, continuation, Thompson's
construction, fragment, state machine.

## Next

We have a machine with a `Split` state that says "go both ways". Chapter 1 went one
way and backtracked. What happens if we go both ways at once?
