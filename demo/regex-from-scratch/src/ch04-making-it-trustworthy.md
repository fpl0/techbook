# Chapter 4: Making It Trustworthy

Chapter 3 ended by saying that on every example in it, `tinyre` agrees with `re`. A handful of examples, and I chose all of them. A test the author chose measures the author's imagination, and the patterns that break an engine are the ones nobody imagined. Russ Cox describes what RE2 does instead: ["Given a list of small regular expressions and operators, the RegexpGenerator class generates all possible expressions using those operators up to a given size. Then the StringGenerator generates all possible strings over a given alphabet up to a given size. Then, for every regular expression and every input string, the RE2 tests check that the output of the four different regular expression engines agree with each other, and with a trivial backtracking implementation written only for testing, and (usually) with PCRE itself."](https://swtch.com/~rsc/regexp/regexp3.html) Such tests "must limit themselves to small regular expressions and small input strings, but most bugs can be exposed by small test cases."

This chapter does the same to `tinyre`, with `re` in the role of PCRE. The first time I ran it, the two engines disagreed 171 times. None of the disagreements was a bug in the simulator. Each was a pattern with two meanings, and the fix was a decision rather than a patch. After that comes the part every engine owes its users: the list of what `tinyre` cannot do, and what the production engines that made the same trade do about each item.

<div class="orient">
  <h3>What you'll learn</h3>
  <ul>
    <li>Enumerate every small pattern and every short string, and compare two engines on all of them</li>
    <li>Read a mismatch report and decide whether the fault is in the simulator, the parser, or the meaning of the pattern</li>
    <li>Say which of the features you use every day an automata engine gives up, and why each one</li>
    <li>Name the production engines with a linear-time guarantee, and the terminology that makes the backtracking ones sound like them</li>
  </ul>
  <h3>Assumes you know</h3>
  <p>The public API of chapter 3: <code>tinyre.compile</code>, <code>fullmatch</code> and <code>search</code>. The <code>repeat</code> method of chapter 2's parser. What the live set forgets. <code>itertools.product</code>.</p>
  <p class="meta">~40 min · 4 exercises</p>
</div>

<details>
  <summary>Warm-up: chapter 1 called the Stack Overflow pattern <code>\s+$</code> quadratic. Where did its 199,990,000 steps come from, and what shape of pattern would have made it exponential?</summary>
  <p>One give-back loop inside the loop over start positions: 20,000 spaces from the first start, 19,999 from the second, down to one. Exponential needs a quantifier inside a quantifier, star height two, such as <code>(a+)+b</code>, and no pattern in chapter 1's language could reach it.</p>
</details>

<details>
  <summary>Warm-up: Listing 2-2 refuses <code>a+?</code> and accepts <code>(a+)?</code>. Why, and what tree does the second one parse to?</summary>
  <p><code>repeat</code> takes one quantifier and raises "multiple repeat" if another follows. Parentheses make <code>(a+)</code> an atom, so the <code>?</code> quantifies that atom: a <code>Repeat</code> with <code>many=False</code> around a <code>Repeat</code> with <code>min=1</code>. Chapter 3's simulator runs it without complaint. The machine cannot tell you what a pattern was supposed to mean, which is what this chapter is about.</p>
</details>

<div class="crux">
  <div class="title">The crux</div>
  <p>Two engines that agree on your examples can disagree on the next pattern. The space of patterns is infinite, so which finite part of it is worth checking completely, and what do you do when both engines are right and still disagree?</p>
</div>

## Every small pattern

Nine pieces: `a`, `b`, `.`, `*`, `+`, `?`, `|`, `(` and `)`. Every string of one to four pieces is 9 + 81 + 729 + 6,561 = 7,380 strings, and most of them are not patterns. `)(*` is one. Both engines reject 6,100 of the 7,380. Python's `re` accepts 608 more that `tinyre` refuses: 481 with an empty alternative or an empty group, `a|` and `()` and their relatives, which the `atom` method of Listing 2-2 rejects because it demands a character, and 127 with two quantifiers in a row, which the next section is about.<label for="sn-4-1" class="margin-toggle sidenote-number"></label><input type="checkbox" id="sn-4-1" class="margin-toggle"><span class="sidenote">Python reads <code>a|</code> as "<code>a</code> or the empty string". <code>tinyre</code> could accept it by letting <code>concat</code> return an empty node. The tree has no node for the empty string, and adding one for the sake of patterns nobody types on purpose would be a class the compiler never needs, the case Listing 2-1 argued against.</span> That leaves 672 patterns both engines compile. On the other side, every string over `ab` of length zero to three is 1 + 2 + 4 + 8 = 15 strings. Multiply and the whole test is 10,080 cases, which a Python loop finishes in about a tenth of a second.

Running two implementations on the same inputs and treating every disagreement as a finding is **differential testing**. It works here because an oracle already exists: `re` has been answering these questions for far longer than `tinyre` has, so a disagreement is a question to investigate rather than a verdict against either side. Generating every input up to a size bound, rather than sampling, is **exhaustive enumeration**, and it is what lets a count of zero mean something. A random sample that finds nothing has found nothing; an enumeration that finds nothing has proved a statement about a finite set, exactly as strong as the set is large. In Listing 4-1, watch what happens to a pattern only one engine accepts, and which method of the two pattern objects gets compared.

```python run file=code/difftest.py caption="The differential test. Two generators, one loop, and the comparison is a single `!=`."
"""Differential test: every small pattern, every short string, tinyre against re."""
import itertools
import re
import tinyre

ALPHABET = "ab"
PIECES = ["a", "b", ".", "*", "+", "?", "|", "(", ")"]


def patterns(max_len):
    """Every string of PIECES up to max_len that both engines accept."""
    for n in range(1, max_len + 1):
        for parts in itertools.product(PIECES, repeat=n):
            source = "".join(parts)
            try:
                re.compile(source)
                tinyre.compile(source)
            except (re.error, SyntaxError):
                continue
            yield source


def strings(max_len):
    for n in range(max_len + 1):
        for chars in itertools.product(ALPHABET, repeat=n):
            yield "".join(chars)


def run(max_pattern=4, max_string=3):
    cases = mismatches = 0
    for source in patterns(max_pattern):
        ours, theirs = tinyre.compile(source), re.compile(source)
        for text in strings(max_string):
            cases += 1
            if ours.fullmatch(text) != (theirs.fullmatch(text) is not None):
                mismatches += 1
                if mismatches <= 5:
                    print(f"  {source!r} on {text!r}: tinyre says "
                          f"{ours.fullmatch(text)}, re says the opposite")
    return cases, mismatches


if __name__ == "__main__":
    cases, mismatches = run()
    print(f"{cases} cases, {mismatches} mismatches")
```

```output
10080 cases, 0 mismatches
```

<ol class="annot">
<li>Lines 10 to 19. A pattern either engine rejects is skipped, not counted, because compiling and matching are different questions. The 608 strings that only <code>re</code> accepts are a syntax disagreement, and this test is blind to them by construction. A version that counted them as failures would report 608 failures that no change to the simulator could fix.</li>
<li>Line 34. <code>fullmatch</code>, not <code>search</code>. Ninety of the 672 patterns can match the empty string, and <code>search</code> says <code>True</code> on every text for those, so about a seventh of the test would be checking nothing. The second reason is about spans. Ask <em>where</em> the match is and the two engines stop answering the same question. Python, like Perl, returns the <strong>leftmost-first</strong> match: the earliest start, then the alternative the pattern reaches first, which the ECMAScript specification states as <a href="https://tc39.es/ecma262/multipage/text-processing.html"><code>/a|ab/.exec("abc")</code> returning <code>"a"</code> and not <code>"ab"</code></a>. POSIX wants <strong>leftmost-longest</strong>, the earliest start and then the longest match from it, a rule of which Cox says <a href="https://swtch.com/~rsc/regexp/regexp2.html">"POSIX's rules haven't caught on"</a>. Chapter 3's live set records neither preference, so the one answer it can give identically is the yes or no of the whole text.</li>
<li>Lines 36 to 39. At most five cases are printed, and they are the five smallest, because the enumeration runs shortest pattern first and shortest string first. A failing run hands you a minimal reproducer without a second tool.</li>
</ol>

Listing 4-2 runs the test from a script that imports it, and prints the two factors before the product. The last line is the promise this book makes about `tinyre`.

```python run caption="The two generators counted separately, then every pattern against every string."
import difftest

print(len(list(difftest.patterns(4))), "patterns,", len(list(difftest.strings(3))), "strings")
cases, mismatches = difftest.run()
print(f"{cases:,} cases, {mismatches} mismatches")
```

```output
672 patterns, 15 strings
10,080 cases, 0 mismatches
```

Read the number for what it is. On 672 patterns and 15 strings, `tinyre.fullmatch` and `re.fullmatch` never disagree. It says nothing about longer patterns, nothing about a third letter, and nothing about the 608 patterns it skipped. Cox's sentence about small test cases is a claim about where bugs live, not a proof. What the enumeration buys is confidence of a different kind from a handful of examples: not "the cases I thought of pass" but "every case below this size passes", with the size stated.

<details>
  <summary>Predict: extend the strings to length four over the same alphabet, leaving the patterns alone. How many cases does the test run?</summary>
  <p>20,832. Strings over <code>ab</code> of length zero to four are 1 + 2 + 4 + 8 + 16 = 31, and the 672 patterns are unchanged, so 672 × 31. Each extra letter of string doubles the string count; each extra piece of pattern multiplies the raw pattern count by nine before the two parsers thin it. The string side is the cheap one to extend.</p>
</details>

<div class="callout">
  <div class="title">This trips people up</div>
  <p>"Zero mismatches on ten thousand cases, so the engine is correct." Count the pieces. <code>(a*)*</code> is five, so no pattern in the whole test has a quantifier inside a quantifier, and the split cycle that chapter 3 built <code>seen</code> to survive is never exercised here. <code>(a*)*b</code>, the pattern of Listing 3-7, is six pieces long, two past the bound. A test bounded by size is silent about everything past the bound, and the bound is a number you chose. State it next to the result, every time.</p>
</div>

## The mismatch the test found

The parser in Listing 2-2 was not the first parser. The first version's `repeat` method looped: after one quantifier it looked for another and wrapped the node again, so `a+?` parsed as `(a+)?` and `a?+` as `(a?)+`. Each of those is a legal tree, the compiler wires it, the simulator runs it, and nothing in the three files had any reason to object. The test did. With that parser accepting 798 patterns instead of 672, it ran 11,970 cases and reported 171 mismatches, spread over 56 patterns, and every one of the 56 had two quantifiers side by side. The first line of the report was `'a+?'` on the empty string, `tinyre` saying `True`. The second was `'a?+'` on `'aa'`, `tinyre` saying `True` again.

Python's `re` reads both patterns, and gives each a meaning of its own. A `?` after a quantifier makes it a **lazy quantifier**, which the [`re` documentation](https://docs.python.org/3/library/re.html) calls non-greedy: `a+?` still demands at least one `a`, and only its appetite has changed. So it does not match the empty string, and `(a+)?` does. A `+` after a quantifier is a **possessive quantifier**, and that reading is recent. The 3.11 release notes say ["Atomic grouping ((?>...)) and possessive quantifiers (*+, ++, ?+, {m,n}+) are now supported in regular expressions"](https://docs.python.org/3/whatsnew/3.11.html), and the reference describes what possessive means: possessive quantifiers "do not allow back-tracking when the expression following it fails to match". `a?+` takes an `a` if there is one and will not give it back, so on `aa` the second `a` has nowhere to go, and the match fails where `(a?)+` succeeds. `a*+a` is the sharpest case: it takes every `a` in the text, refuses to return one for the literal, and matches nothing at all. The two engines were both right about the pattern each believed it had been given.

The fix had two candidates. One was to implement both meanings. A lazy quantifier is a preference between matches, and chapter 3's set holds no preferences; a possessive quantifier is defined by what a backtracker refuses to do, and the RE2 syntax page lists [possessive quantifiers among the constructs it does not support](https://github.com/google/re2/wiki/Syntax). The other candidate was Thompson's, the "syntax sieve" from chapter 3: refuse. `re` refuses `a**` with the message "multiple repeat". Listing 2-2 refuses every second quantifier with the same words, and Listing 4-3 shows the refusal reaching the public API.

```python expect-error expect="multiple repeat" caption="A stacked quantifier is a syntax error, not a guess."
import tinyre

print(tinyre.compile("a+?"))
```

```output
Traceback (most recent call last):
  File "snippet.py", line 3, in <module>
    print(tinyre.compile("a+?"))
          ~~~~~~~~~~~~~~^^^^^^^
  File "code/tinyre.py", line 20, in compile
    return Pattern(source)
  File "code/tinyre.py", line 10, in __init__
    self.start = compile_pattern(parse(source))
                                 ~~~~~^^^^^^^^
  File "code/parse.py", line 61, in parse
    return Parser(pattern).parse()
           ~~~~~~~~~~~~~~~~~~~~~^^
  File "code/parse.py", line 19, in parse
    node = self.alt()
  File "code/parse.py", line 25, in alt
    node = self.concat()
  File "code/parse.py", line 32, in concat
    node = self.repeat()
  File "code/parse.py", line 43, in repeat
    raise SyntaxError(f"multiple repeat at {self.pos}")
SyntaxError: multiple repeat at 2
```

The argument for refusing is not that the construct is rare. A pattern that means one thing in this engine and another in the engine it is checked against is worse than a syntax error, because the syntax error is found at compile time by the first person to type it and the difference in meaning is found in production by the last. The refusal also keeps the test honest. Çakar, Lee and Davis, surveying testing practice across 22 engines, note that differential testing ["is concerning because regex syntax and semantics vary significantly between dialects (e.g., POSIX vs. PCRE)"](https://arxiv.org/abs/2603.00311). `tinyre` avoids the dialect problem by having no dialect: its syntax is a strict subset of Python's, so after this fix every pattern both engines accept means the same thing in both, and a disagreement can only be a bug. The same paper observes that byte-level mutation produces "syntactically invalid inputs that exercise only parsing logic, not matching internals", which is why Listing 4-1 enumerates pieces of the grammar rather than bytes.

A syntax mismatch is one class of bug. The class the test exists for is a wrong machine, and Listing 4-4 makes one on purpose: it replaces `machine.compile_node` with a version whose `?` case compiles the child without the skip arrow, so that `a?` behaves like `a`, and then runs the test. The interesting part of the output is which five cases it prints.

```python run caption="An injected bug in the `?` case, and the test's report of it. The listed cases are the five smallest."
import machine
from nodes import Repeat
import difftest

original = machine.compile_node


def buggy(node, cont):
    """The `?` case with its skip arrow removed: `a?` now behaves like `a`."""
    if isinstance(node, Repeat) and not node.many:
        return buggy(node.child, cont)
    return original(node, cont)


machine.compile_node = buggy
cases, mismatches = difftest.run()
print(f"{cases:,} cases, {mismatches} mismatches")
```

```output
  'a?' on '': tinyre says False, re says the opposite
  'b?' on '': tinyre says False, re says the opposite
  '.?' on '': tinyre says False, re says the opposite
  'aa?' on 'a': tinyre says False, re says the opposite
  'ab?' on 'a': tinyre says False, re says the opposite
10,080 cases, 334 mismatches
```

The report diagnoses itself. Every listed pattern has a `?`, every listed text is the one that omits the optional character, and the first line is the smallest pattern in the language that can show the fault. The replacement has to be assigned to the module attribute, because `compile_node` recurses through its module-global name and `compile_pattern` looks it up there at call time, the same lesson as chapter 1's exercise 3. Nothing in `difftest.py` knows the bug exists. It compares two answers, and 334 times they differ.

<details>
  <summary>Predict: inject a different bug, so that <code>a*</code> compiles as <code>a?</code>. Which case does the report print first?</summary>
  <p><code>'a*'</code> on <code>'aa'</code>, <code>tinyre</code> saying <code>False</code>. The empty string and a single <code>a</code> both match <code>a?</code>, so the smallest text that separates the two is two letters long, and the smallest pattern is the one-quantifier star. The bug is one loop removed, and the reproducer is the shortest text that needs the loop. Run it and the count is 346 mismatches.</p>
</details>

## What we gave up

Ten thousand agreements were bought by a small language. The table says which of the constructs you use daily `tinyre` has, and puts RE2 beside it, because RE2 made the same trade and shows how much of the everyday language survives it. The RE2 column comes from its [syntax page](https://github.com/google/re2/wiki/Syntax) and its README; the Python column from the [`re` reference](https://docs.python.org/3/library/re.html).

| Construct | `tinyre` | RE2 | Python `re` |
|---|---|---|---|
| literal, `.`, concatenation, `*`, `+`, `?`, `\|`, `( )` | yes | yes | yes |
| anchors `^` `$` | no | yes | yes |
| character classes `[a-z]`, `\d` | no | yes | yes |
| capture groups reporting a span | no | yes | yes |
| lazy quantifiers `+?` | no | yes | yes |
| possessive quantifiers `++` | no | no | 3.11 and later |
| lookaround `(?=…)` | no | no | yes |
| backreferences `\1` | no | no | yes |

The first three missing rows are absence, not sacrifice. An anchor is a state that consumes nothing and checks a position; a class is a character state with a set instead of a character; Unicode is a class with a larger alphabet and a normalisation problem in front of it. None of them threatens the bound, and RE2 has all of them. The interesting rows are the last four, where an automata engine has to decide.

Captures cost a constant, and chapter 3 named the design that pays it. The Pike VM keeps one thread per state and each thread carries its saved positions, so the m+1 bound survives. Cox reports what it costs in RE2: the NFA "must copy around submatch boundary sets", so ["it can be slower in common cases than a backtracker like PCRE. In exchange for guaranteed worst case performance, the average case suffers a little"](https://swtch.com/~rsc/regexp/regexp3.html). That is a trade the engines below take gladly, and the reason each of them puts something faster in front of the VM for the cases that do not need it.

Backreferences and lookaround are where RE2 draws its line, and it draws it as policy. Its README states: ["As a matter of principle, RE2 does not support constructs for which only backtracking solutions are known to exist. Thus, backreferences and look-around assertions are not supported."](https://github.com/google/re2/blob/main/README.md) For backreferences the reason is the one chapter 3 gave, that two threads in the same state stop being interchangeable, and Cox's statement that the problem is NP-complete stands behind it. Lookaround is a softer case. Cox writes of generalised assertions that they "are harder to accommodate but in principle could be encoded in the NFA", and RE2 leaves them out anyway. Rust's `regex` crate says the same in its own words: it ["lacks several features that are not known how to implement efficiently. This includes, but is not limited to, look-around and backreferences. In exchange, all regex searches in this crate have worst case O(m * n) time complexity"](https://docs.rs/regex/latest/regex/).

## Where the real engines go

RE2 exists because Google Code Search took patterns from strangers. Cox: ["Since Code Search accepts regular expressions from anyone on the Internet, using PCRE would have left it open to easy denial of service attacks."](https://swtch.com/~rsc/regexp/regexp3.html) The README puts the goal first: "Safety is RE2's primary goal", and "One of its primary guarantees is that the match time is linear in the length of the input string". The engine RE2 runs first is a **lazy DFA**, which is chapter 3's simulation with a cache in front of it. Each distinct live set becomes a DFA state the first time it is seen. The transition out of it on each character is computed once and stored, so a text that keeps producing the same sets, as `(a|b)*c` did in Figure 3-1, costs one table lookup per character. The number of distinct sets can be exponential in the pattern. So the cache is bounded, and Cox says what happens at the bound: ["The RE2 DFA treats its states as a cache; if the cache fills, the DFA frees them all and starts over. This lets the DFA operate in a fixed amount of memory despite considering an arbitrary number of states during the course of the match."](https://swtch.com/~rsc/regexp/regexp3.html) Throwing the table away costs time and never correctness. The simulation underneath still runs. The DFA finds where the match is; when captures are wanted, "then it is time to invoke the NFA to find submatch boundaries".

Go's `regexp` package accepts RE2's syntax, and its documentation makes the promise in one sentence: ["The regexp implementation provided by this package is guaranteed to run in time linear in the size of the input. (This is a property not guaranteed by most open source implementations of regular expressions.)"](https://pkg.go.dev/regexp)<label for="sn-4-2" class="margin-toggle sidenote-number"></label><input type="checkbox" id="sn-4-2" class="margin-toggle"><span class="sidenote">Go defaults to leftmost-first, "the one that a backtracking search would have found first", and offers <code>CompilePOSIX</code> and <code>Regexp.Longest</code> for leftmost-longest. Either way the answer is a preference between matches, which is the thing chapter 3's set does not record.</span> Rust's `regex` crate stacks four engines behind one interface, and Andrew Gallant's account of the design is the clearest description of an engine ladder I know. Figure 4-1 draws it. The lazy DFA goes first, to find the bounds of a match; if captures are needed, a one-pass DFA handles patterns that never have two live choices at once, a **bounded backtracker** handles the rest while "len(regex) * len(haystack)" fits its visited bitmap, and the Pike VM handles everything. Gallant's summary is that ["Only the PikeVM is required"](https://burntsushi.net/regex-internals/); every other engine is an optimisation with a condition on it, and when the condition fails the search falls through to the one that always works.

<figure>
<svg viewBox="0 0 800 360" role="img" aria-labelledby="dia-4-1-title">
  <title id="dia-4-1-title">Rust's regex crate tries the lazy DFA first, then for captures a one-pass DFA, then a bounded backtracker, and falls through to the PikeVM, the one engine that is always able to answer</title>
  <defs>
    <marker id="arrow-ch4" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--dia-muted)"/>
    </marker>
  </defs>

  <g fill="var(--dia-fill)" stroke="var(--dia-fg)" stroke-width="1.5">
    <rect x="216" y="16"  width="272" height="56" rx="4"/>
    <rect x="216" y="104" width="272" height="56" rx="4"/>
    <rect x="216" y="192" width="272" height="56" rx="4"/>
  </g>
  <g fill="var(--dia-fill)" stroke="var(--dia-accent)" stroke-width="2.5">
    <rect x="216" y="280" width="272" height="56" rx="4"/>
  </g>

  <g font-family="var(--font-ui)" font-size="16" fill="var(--dia-fg)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="352" y="44">lazy DFA</text>
    <text x="352" y="132">one-pass DFA</text>
    <text x="352" y="220">bounded backtracker</text>
    <text x="352" y="308" fill="var(--dia-accent)">PikeVM</text>
  </g>

  <g font-family="var(--font-ui)" font-size="15" fill="var(--dia-muted)"
     text-anchor="start" dominant-baseline="middle">
    <text x="504" y="36">chapter 3's sets, memoised;</text>
    <text x="504" y="56">cache cleared when it fills</text>
    <text x="504" y="124">captures, if the pattern never</text>
    <text x="504" y="144">has two live choices at once</text>
    <text x="504" y="212">chapter 1 with a visited bitmap;</text>
    <text x="504" y="232">only while regex × text fits</text>
    <text x="504" y="300">chapter 3's simulator with threads;</text>
    <text x="504" y="320">the only engine that is required</text>
  </g>
  <g font-family="var(--font-ui)" font-size="15" fill="var(--dia-accent)"
     text-anchor="end" dominant-baseline="middle">
    <text x="200" y="88">match found, captures needed</text>
    <text x="200" y="176">pattern is not one-pass</text>
    <text x="200" y="264">too big for the bitmap</text>
  </g>

  <g stroke="var(--dia-muted)" stroke-width="1.5" fill="none" marker-end="url(#arrow-ch4)">
    <path d="M 352 72 L 352 104"/>
    <path d="M 352 160 L 352 192"/>
    <path d="M 352 248 L 352 280"/>
  </g>
</svg>
<figcaption>Figure 4-1. The three engines above the bottom one are faster and conditional. The condition is checked, not hoped for, and the fall-through lands on the machine this book built, so the worst case is chapter 3's bound and never chapter 1's.</figcaption>
</figure>

.NET 7 added a `NonBacktracking` option, which Stephen Toub describes as ["grounded in the Symbolic Regex Matcher work from Microsoft Research"](https://devblogs.microsoft.com/dotnet/regular-expression-improvements-in-dotnet-7/). It "starts with a DFA, building out the nodes lazily, and at some point if the graph gets too big, it switches over dynamically to NFA-based processing", the top of the same ladder, and it gives up the same rows of the table: "Atomic groups, Backreferences, Balancing groups, Conditional, Lookarounds". Toub adds that "the goal of NonBacktracking is not to be always faster than the backtracking engines". It is an option, not the default.

That is the pattern everywhere. The defaults of Perl, PCRE, Python, Java and JavaScript all backtrack, and the words their documentation uses will mislead you if you have read this book. The PCRE2 manual says its ["standard algorithm is an 'NFA algorithm'. It conducts a depth-first search of the pattern tree"](https://www.pcre.org/current/doc/html/pcre2matching.html). Java's `Pattern` class says its engine ["performs traditional NFA-based matching with ordered alternation as occurs in Perl 5"](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/regex/Pattern.html). Depth-first search of a pattern tree is chapter 1. The word NFA in those two sentences names a machine like chapter 2's and then a matcher that walks it one path at a time, which is what the machine was built to avoid. Cox and Gallant both put the phrase in quotation marks, and you should too. ECMAScript defines its pattern semantics with [backtracking continuations](https://tc39.es/ecma262/multipage/text-processing.html) outright. Python's `re` documentation mentions no step limit and no timeout; my runs in chapter 1 went to 24 characters without one interrupting, which is an observation about this interpreter and not a documented guarantee.

<div class="tip">
  <div class="title">Tip</div>
  <p>If the text or the pattern comes from someone you do not control, use an engine with a bound or put a clock on the one you have. RE2, Go's <code>regexp</code>, Rust's <code>regex</code> and .NET's <code>NonBacktracking</code> give up backreferences and lookaround in exchange for a worst case you can state. If you must stay on a backtracker, the third-party <a href="https://pypi.org/project/regex/"><code>regex</code> module</a> for Python accepts a timeout on every matching call and raises when it expires; the standard <code>re</code> does not. A pattern that cannot use either is a pattern you have decided to trust on every input it will ever see.</p>
</div>

## Practice

<div class="exercises">
  <div class="exercise">
    <span class="label">Exercise 1</span>
    <p>Add a third letter to the pieces without adding it to the alphabet of the strings. Fill in the blank, run the test, and explain why the case count rises even though no string contains a <code>c</code>.</p>

```python literal why="exercise stub"
PIECES = ["a", "b", ".", "*", "+", "?", "|", "(", ")", ________]
```

    <details><summary>Solution</summary><p><code>"c"</code>. The count is 22,260 cases with no mismatches: 1,484 patterns instead of 672, times the same 15 strings. A pattern such as <code>c*</code> or <code>a|c</code> is a perfectly good test against texts that lack a <code>c</code>, since both engines must agree that the branch never fires. Each pattern that mentions <code>c</code> is being tested on its <em>other</em> alternatives, a kind of case the two-letter version could not reach.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 2</span>
    <p>Add <code>search</code> to the comparison as a second check alongside <code>fullmatch</code>. Finish the stub so that a case counts as a mismatch if either answer differs.</p>

```python literal why="exercise stub"
def run(max_pattern=4, max_string=3):
    cases = mismatches = 0
    for source in patterns(max_pattern):
        ours, theirs = tinyre.compile(source), re.compile(source)
        for text in strings(max_string):
            cases += 1
            full_ok = ours.fullmatch(text) == (theirs.fullmatch(text) is not None)
            search_ok = ...
            if not (full_ok and search_ok):
                ...
    return cases, mismatches
```

    <details><summary>Solution</summary><p><code>ours.search(text) == (theirs.search(text) is not None)</code>, and the body of the <code>if</code> increments and prints as before, naming which of the two checks failed. The boolean <code>search</code> is comparable because existence of a match anywhere does not depend on leftmost-first or leftmost-longest; only the span does. Expect the count of cases to stay at 10,080 and the count of useful cases to fall, since the 90 patterns that match the empty string now contribute 1,350 checks that can never fail. The exercise is worth doing for the re-entry logic of chapter 3's <code>search</code>, which the <code>fullmatch</code> test never touched.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 3</span>
    <p>Change the string alphabet to <code>abc</code> and the string length to four, keeping the nine pieces. Before running it, work out how many strings and how many cases there will be, then run it and check.</p>
    <details><summary>Solution</summary><p>Strings over three letters of length zero to four are 1 + 3 + 9 + 27 + 81 = 121. The patterns are unchanged at 672, since the pieces are unchanged, so 672 × 121 = 81,312 cases, and the run reports zero mismatches in well under a second. The third letter matters more than it looks: it is the first text character that no literal in any pattern can match, so every <code>.</code> is now being tested against something an <code>a</code> or <code>b</code> state must refuse.</p></details>
  </div>
  <div class="exercise">
    <span class="label">Exercise 4</span>
    <p>Differential testing is not a regex idea. Write your own <code>parse_int(s)</code> for decimal strings with an optional sign, then enumerate every string of up to four characters over <code>"0123456789+- "</code> and compare it with <code>int(s)</code>, treating "raises" as an answer. Report what you found, and say which disagreements were bugs and which were decisions.</p>
    <details><summary>Solution</summary><p>Most people's first version disagrees with <code>int</code> on at least three of: leading and trailing whitespace (<code>int(" 7 ")</code> is 7), a lone sign, an empty string, and the <code>_</code> digit separator if you add it to the alphabet. Each disagreement forces the question this chapter's mismatch forced: is <code>int</code>'s behaviour the specification, or a dialect you have chosen not to speak? The whitespace rule is a specification to follow; a lone sign is a case both should reject, and if yours accepts it, that is a bug. A parser that documents "no whitespace" and rejects it is making the decision Listing 2-2 made, and the test should then skip those inputs the way Listing 4-1 skips the patterns only one engine accepts.</p></details>
  </div>
</div>

## Mental model

- Two engines that agree on your examples have agreed on your imagination. Enumerate every pattern and string below a size bound instead, and state the bound beside the result.
- A differential test needs an oracle with the same meaning for every input it accepts. `tinyre` is a strict subset of Python's syntax so that any disagreement is a bug and never a dialect.
- A pattern with two meanings is refused, not guessed. `a+?` is lazy in Python, `a?+` is possessive, and the parser answers both with "multiple repeat".
- The one answer the live set can give identically to a backtracker is the yes or no of `fullmatch`. Spans need a preference, leftmost-first or leftmost-longest, that the set does not record.
- Anchors, classes and Unicode are absent from `tinyre` and cost an automata engine nothing. Captures cost a constant. Backreferences and lookaround are the line RE2, Go and Rust refuse to cross.
- Production automata engines are a ladder: a lazy DFA first, faster engines with conditions, and the Pike VM at the bottom, always able to answer.
- Perl, PCRE, Python, Java and JavaScript backtrack by default, and two of them call it NFA matching.

**Terms introduced:** differential testing — running two implementations on the same inputs and treating every disagreement as a finding to investigate; exhaustive enumeration — generating every input up to a stated size bound rather than a sample of them; lazy quantifier — a quantifier followed by `?`, which in Python matches as few repetitions as it can before letting the rest of the pattern try; possessive quantifier — a quantifier followed by `+`, which in Python 3.11 and later takes as many repetitions as it can and never gives any back; leftmost-first — the Perl and Python rule for choosing among matches: the earliest start, then the alternative the pattern reaches first; leftmost-longest — the POSIX rule: the earliest start, then the longest match from it; lazy DFA — a DFA whose states are live sets built as the text demands them and kept as a bounded cache that is cleared when full.

## One opinion

I think that for anything reading input from the internet, the default regex engine of Python, Java, JavaScript and Perl is the wrong default, and I would say so in a code review. The argument for backtracking is real: captures come for free, backreferences and lookaround exist, and the common case is fast. All three are about what the pattern can express, and none of them is about what the input can do to you. Chapter 1 showed a seven-character pattern that turns twenty-four characters of input into half a second, and two outages that needed only quadratic cost. The engines in this chapter give up two features and gain a sentence you can put in a design document: the match time is linear in the input. If the feature list wins that argument for a service that reads headers from strangers, I would like to see the pattern that needed the backreference.

## Going deeper

- Cox, ["Regular Expression Matching in the Wild"](https://swtch.com/~rsc/regexp/regexp3.html) (2010). The RE2 design, engine by engine, and the "Testing" section this chapter's test is modelled on. Read it for the one-pass NFA and the cache-flushing DFA.
- Gallant, ["Regex engine internals as a library"](https://burntsushi.net/regex-internals/) (2023). The Rust ladder of Figure 4-1 with the conditions on each rung, from the person who built it. Long, and worth every section.
- Davis, Coghlan, Servant and Lee, ["The Impact of Regular Expression Denial of Service in Practice"](https://davisjam.github.io/files/publications/DavisCoghlanServantLee-EcosystemREDOS-ESECFSE18.pdf) (2018). How often the patterns in real packages are super-linear, and what the maintainers did when told. Read it before deciding the tip box does not apply to you.
- The Rust `regex` [test suite](https://github.com/rust-lang/regex/blob/master/testdata/README.md). A TOML corpus run against every engine in the crate, with fuzz targets beside it. The grown-up form of Listing 4-1: one set of cases, every engine, no engine allowed to have its own.
- Çakar, Lee and Davis, ["Towards the Systematic Testing of Regular Expression Engines"](https://arxiv.org/abs/2603.00311) (2026). A survey of how 22 engines are tested and why dialects make differential testing hard. Read it for what this chapter got away with by staying a subset.

## What this book did not cover

`tinyre` matches eight constructs over whatever characters Python hands it, answers yes or no, and agrees with `re` on 10,080 cases. It has no character classes, no anchors, and no Unicode beyond treating each code point as a literal. Its groups capture nothing, and it has no way to say which of two matches it prefers, so the whole question of POSIX versus Perl semantics, leftmost-longest versus leftmost-first, was named here and never implemented. It never builds a DFA, lazy or otherwise. The section of Cox's 2007 article headed "Caching the NFA to build a DFA" is the next thing to read, and the live sets you traced in chapter 3 are the states it caches. Captures come after that, through Cox's 2009 article on the Pike VM, and the exercise is to add saved positions to chapter 3's live states without losing the m+1 bound. If you want the real thing rather than the next step, Gallant's article and the source of Go's `regexp` package are both readable in an afternoon by someone who has built the four files in this book. Both are, at bottom, chapter 3 with a cache in front of it and a decision about what to refuse.
