# Chapter 2: From Pattern to Machine

Hand `(ab)*` to the matcher from chapter 1 and it goes looking for a literal open parenthesis. `match_here` reads the pattern one character at a time, and the only two-character construct it knows is a star after a single character, so `(ab)*` means `(`, then `a`, then `b`, then any number of `)`. The text `(ab` matches it. The text `abab` does not. Nothing in chapter 1's language can say "these two characters, repeated", and its matcher could not be taught to, because the matcher *is* the pattern string, re-read from the front on every call.

Ken Thompson's 1968 paper takes the opposite view from its abstract onward. It describes "an implementation of this method in the form of a compiler" which ["accepts a regular expression as source language and produces an IBM 7094 program as object language"](https://www.oilshell.org/archive/Thompson-1968.pdf); the object program then reads the text. Compile once, match as often as you like, and what runs against the text is a machine. This chapter builds that machine in three files and 127 lines of Python, and ends by counting its states.

<div class="orient">
  <h3>What you'll learn</h3>
  <ul>
    <li>Parse the eight-construct pattern language into a tree, with precedence decided by the shape of the parser</li>
    <li>Compile the tree into a graph of states in which "either of these" is a state, not a decision</li>
    <li>Draw Thompson's wiring for concatenation, alternation, star, plus and optional from memory</li>
    <li>Count the states of any pattern without compiling it, and say why the count cannot depend on the text</li>
  </ul>
  <h3>Assumes you know</h3>
  <p>The recursive matcher of chapter 1, well enough to say what <code>match_star</code> gives back. Python dataclasses and <code>isinstance</code>. Nothing about parsers or automata.</p>
  <p class="meta">~45 min · 4 exercises</p>
</div>

<details>
  <summary>Warm-up: chapter 1 measured <code>a*a*a*b</code> at about eight times the cost per doubling of the input. Why cubic, and why not exponential?</summary>
  <p>Three stars, three nested give-back loops, each of about n trips, so about n³ calls. Exponential needs a quantifier inside a quantifier, and chapter 1's language cannot nest one, because a star can only follow a single character.</p>
</details>

<details>
  <summary>Warm-up: what exactly does <code>match_star</code> give back, and in what order?</summary>
  <p>Characters of its own run, one per failed attempt, from the longest run down to zero. It never gives back a character it did not take, and it never skips a length.</p>
</details>

<div class="crux">
  <div class="title">The crux</div>
  <p>A string can only say one thing at a time, and so can a tree. <code>a|b</code> needs something that can say "both, right now" without choosing and without coming back. What is the smallest such thing, and how many of them does a pattern need?</p>
</div>

## A tree first

`ab|c` matches `ab` or `c`, not `a` followed by one of `b` or `c`, and nothing in the string says so. You supply the grouping from a precedence rule you may never have seen written down. POSIX writes it down: the ERE table in [§9.4.8](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap09.html) ranks repetition above concatenation and concatenation above alternation, and adds that "concatenation has a higher order of precedence than alternation". Russ Cox compresses the same rule to [one sentence](https://swtch.com/~rsc/regexp/regexp1.html): the precedence, "from weakest to strongest binding, is first alternation, then concatenation, and finally the repetition operators". So `ab|c` is `(ab)|c`, `ab*` is `a(b*)`, and the parentheses in `(ab)*` exist to override the second of those.

The four constructs chapter 1 lacked are plus (`a+`, one or more), optional (`a?`, zero or one), alternation (`a|b`, either), and the group, which makes whatever it encloses a single unit for the operator after it. With literal, dot, concatenation and star, that is the whole language of this book. The structure that records how a pattern groups is an **abstract syntax tree**: one node per construct, its operands as children, and no trace of the parentheses that decided the shape. Every node type the language needs is in Listing 2-1. Notice how few there are, and which one carries flags.

```python run file=code/nodes.py caption="The tree. Five classes, no methods, no parentheses."
"""The tree a pattern parses into. One class per construct, nothing else."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Char:
    ch: str


@dataclass(frozen=True)
class Dot:
    pass


@dataclass(frozen=True)
class Concat:
    left: object
    right: object


@dataclass(frozen=True)
class Alt:
    left: object
    right: object


@dataclass(frozen=True)
class Repeat:
    child: object
    min: int       # 0 for * and ?, 1 for +
    many: bool     # True for * and +, False for ?
```

One class per construct, rather than one `Node` with a `kind` string, because the compiler in Listing 2-5 dispatches on type, and a node it does not recognise should fail at `isinstance` rather than fall off the end of a chain of string comparisons. `Repeat` is the one place the rule bends. `*`, `+` and `?` could be three classes, and the compiler would treat two of them identically except for a single entry point. Two fields hold the actual difference: `many` says whether there is a loop at all, and `min` says whether the loop must run once before it may be skipped. `frozen=True` is there because a node is a value: two parses of the same pattern compare equal, and nothing can edit a tree after the parser hands it over.

Turning the string into that tree is the parser's job, and Listing 2-2 does it by **recursive descent**: one method per **precedence level**, each obtaining its operands by calling the level that binds more tightly. Read `alt`, `concat`, `repeat` and `atom` in that order and you are reading the POSIX table from the bottom up.

```python run file=code/parse.py caption="The parser. Each method is one row of the precedence table."
"""Recursive descent, one method per precedence level: alt < concat < repeat < atom."""
from nodes import Char, Dot, Concat, Alt, Repeat


class Parser:
    def __init__(self, pattern):
        self.src = pattern
        self.pos = 0

    def peek(self):
        return self.src[self.pos] if self.pos < len(self.src) else None

    def take(self):
        ch = self.peek()
        self.pos += 1
        return ch

    def parse(self):
        node = self.alt()
        if self.peek() is not None:
            raise SyntaxError(f"unexpected {self.peek()!r} at {self.pos}")
        return node

    def alt(self):
        node = self.concat()
        while self.peek() == "|":
            self.take()
            node = Alt(node, self.concat())
        return node

    def concat(self):
        node = self.repeat()
        while self.peek() not in (None, "|", ")"):
            node = Concat(node, self.repeat())
        return node

    def repeat(self):
        node = self.atom()
        if self.peek() in ("*", "+", "?"):
            op = self.take()
            node = Repeat(node, min=1 if op == "+" else 0, many=op != "?")
        if self.peek() in ("*", "+", "?"):
            raise SyntaxError(f"multiple repeat at {self.pos}")
        return node

    def atom(self):
        ch = self.take()
        if ch == "(":
            node = self.alt()
            if self.take() != ")":
                raise SyntaxError("missing )")
            return node
        if ch == ".":
            return Dot()
        if ch is None or ch in "|)*+?":
            raise SyntaxError(f"expected a character, got {ch!r} at {self.pos - 1}")
        return Char(ch)


def parse(pattern):
    return Parser(pattern).parse()
```

<ol class="annot">
<li>Lines 24 to 29. The arms of an alternation come from <code>concat</code>, so they are whole sequences before <code>alt</code> ever sees a <code>|</code>. That is the precedence rule made structural: a method can only hold operands that bind more tightly than it does, or as Nystrom puts it in <a href="https://craftinginterpreters.com/parsing-expressions.html"><em>Crafting Interpreters</em></a>, "each rule here only matches expressions at its precedence level or higher".</li>
<li>Line 33. Juxtaposition is the operator, so <code>concat</code> loops until it meets something that cannot begin an atom: the end, a <code>|</code>, or the <code>)</code> that closes a group. Thompson's compiler had a whole first stage that "inserts the operator '.' for juxtaposition"; here the loop is the operator.</li>
<li>Lines 42 and 43. After one quantifier, a second is an error, not a nested <code>Repeat</code>. Python's <code>re</code> rejects <code>a**</code> with the same words, "multiple repeat", and it has to, because Python reads <a href="https://docs.python.org/3/library/re.html"><code>a+?</code> as a non-greedy plus</a>, not as an optional <code>a+</code>. Chapter 4 tells the story of how a test found that out.</li>
<li>Lines 48 to 52. A group is not a node. <code>atom</code> recurses into <code>alt</code>, the loosest level, and returns whatever comes back; the parentheses vanish. That is why Listing 2-7 can ignore them when it counts.</li>
</ol>

Recursive descent has a reputation as the method you use before you learn a real one. Nystrom's reply is that it is "the simplest way to build a parser" and also what "GCC, V8 (the JavaScript VM in Chrome), Roslyn (the C# compiler written in C#)" use. The grammar under Listing 2-2 is [Matt Might's](https://matt.might.net/articles/parsing-regex-with-recursive-descent/), with `+` and `?` admitted beside `*`.<label for="sn-2-1" class="margin-toggle sidenote-number"></label><input type="checkbox" id="sn-2-1" class="margin-toggle"><span class="sidenote">Might's top rule is right-recursive, so his parser reads <code>a|b|c</code> as <code>a|(b|c)</code>. Cox's yacc rule and the loop in Listing 2-2 lean left. For matching it makes no difference which way an alternation leans.</span> The trees for `(a|b)*c` and `abc` are in Listing 2-3. In the second, watch which way the concatenation leans.

```python run caption="Two trees. The star sits above the alternation, and the parentheses are gone."
from parse import parse

print(parse("(a|b)*c"))
print(parse("abc"))
```

```output
Concat(left=Repeat(child=Alt(left=Char(ch='a'), right=Char(ch='b')), min=0, many=True), right=Char(ch='c'))
Concat(left=Concat(left=Char(ch='a'), right=Char(ch='b')), right=Char(ch='c'))
```

`abc` leans left because the loop in `concat` folds each new atom onto the tree it already holds. Which way it leans never changes what matches. It does decide the order in which Listing 2-5 allocates states, a detail that only matters when you are staring at a printout of the machine, as you will be shortly.

<details>
  <summary>Predict: what tree does <code>ab|c</code> give, and what tree does <code>a(b|c)</code> give?</summary>
  <p><code>Alt(Concat(a, b), c)</code> and <code>Concat(a, Alt(b, c))</code>. In the first, <code>alt</code> calls <code>concat</code>, which consumes <code>ab</code> before <code>alt</code> gets to look at the <code>|</code>. In the second, <code>concat</code> takes <code>a</code>, then asks <code>repeat</code> for the next atom, which is a group, and <code>atom</code> restarts the whole descent at <code>alt</code> inside the parentheses.</p>
</details>

A pattern that ends before its group closes fails at the one line in the parser that demanded a `)`. The traceback in Listing 2-4 is also a trace of the descent.

```python expect-error expect="missing" caption="An unclosed group. Read the frames from the bottom: atom, repeat, concat, alt, parse."
from parse import parse

print(parse("a(b"))
```

```output
Traceback (most recent call last):
  File "snippet.py", line 3, in <module>
    print(parse("a(b"))
          ~~~~~^^^^^^^
  File "code/parse.py", line 61, in parse
    return Parser(pattern).parse()
           ~~~~~~~~~~~~~~~~~~~~~^^
  File "code/parse.py", line 19, in parse
    node = self.alt()
  File "code/parse.py", line 25, in alt
    node = self.concat()
  File "code/parse.py", line 34, in concat
    node = Concat(node, self.repeat())
                        ~~~~~~~~~~~^^
  File "code/parse.py", line 38, in repeat
    node = self.atom()
  File "code/parse.py", line 51, in atom
    raise SyntaxError("missing )")
SyntaxError: missing )
```

The call stack is the precedence table, one frame per level, and that is why the method is easy to debug: the frame that built a wrong node is a method you wrote, named after the grammar rule it implements.

## The machine

A tree still cannot say "both". `Alt(a, b)` names two children and leaves it to whoever walks the tree to choose, which is what chapter 1's matcher did, one child at a time, with a return trip when the first failed. The machine this chapter builds has a **state** for that, one with two outgoing arrows and no character on either, so that being in it means being in both of its successors at once.

Thompson's paper has two node types, "NNODE matches a single character" and "CNODE will split the current search path". Cox's C keeps the same two and adds a terminal. His `struct State` holds a character `c` and two pointers, and the [comment above it](https://swtch.com/~rsc/regexp/nfa.c.txt) is the whole design: "If c == Match, no arrows out; matching state. If c == Split, unlabeled arrows to out and out1 (if != NULL). If c < 256, labeled arrow with character c to out." Figure 2-1 draws the two kinds with arrows.

<figure>
<svg viewBox="0 0 800 176" role="img" aria-labelledby="dia-2-1-title">
  <title id="dia-2-1-title">A character state has one arrow and consumes one character to follow it; a split state has two arrows, consumes nothing, and the machine takes both</title>
  <defs>
    <marker id="arrow-ch2" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--dia-muted)"/>
    </marker>
  </defs>

  <g fill="var(--dia-fill)" stroke="var(--dia-fg)" stroke-width="1.5">
    <rect x="32"  y="64" width="128" height="48" rx="4"/>
    <rect x="240" y="64" width="96"  height="48" rx="4"/>
    <rect x="656" y="16" width="112" height="48" rx="4"/>
    <rect x="656" y="112" width="112" height="48" rx="4"/>
  </g>
  <g fill="var(--dia-fill)" stroke="var(--dia-accent)" stroke-width="2.5">
    <rect x="448" y="64" width="128" height="48" rx="4"/>
  </g>

  <g font-family="var(--font-ui)" font-size="14" fill="var(--dia-fg)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="96"  y="88">Char('a')</text>
    <text x="288" y="88">out</text>
    <text x="512" y="88" fill="var(--dia-accent)">Split</text>
    <text x="712" y="40">out</text>
    <text x="712" y="136">alt</text>
  </g>
  <g font-family="var(--font-ui)" font-size="13" fill="var(--dia-muted)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="200" y="76">consumes a</text>
    <text x="96"  y="144">one arrow, one character</text>
    <text x="512" y="144">two arrows, no character: both</text>
  </g>

  <g stroke="var(--dia-muted)" stroke-width="1.5" fill="none" marker-end="url(#arrow-ch2)">
    <path d="M 160 88 L 240 88"/>
    <path d="M 576 76 L 656 44"/>
    <path d="M 576 100 L 656 132"/>
  </g>
</svg>
<figcaption>Figure 2-1. The character state is chapter 1's literal test, frozen into a graph. The split state is the thing chapter 1 had no word for: an "either" that is a place rather than a choice.</figcaption>
</figure>

A character state has one arrow and consumes one character to follow it. A **split state** has two arrows and consumes nothing; when the machine reaches one, it takes both. The **match state** has no arrows, and reaching it with the text exhausted is what "the pattern matches" means. Every operator in the language is an arrangement of those three. What the textbooks call a nondeterministic finite automaton, an NFA, is a graph of exactly this kind, and the rest of this book calls it the machine. The compiler in Listing 2-5 is Cox's struct with Python names, plus one function that turns a tree into wired states. Read the second parameter of `compile_node` before you read any of its cases.

```python run file=code/machine.py caption="The compiler. Every case returns an entry state already wired to what follows it."
"""Thompson's construction, continuation style: each node is compiled knowing
what state comes after it, so no dangling pointers ever need patching."""
from dataclasses import dataclass
from nodes import Char, Dot, Concat, Alt, Repeat


@dataclass(eq=False)
class State:
    ch: str | None = None          # None on a split state; "." matches anything
    out: object = None             # next state after consuming ch
    alt: object = None             # second branch, split states only
    matched: bool = False


def compile_node(node, cont):
    """Return the entry state for `node`, wired so that finishing it leads to `cont`."""
    if isinstance(node, Char):
        return State(ch=node.ch, out=cont)
    if isinstance(node, Dot):
        return State(ch=".", out=cont)
    if isinstance(node, Concat):
        return compile_node(node.left, compile_node(node.right, cont))
    if isinstance(node, Alt):
        return State(out=compile_node(node.left, cont), alt=compile_node(node.right, cont))
    if isinstance(node, Repeat):
        if not node.many:                             # ?  one pass, or skip it
            return State(out=compile_node(node.child, cont), alt=cont)
        split = State(alt=cont)                       # * and +: a loop through a split
        split.out = compile_node(node.child, split)   # the child leads back to the split
        return split if node.min == 0 else split.out  # * enters at the split, + at the child
    raise TypeError(node)


def compile_pattern(node):
    return compile_node(node, State(matched=True))
```

<ol class="annot">
<li>Line 7. With <code>eq=False</code>, two states are equal only when they are the same object. A star wires a cycle, and value equality on a cycle would recurse until the stack ran out. Identity is also what chapter 3 relies on to remember which states it has visited.</li>
<li>Line 15. <code>cont</code> is the state after the node, and it exists before the node does; every case returns an entry state wired so that finishing the node lands there. Cox's C builds partial machines that "have one or more dangling arrows, pointing to nothing" and patches them later through a list of pointers to pointers. This version never has a dangling arrow, because the target is known at construction time. The two-endpoint idea is from <a href="https://julesjacobs.com/notes/nfa/nfa.pdf">Jules Jacobs' note</a>, whose <code>addRe(i, j, r)</code> adds <code>r</code> to a graph between states <code>i</code> and <code>j</code>. The name <strong>continuation style</strong> is this book's, not the literature's.</li>
<li>Line 22. Concatenation makes no state. The right child is compiled first so that the left child can be handed its entry as <code>cont</code>. The machine is built back to front, which is why <code>compile_pattern</code> makes the match state before anything else.</li>
<li>Lines 28 to 30. The star case allocates the split before compiling the child, because the child's <code>cont</code> <em>is</em> the split: the loop has to exist before anything can point at it. <code>*</code> and <code>+</code> build the same two-state loop and differ only in where the pattern enters, at the split when zero passes are allowed or at the child when one pass is forced. That is the entire content of <code>min</code>.</li>
</ol>

<div class="callout">
  <div class="title">This trips people up</div>
  <p>A split state does not choose. Chapter 1's matcher picked an alternative, tried it, and came back for the next; a split is a place where the machine is in two states at once, and nothing comes back because nothing left. If you catch yourself asking which arm the machine takes at a split, the answer is both, and chapter 3 is about what that answer costs.</p>
</div>

## Thompson's construction, one operator at a time

`a|b` and `a?` compile to the same split state. The difference is where the second arrow points. Figure 2-2 draws the wiring for each operator, with `next` standing in for whatever `cont` was when the operator was compiled. Cox's description of the same five shapes is the caption each panel deserves: concatenation "connects the final arrow of the e1 machine to the start of the e2 machine"; alternation "adds a new start state with a choice of either the e1 machine or the e2 machine"; `e?` "alternates the e machine with an empty path"; `e*` "uses the same alternation but loops a matching e machine back to the start"; and `e+` "also creates a loop, but one that requires passing through e at least once".

<figure>
<svg viewBox="0 0 800 352" role="img" aria-labelledby="dia-2-2-title">
  <title id="dia-2-2-title">Five fragments: ab chains two character states; a|b splits to a and b which rejoin; a* enters at a split whose child loops back; a+ enters at the child; a? splits to a or straight to next</title>

  <g fill="var(--dia-fill)" stroke="var(--dia-fg)" stroke-width="1.5">
    <rect x="24"  y="64"  width="64" height="40" rx="4"/>
    <rect x="136" y="64"  width="64" height="40" rx="4"/>
    <rect x="536" y="16"  width="64" height="40" rx="4"/>
    <rect x="536" y="112" width="64" height="40" rx="4"/>
    <rect x="136" y="208" width="64" height="40" rx="4"/>
    <rect x="280" y="248" width="64" height="40" rx="4"/>
    <rect x="648" y="208" width="64" height="40" rx="4"/>
  </g>
  <g fill="var(--dia-fill)" stroke="var(--dia-accent)" stroke-width="2.5">
    <rect x="424" y="64"  width="64" height="40" rx="4"/>
    <rect x="24"  y="248" width="64" height="40" rx="4"/>
    <rect x="392" y="208" width="64" height="40" rx="4"/>
    <rect x="536" y="248" width="64" height="40" rx="4"/>
  </g>
  <g fill="var(--dia-fill)" stroke="var(--dia-muted)" stroke-width="1.5">
    <rect x="248" y="64"  width="96" height="40" rx="4"/>
    <rect x="680" y="64"  width="96" height="40" rx="4"/>
    <rect x="136" y="296" width="96" height="40" rx="4"/>
    <rect x="392" y="296" width="96" height="40" rx="4"/>
    <rect x="648" y="296" width="96" height="40" rx="4"/>
  </g>

  <g font-family="var(--font-ui)" font-size="14" fill="var(--dia-fg)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="56"  y="84">a</text>
    <text x="168" y="84">b</text>
    <text x="568" y="36">a</text>
    <text x="568" y="132">b</text>
    <text x="168" y="228">a</text>
    <text x="312" y="268">a</text>
    <text x="680" y="228">a</text>
    <text x="456" y="84"  fill="var(--dia-accent)">Split</text>
    <text x="56"  y="268" fill="var(--dia-accent)">Split</text>
    <text x="424" y="228" fill="var(--dia-accent)">Split</text>
    <text x="568" y="268" fill="var(--dia-accent)">Split</text>
  </g>
  <g font-family="var(--font-ui)" font-size="14" fill="var(--dia-muted)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="296" y="84">next</text>
    <text x="728" y="84">next</text>
    <text x="184" y="316">next</text>
    <text x="440" y="316">next</text>
    <text x="696" y="316">next</text>
  </g>
  <g font-family="var(--font-ui)" font-size="14" fill="var(--dia-fg)"
     text-anchor="start" dominant-baseline="middle">
    <text x="24"  y="24">ab</text>
    <text x="424" y="24">a|b</text>
    <text x="24"  y="184">a*</text>
    <text x="280" y="184">a+</text>
    <text x="536" y="184">a?</text>
  </g>

  <g stroke="var(--dia-muted)" stroke-width="1.5" fill="none" marker-end="url(#arrow-ch2)">
    <path d="M 88 84 L 136 84"/>
    <path d="M 200 84 L 248 84"/>
    <path d="M 488 76 L 536 44"/>
    <path d="M 488 92 L 536 124"/>
    <path d="M 600 36 L 680 76"/>
    <path d="M 600 132 L 680 92"/>
    <path d="M 88 260 L 136 236"/>
    <path d="M 88 276 L 136 304"/>
    <path d="M 168 208 L 168 192 L 56 192 L 56 248"/>
    <path d="M 344 260 L 392 236"/>
    <path d="M 424 208 L 424 192 L 312 192 L 312 248"/>
    <path d="M 424 248 L 440 296"/>
    <path d="M 600 260 L 648 236"/>
    <path d="M 600 276 L 648 304"/>
    <path d="M 680 248 L 696 296"/>
  </g>
</svg>
<figcaption>Figure 2-2. One split per operator, none for concatenation. Star and plus are the same loop entered at opposite ends; optional is alternation with an empty second arm.</figcaption>
</figure>

Each panel is a **fragment**: a sub-machine with one entry state and one exit, the exit being whatever follows. Wiring fragments together, operator by operator, until the last exit is the match state is **Thompson's construction**, and the 1968 paper builds exactly these shapes. Its method differs in one respect: Thompson's compiler, and Cox's C after it, read the pattern in postfix and keep a stack of fragments, where the tree version here recurses. The shapes come out the same.<label for="sn-2-2" class="margin-toggle sidenote-number"></label><input type="checkbox" id="sn-2-2" class="margin-toggle"><span class="sidenote">Thompson's compiler has three stages: "a syntax sieve", conversion "to reverse Polish form", and "the object code producer". Every tutorial that compiles from postfix with a stack is following that paper, not a textbook.</span> In Listing 2-6 the machine for `(a|b)*c` is walked breadth-first from its entry and printed one state per line. Find the arrows that point backwards.

```python run caption="The machine for `(a|b)*c`, one state per line, numbered in order of discovery."
from parse import parse
from machine import compile_pattern


def walk(start):
    """Number states in discovery order and print each one with its arrows."""
    number, queue = {id(start): 0}, [start]
    while queue:
        s = queue.pop(0)
        arrows = []
        for target in (s.out, s.alt):
            if target is not None:
                if id(target) not in number:
                    number[id(target)] = len(number)
                    queue.append(target)
                arrows.append(f"s{number[id(target)]}")
        label = "Match" if s.matched else "Split" if s.ch is None else f"Char({s.ch!r})"
        print(f"s{number[id(s)]}: {label:<9}" + (" -> " + ", ".join(arrows) if arrows else ""))


walk(compile_pattern(parse("(a|b)*c")))
```

```output
s0: Split     -> s1, s2
s1: Split     -> s3, s4
s2: Char('c') -> s5
s3: Char('a') -> s0
s4: Char('b') -> s0
s5: Match
```

Two split states, three character states, one match state. `s0` is the star's split; its first arrow leads to the alternation's split `s1` and its second to `c`. Both `a` and `b` lead back to `s0`, which is the loop, and there is no state for the parentheses and none for the concatenation. The numbers are the walk's, not the compiler's, which is why the star's split is `s0` even though Listing 2-5 allocated the match state first.

<details>
  <summary>Predict: how many states does chapter 1's <code>a*a*a*b</code> compile to?</summary>
  <p>Eight. Three stars make three splits, four literals make four character states, and <code>compile_pattern</code> adds one match state. The pattern that cost chapter 1's matcher 822.2 ms at 320 characters of input is a machine of eight states, and in chapter 3 that number is the whole reason it runs fast.</p>
</details>

## The size guarantee

Nothing in Listing 2-5 allocates more than one `State` per case, and the concatenation case allocates none. Cox states the consequence: the construction "creates exactly one state per character or metacharacter in the regular expression, excluding parentheses", so the number of states "is at most equal to the length of the original regular expression". Add the match state, which `compile_pattern` makes once, and for this compiler the count is exact rather than a bound. Six patterns are checked in Listing 2-7, with the non-parenthesis character count printed beside the state count.

```python run caption="States against non-parenthesis characters. The right column is the middle column plus one, on every row."
from parse import parse
from machine import compile_pattern


def count_states(s, seen):
    if s is None or id(s) in seen:
        return
    seen.add(id(s))
    count_states(s.out, seen)
    count_states(s.alt, seen)


print(f"{'pattern':<12} {'chars':>5} {'states':>6}")
for pattern in ("a", "a*b", "a|b", "a*a*a*b", "(a|b)*c", "(ab)+(c|d)?"):
    chars = sum(1 for ch in pattern if ch not in "()")
    seen = set()
    count_states(compile_pattern(parse(pattern)), seen)
    print(f"{pattern:<12} {chars:>5} {len(seen):>6}")
```

```output
pattern      chars states
a                1      2
a*b              3      4
a|b              3      4
a*a*a*b          7      8
(a|b)*c          5      6
(ab)+(c|d)?      7      8
```

The count depends on the pattern alone. Whatever the text is, however long, the machine that reads it has m+1 states for a pattern of m non-parenthesis characters, and a machine cannot be in more states than it has. That is the promise chapter 3 collects on: if the machine never occupies more than m+1 states, the work it does per character of text is bounded by a number that does not grow with the text. No such number existed in chapter 1. Its alternatives lived in nested loops whose trip counts grew with the text, and nothing capped how many were pending at once.

<div class="aside">
  <div class="title">Aside</div>
  <p>Thompson saw the hazard in this construction in 1968. "Code compiled for a** will go into a loop due to the closure operator on an operand containing the null regular expression", he writes, and offers two ways out: refuse the expression at the syntax sieve, since "in most practical applications, this would not be a serious restriction", or recognise the empty string separately, so that "a** is compiled as λ|aa*(aa*)*". The parser in Listing 2-2 takes the first way out for <code>a**</code> and not for <code>(a*)*</code>, which compiles to a split whose arrows lead back to itself through a second split without consuming a character. Surviving that cycle is chapter 3's problem, and the trick it uses is in the same closing notes of Thompson's paper.</p>
</div>

## Practice

<div class="exercises">
  <div class="exercise">
    <span class="label">Exercise 1</span>
    <p>The dataclass reprs in Listing 2-3 are exact and hard to read. This pretty-printer indents one level per child. Fill in the blank so that a <code>Repeat</code> prints as <code>*</code>, <code>+</code> or <code>?</code>.</p>

```python literal why="exercise stub"
def show(node, depth=0):
    pad = "  " * depth
    if isinstance(node, Char):
        print(pad + node.ch)
    elif isinstance(node, Dot):
        print(pad + ".")
    elif isinstance(node, (Concat, Alt)):
        print(pad + type(node).__name__)
        show(node.left, depth + 1)
        show(node.right, depth + 1)
    elif isinstance(node, Repeat):
        print(pad + ________)
        show(node.child, depth + 1)
```

    <details><summary>Solution</summary><p><code>"*" if node.many and node.min == 0 else "+" if node.many else "?"</code>. The printer has to reconstruct the operator from the two fields, which is the cost of storing what the compiler needs instead of what the user typed. The parser could keep the operator character as a third field; it does not, because a field the compiler never reads is a place two versions of the truth can disagree.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 2</span>
    <p>Might's grammar has a base for an escaped character. Extend <code>atom</code> so that <code>\.</code> matches a literal dot and <code>\(</code> a literal parenthesis, and so that a pattern ending in a lone backslash is a syntax error.</p>

```python literal why="exercise stub"
def atom(self):
    ch = self.take()
    if ch == "\\":
        ...
    if ch == "(":
        ...
```

    <details><summary>Solution</summary><p>Take one more character; if it is <code>None</code>, raise <code>SyntaxError("trailing backslash")</code>; otherwise return <code>Char</code> of it, whatever it is. <code>atom</code> handles the escape entirely, so <code>\.*</code> parses as a starred literal dot with no change to <code>repeat</code>. Nothing in <code>nodes.py</code> or <code>machine.py</code> moves, which is the point of separating the tree from the string: a change to spelling is a change to one method.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 3</span>
    <p>The <code>count_states</code> of Listing 2-7 recurses once per state, so a long chain of literals compiles to a machine it cannot count. Write <code>count_states</code> without recursion and find the pattern length at which the recursive version fails.</p>
    <details><summary>Solution</summary><p>Keep an explicit stack of states to visit; pop one, skip it if seen, mark it, push its <code>out</code> and <code>alt</code>. Same set, one frame deep. You will find that <code>compile_node</code> fails first, since it recurses once per <code>Concat</code>; the fix, an explicit stack or a <code>Concat</code> holding a list, costs clarity in the listing that teaches the construction, so the book leaves the limit and says so here.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 4</span>
    <p>"Compile once, match often" is the reason this chapter exists. Name three other systems you use in which the same reason produced a two-stage design, and for each say what the compiled artefact is.</p>
    <details><summary>Solution</summary><p>Python's <code>re.compile</code>, whose artefact is a pattern object holding bytecode for its matcher. A database's prepared statement, whose artefact is a query plan. A GPU shader, compiled to a device program at load time. A template engine, which parses a template once into a tree of instructions. In every case the first run is slower than interpreting would have been, the second is faster, and a cache keyed on the source decides whether the trade pays.</p></details>
  </div>
</div>

## Mental model

- A pattern is parsed once into a tree of five node types. Parentheses shape the tree and then vanish.
- Precedence is the order of the parser's methods: `alt` calls `concat` calls `repeat` calls `atom`, and each method can only hold operands from the tighter level.
- A machine state is one of three things: a character with one arrow, a split with two arrows and no character, or the match state with none.
- Each node is compiled knowing the state after it, so concatenation makes no state and no arrow is ever patched. The machine is built from the match state backwards.
- Star and plus are the same loop entered at opposite ends; optional is a split whose second arrow skips the child.
- A pattern of m non-parenthesis characters compiles to exactly m+1 states, whatever the text.

**Terms introduced:** abstract syntax tree — the tree a pattern parses into, one node per construct with its operands as children and no record of the parentheses; recursive descent — a parser made of one function per grammar rule, each calling the rules it depends on; precedence level — one row of the operator-binding order, which in a recursive-descent parser is one method; state — a node of the machine, holding at most one character and at most two arrows; split state — a state with two arrows and no character, which the machine follows both at once; match state — the state with no arrows, whose occupation at the end of the text means the pattern matched; fragment — a sub-machine with one entry and one exit, produced by compiling one node; Thompson's construction — the wiring of fragments into a machine with one state per character or metacharacter, from Thompson's 1968 paper; continuation style — this book's name for compiling each node with the state that follows it already in hand, so that no arrow is ever left dangling.

## One opinion

I think the continuation-style compiler is the version to teach, and Cox's patch-list version is the version to read. Teach from Listing 2-5 because it is one function whose only subtle line is the star's allocation order, and that line is subtle for a reason the reader can see. Read Cox's C because it is the 1968 paper's method, a stack of fragments with holes patched afterwards, and it is how you find out that Thompson compiled straight to machine code with the same structure. Learn the construction from one and the history from the other.

## Going deeper

- Thompson, ["Programming Techniques: Regular expression search algorithm"](https://www.oilshell.org/archive/Thompson-1968.pdf), *Communications of the ACM*, 1968. Four pages: the machine-code lists, the `a**` remark, and the note chapter 3 depends on.
- Cox, ["Regular Expression Matching Can Be Simple And Fast"](https://swtch.com/~rsc/regexp/regexp1.html) (2007), and its [nfa.c](https://swtch.com/~rsc/regexp/nfa.c.txt). About 200 lines of C, postfix in, patch lists throughout.
- Might, ["Parsing regular expressions with recursive descent"](https://matt.might.net/articles/parsing-regex-with-recursive-descent/). The four-level grammar most tutorials copy.
- Aho, Lam, Sethi and Ullman, *Compilers*, 2nd ed., §3.7, for the textbook bound of at most twice the operators and operands. I read the argument in a [lecture transcript](https://cse.iitkgp.ac.in/~bivasm/notes/scribe/11CS10055.pdf), not the book.

The machine for `(a|b)*c` can stand in three states at once. Chapter 3 runs it, and finds out what "at once" costs.
