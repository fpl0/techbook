# Research notes: parsing a regex into an AST, and compiling the AST to a Thompson NFA

Scope: the teaching subset (literal, `.`, concatenation, `*`, `+`, `?`, `|`, parentheses). Each claim carries its source inline as `claim — URL — quote/section`. Anything I could not trace to a primary source is prefixed `UNSOURCED:`. Accessed 2026-09-05.

## 1. Grammar and precedence

**Precedence order (lowest to highest): alternation, concatenation, postfix repetition.**

- POSIX ERE precedence table, highest to lowest: collation symbols, escaped characters, bracket expression, grouping `()`, duplication `* + ? {m,n}`, concatenation, anchoring `^ $`, alternation `|`. The spec also states flatly that "concatenation has a higher order of precedence than alternation." — https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap09.html — §9.4.8 "ERE Precedence".
- The POSIX ERE grammar (§9.5.3) already *is* a precedence-stratified grammar: `extended_reg_exp : ERE_branch | extended_reg_exp '|' ERE_branch`; a branch is a sequence of `ERE_expression`s; `ERE_expression : one_char_or_coll_elem_ERE | '^' | '$' | '(' extended_reg_exp ')' | ERE_expression ERE_dupl_symbol`; `ERE_dupl_symbol : '*' | '+' | '?' | '{' ... '}'`. — same URL, §9.5.3.
- Russ Cox states the same order in one sentence: "The operator precedence, from weakest to strongest binding, is first alternation, then concatenation, and finally the repetition operators." — https://swtch.com/~rsc/regexp/regexp1.html — section "Regular Expressions".
- Python `re` docs describe the operators but do not give a precedence table: `A|B` "creates a regular expression that will match either A or B"; `*` "Causes the resulting RE to match 0 or more repetitions of the preceding RE, as many repetitions as are possible"; `+` "1 or more"; `?` "0 or 1"; `.` "In the default mode, this matches any character except a newline"; `(...)` "Matches whatever regular expression is inside the parentheses, and indicates the start and end of a group". — https://docs.python.org/3/library/re.html — "Regular Expression Syntax". Useful for aligning the subset's semantics with `re`, not for citing precedence.

**A clean recursive-descent grammar.** Matt Might's version, which is the one most Python tutorials copy:

```
<regex>  ::= <term> '|' <regex>  |  <term>
<term>   ::= { <factor> }
<factor> ::= <base> { '*' }
<base>   ::= <char>  |  '\' <char>  |  '(' <regex> ')'
```

His gloss: "A regular expression is a term; or a regular expression is a term, a '|' and another regular expression. A term is a possibly empty sequence of factors. A factor is a base followed by a possibly empty sequence of '*'. A base is a character, an escaped character, or a parenthesized regular expression." And on the method: "The core idea in recursive descent is to construct a procedure for each kind of term in the grammar", giving `regex()`, `term()`, `factor()`, `base()`. — https://matt.might.net/articles/parsing-regex-with-recursive-descent/ — whole article. (Note: his `<regex>` rule is right-recursive, so `a|b|c` parses as `a|(b|c)`; harmless for matching. Add `+` and `?` alongside `*` in `<factor>` for the book's subset.)

Cox's own yacc grammar for re1 (his companion code for the VM article) is the same shape, left-recursive: `alt: concat | alt '|' concat`; `concat: repeat | concat repeat`; `repeat: single | single '*' | single '+' | single '?'` (plus non-greedy variants); `single: '(' alt ')' | CHAR | '.'`. — https://raw.githubusercontent.com/rsc/re1/main/parse.y — rules section. Good evidence that "alt → concat → repeat → single" is the canonical four-level layering.

Dragon book §3.7 is cited everywhere for the construction (see §2) but I could not fetch the book text; treat it as a supporting citation for the NFA construction, not for the parser.

## 2. Thompson's construction

**The 1968 paper.** Ken Thompson, "Programming Techniques: Regular expression search algorithm", *Communications of the ACM* 11(6), June 1968, pp. 419–422, doi:10.1145/363347.363387. Abstract, verbatim: "A method for locating specific character strings embedded in character text is described and an implementation of this method in the form of a compiler is discussed. The compiler accepts a regular expression as source language and produces an IBM 7094 program as object language. The object program then accepts the text to be searched as input and produces a signal every time an embedded string in the text matches the given regular expression." — https://www.oilshell.org/archive/Thompson-1968.pdf (mirror of the CACM PDF; ACM DL page https://dl.acm.org/doi/10.1145/363347.363387 was 403 to my fetcher) — p. 419.

What it actually describes:
- Motivation: "Previous search algorithms involve backtracking when a partially successful search path fails. This necessitates a lot of storage and bookkeeping, and executes slowly. In the regular expression recognition technique described in this paper, each character in the text to be searched is examined in sequence against a list of all possible current characters. During this examination a new list of all possible next characters is built." — p. 419, "The Algorithm". He relates this to Brzozowski derivatives in the same paragraph.
- Three-stage compiler: "The first stage is a syntax sieve that allows only syntactically correct regular expressions to pass. This stage also inserts the operator '.' for juxtaposition of regular expressions. The second stage converts the regular expression to reverse Polish form. The third stage is the object code producer." — p. 419, "The Compiler". So the original is *postfix-driven with a stack of operands*, not AST-driven; Cox's C version follows that exactly.
- Two node types: "NNODE matches a single character" and "CNODE will split the current search path." — p. 419–420. These are Cox's `c < 256` state and `Split` state.
- Star is defined by rewriting: "The closure operator is realized with a CNODE by noting the identity X* = λ | X X*". — p. 420.
- The object program is literally a list of `TSX` (transfer) instructions: "In the compiled code, the lists mentioned in the algorithm are not characters, but transfer instructions into the compiled code." The sample third stage "is written in ALGOL-60 and produces object programs in IBM 7094 machine language." — p. 419, 420.
- Origin: "This compile-search algorithm is incorporated as the context search in a time-sharing text editor." — p. 419. Cox identifies the editor as QED on CTSS. — regexp1.html, "History and References".

**Cox's modern presentation.** "Regular Expression Matching Can Be Simple And Fast" (2007). — https://swtch.com/~rsc/regexp/regexp1.html and full source https://swtch.com/~rsc/regexp/nfa.c.txt.

- Historical framing: "Thompson introduced the multiple-state simulation approach in his 1968 paper. In his formulation, the states of the NFA were represented by small machine-code sequences, and the list of possible states was just a sequence of function call instructions. In essence, Thompson compiled the regular expression into clever machine code." And: "R. McNaughton and H. Yamada and Ken Thompson are commonly credited with giving the first constructions to convert regular expressions into NFAs, even though neither paper mentions the then-nascent concept of an NFA." — "Implementation" and "History and References".
- State representation (nfa.c.txt, comment verbatim): "Represents an NFA state plus zero or one or two arrows exiting. if c == Match, no arrows out; matching state. If c == Split, unlabeled arrows to out and out1 (if != NULL). If c < 256, labeled arrow with character c to out." `struct State { int c; State *out; State *out1; int lastlist; };` with `enum { Match = 256, Split = 257 };`.
- Fragments: "The partial NFAs have no matching states: instead they have one or more dangling arrows, pointing to nothing. The construction process will finish by connecting these arrows to a matching state." `struct Frag { State *start; Ptrlist *out; };` — "Start points at the start state for the fragment, and out is a list of pointers to State* pointers that are not yet connected to anything." Helpers: "List1 creates a new pointer list containing the single pointer outp. Append concatenates two pointer lists, returning the result. Patch connects the dangling arrows in the pointer list l to the state s: it sets *outp = s for each pointer outp in l." — regexp1.html, "Implementation".
- Per-operator constructions, from `post2nfa` (nfa.c.txt), verbatim:

```c
default:              s = state(*p, NULL, NULL);
                      push(frag(s, list1(&s->out)));
case '.': /* catenate */ e2 = pop(); e1 = pop();
                      patch(e1.out, e2.start);
                      push(frag(e1.start, e2.out));
case '|': /* alternate */ e2 = pop(); e1 = pop();
                      s = state(Split, e1.start, e2.start);
                      push(frag(s, append(e1.out, e2.out)));
case '?': /* zero or one */ e = pop();
                      s = state(Split, e.start, NULL);
                      push(frag(s, append(e.out, list1(&s->out1))));
case '*': /* zero or more */ e = pop();
                      s = state(Split, e.start, NULL);
                      patch(e.out, s);
                      push(frag(s, list1(&s->out1)));
case '+': /* one or more */ e = pop();
                      s = state(Split, e.start, NULL);
                      patch(e.out, s);
                      push(frag(e.start, list1(&s->out1)));
```
  Finally `patch(e.out, &matchstate); return e.start;`. Prose versions: concatenation "connects the final arrow of the e1 machine to the start of the e2 machine"; alternation "adds a new start state with a choice of either the e1 machine or the e2 machine"; `e?` "alternates the e machine with an empty path"; `e*` "uses the same alternation but loops a matching e machine back to the start"; `e+` "also creates a loop, but one that requires passing through e at least once."

**Size bound, exact quotes.** "Counting the new states in the diagrams above, we can see that this technique creates exactly one state per character or metacharacter in the regular expression, excluding parentheses. Therefore the number of states in the final NFA is at most equal to the length of the original regular expression." — regexp1.html, "Converting Regular Expressions to NFAs". Why: each literal makes one state; `|`, `?`, `*`, `+` each make exactly one `Split`; concatenation and parentheses make none. Consequence for matching: "For a regular expression of length m run on text of length n, the Thompson NFA requires O(mn) time." — regexp1.html, "Performance".

Textbook form of the bound (the Dragon book's construction adds a fresh start and accept state per operator, so its constant is 2): "N(r) has at most twice as many states as there are operators and operands in r. This bound follows from the fact that each step of the algorithm creates at most two new states." — quoted from a lecture scribe transcript of the Dragon book's §3.7.4, https://cse.iitkgp.ac.in/~bivasm/notes/scribe/11CS10055.pdf, p. 3; Wikipedia cites the same material to Aho, Lam, Sethi, Ullman, *Compilers* 2nd ed. (2007), pp. 159–163 — https://en.wikipedia.org/wiki/Thompson%27s_construction. I did not verify against the book itself. Wikipedia's own statement: "the number of states of A is 2s − c (linear in the size of E)" with s = symbols and c = concatenations, and "The number of transitions leaving any state is at most two."

Thompson's paper also states a list-size bound, in machine-code terms: "The maximum number of entries that can be in CLIST is the number of TSX CNODE,4 and TSX NNODE,4 instructions compiled. The maximum number of entries in NLIST is just the number of TSX NNODE,4 instructions compiled." — Thompson-1968.pdf, p. 422, "Notes".

## 3. The continuation-passing variant (compile with "what comes next")

Idea: `compile(node, next) -> start_state`; each node is built knowing the state it must flow into, so no dangling pointers and no `patch()`. Star needs a cycle, so its `Split` is allocated first and its body is compiled with `next = split`.

Published descriptions:
- **Jules Jacobs, "From regex to NFA and back" (note, 29 April 2021)** gives the two-endpoint form `addRe(i, j, re)`: "we define a recursive function addRe(i,j,r) that adds r to the NFA while only inserting edges with characters or ε on them." Verbatim cases: `Seq(a,b)`: `val mid = fresh(); addRe(i,mid,a); addRe(mid,j,b)`; `Alt(a,b)`: `addRe(i,j,a); addRe(i,j,b)`; `Star(a)`: `val mid = fresh(); add(i,mid,Eps); add(mid,j,Eps); addRe(mid,mid,a)`. He argues "The NFAs produced by this construction are more compact than those produced by Thompson's construction. Thompson's construction results in strictly more nodes and more ε-transitions." — https://julesjacobs.com/notes/nfa/nfa.pdf — §4 "How to implement regex to NFA conversion", §6. This is the cleanest citable source for "pass the target state in instead of patching". (He uses a `Star` rule with an extra middle node; his exercise "What can go wrong if we use this rule instead? ... Hint: consider a* + b*" is the same nullable-loop trap RE2 handles in §5.)
- **Cox's re1 `compile.c`** (companion to the 2009 VM article) is the sequential-emission form: `emit(r)` writes instructions into a flat array in order, so "what comes next" is simply the next instruction emitted, and only backward/forward jump targets are filled in after the sub-emit (`p1->y = pc` after `emit(r->left)`). — https://raw.githubusercontent.com/rsc/re1/main/compile.c — `emit()`; the article's rules read the same way: `e*` → `L1: split L2, L3; L2: codes for e; jmp L1; L3:`. — https://swtch.com/~rsc/regexp/regexp2.html — "Regular Expression Virtual Machines". The article itself does not name this a continuation.
- **Kyashif's JS engine** builds each fragment with explicit `start` and `end` state objects rather than a pointer list, which removes `patch()` at the cost of one extra ε-state per fragment. — https://deniskyashif.com/2019/02/17/implementing-a-regular-expression-engine/.

UNSOURCED: I found no publication that names the `compile(node, next)` single-continuation form "continuation-passing" in the Thompson-NFA setting. The CPS literature on regex (Danvy & Nielsen, "Defunctionalization at Work", BRICS RS-01-23, 2001, https://www.brics.dk/RS/01/23/BRICS-RS-01-23.pdf; Harper's matcher) is about *matchers* with a continuation over the remaining input, not about NFA construction. Cite Jacobs for the technique and describe the name as the book's own.

## 4. Nystrom on recursive descent (style reference)

From *Crafting Interpreters*, ch. "Parsing Expressions" — https://craftinginterpreters.com/parsing-expressions.html:
- "Recursive descent is the simplest way to build a parser, and doesn't require using complex parser generator tools like Yacc, Bison or ANTLR."
- "Don't be fooled by its simplicity, though. Recursive descent parsers are fast, robust, and can support sophisticated error handling. In fact, GCC, V8 (the JavaScript VM in Chrome), Roslyn (the C# compiler written in C#) and many other heavyweight production language implementations use recursive descent."
- "Recursive descent is considered a top-down parser because it starts from the top or outermost grammar rule and works its way down into nested subexpressions."
- On encoding precedence as one rule per level: "Each rule here only matches expressions at its precedence level or higher." And the mechanical translation: "Each rule becomes a function."

## 5. The epsilon-cycle hazard

`(a*)*` or `a**` produces a Split whose ε-edges lead back to itself without consuming input; a naive closure walk loops forever.

- **Thompson saw it in 1968**, verbatim: "Code compiled for a** will go into a loop due to the closure operator on an operand containing the null regular expression, λ. There are two ways out of this problem. The first is to not allow such an expression to get through the syntax sieve. In most practical applications, this would not be a serious restriction. The second way out is to recognize lambda separately in operands and remember the CODE location of the recognition of lambda. ... Thus a** is compiled as λ|aa*(aa*)*." — Thompson-1968.pdf, p. 421–422, "Notes". He also introduces dedup of list entries there: "Such redundant searches can be easily terminated by having NNODE (CNODE) search NLIST (CLIST) for a matching entry before it puts an entry in the list. This now gives a maximum size on the number of entries that can be in the lists." — p. 422.
- **Cox's generation marker** (the "visited set per step" done in O(1)): "Addstate adds a state to the list, but not if it is already on the list. Scanning the entire list for each add would be inefficient; instead the variable listid acts as a list generation number. When addstate adds s to a list, it records listid in s->lastlist. If the two are already equal, then s is already on the list being built. Addstate also follows unlabeled arrows: if s is a Split state with two unlabeled arrows to new states, addstate adds those states to the list instead of s." Code: `if(s == NULL || s->lastlist == listid) return; s->lastlist = listid; if(s->c == Split){ addstate(l, s->out); addstate(l, s->out1); return; }`. `startlist` and `step` each do `listid++`. — regexp1.html, "Implementation" / nfa.c.txt. Because the check happens before recursion, an ε-cycle terminates on its second visit.
- Same idea in the VM article and code: "If addthread does not add a thread to the list if an identical thread (with the same pc) is already on the list, then ThreadLists only need room for n possible threads". — regexp2.html, "Thompson's Implementation". re1's `pike.c`: `if(t.pc->gen == gen) { decref(t.sub); return; /* already on list */ } t.pc->gen = gen;` then recurse on `Jmp`/`Split`/`Save`. — https://raw.githubusercontent.com/rsc/re1/main/pike.c — `addthread`.
- **Visited-set form** (what a Python chapter will likely write): Kyashif: "We also have to mark the ε-transition states as visited to prevent infinite looping." — deniskyashif.com (above). abstractsyntaxseed.com keeps an `EPSILON_VISITED` list reset after each consumed character: "transversing an epsilon loop is useless. The machine can't differenciate between a state that has gone through no epsilon loops and the same state that has gone through a thousand loops." — https://www.abstractsyntaxseed.com/blog/regex-engine/implementing-a-nfa (JS, 2022-02-03).
- **Priority-correctness angle (beyond the teaching subset, but worth a footnote)**: RE2 rewrites star-of-nullable at compile time: "When the subexpression is nullable, one Alt isn't enough to guarantee correct priority ordering within the transitive closure. The simplest solution is to handle it as (a+)? instead, which adds the second Alt." `if (a.nullable) return Quest(Plus(a, nongreedy), nongreedy);` — https://raw.githubusercontent.com/google/re2/main/re2/compile.cc — `Compiler::Star`. Backtracking engines face the same input as a termination problem; JavaScript's spec forbids empty optional iterations: "In JavaScript, optional repetitions of a quantifier cannot match the empty string. This prevents the backtracking implementation from executing an infinite loop when matching a nullable star". — Barrière & Pit-Claudel, "Linear Matching of JavaScript Regular Expressions", PACMPL 8 (PLDI 2024), https://arxiv.org/pdf/2311.17620, §2.

## 6. Teaching implementations of Thompson's construction in Python

- **xysun/regex** — https://github.com/xysun/regex, write-up https://xysun.github.io/posts/regex-parsing-thompsons-algorithm.html (2014-05-18). Recursive-descent parser (Might's grammar) emitting postfix, stack of NFA fragments, `State` objects with `epsilon` list and `transitions` dict, two-set simulation with an `addstate` closure. Closest existing Python analogue of Cox's C; benchmarks against `re` on `a?^n a^n`.
- **nitely's `re3.py` gist** — https://gist.github.com/nitely/d04b725f4dca1dd49d7ab43a40f6b44b (MIT, ~250 lines). Shunting-yard to RPN, then Thompson NFA with a `visited` set in closure computation. Explicitly "based on Thompson's paper".
- **Rosetta Code, McNaughton-Yamada-Thompson algorithm, Python entry** — https://rosettacode.org/wiki/McNaughton-Yamada-Thompson_algorithm. Shunting-yard `shunt()` with precedence table `{'*':60,'+':55,'?':50,'.':40,'|':20}`, `State(label, edge1, edge2)`, `NFA(initial, accept)` pairs; `followes()` closure uses a set. Textbook two-endpoint form (no patch list).
- **Every Algorithm, "Thompson's Construction Algorithm"** (2024-01-25) — https://every-algorithm.github.io/2024/01/25/thompsons_construction_algorithm.html. Python (postfix, stack) and Java (recursive descent, infix) side by side; states the bound "The resulting NFA contains at most 2n+2 states, where n is the number of symbols in the expression".
- **GraceKeane/thompsons-construction** — https://github.com/GraceKeane/thompsons-construction (and sibling student repos kevinniland/, niemaattarian/Thompsons-Construction-on-NFAs). Short course-project Python: `shunt`, `compile`, `followes`, `match`. Fine as "look how small this is", not as reference code.
- Non-Python but worth pointing at: Denis Kyashif (JS, 2019) above; sh4dy, "Building a regex engine" (2025-05-01) — https://sh4dy.com/2025/05/01/regex_engine/ (fetch blocked; search snippet says it covers McNaughton-Yamada-Thompson and "exactly one accepting state"); MaxGCoding "AST to NFA" (C++, 2024-10-15) — https://www.maxgcoding.com/ast-to-nfa, compiles from an AST by post-order recursion; Andrew Gallant, "Regex engine internals as a library" (2023-07-05) — https://burntsushi.net/regex-internals/, "Thompson's construction builds an NFA from a structured representation of a regex in O(m) time" and a good discussion of why ε-transitions are the cost center.

## Sources

- Ken Thompson, "Programming Techniques: Regular expression search algorithm", CACM 11(6), 1968, doi:10.1145/363347.363387 — PDF mirror https://www.oilshell.org/archive/Thompson-1968.pdf (accessed 2026-09-05; ACM page https://dl.acm.org/doi/10.1145/363347.363387 returned 403)
- Russ Cox, "Regular Expression Matching Can Be Simple And Fast" (2007) — https://swtch.com/~rsc/regexp/regexp1.html (2026-09-05)
- Russ Cox, nfa.c source — https://swtch.com/~rsc/regexp/nfa.c.txt (2026-09-05)
- Russ Cox, "Regular Expression Matching: the Virtual Machine Approach" (2009) — https://swtch.com/~rsc/regexp/regexp2.html (2026-09-05)
- Russ Cox, re1 sources: parse.y, compile.c, pike.c, thompson.c — https://github.com/rsc/re1 (2026-09-05)
- POSIX.1-2017 Base Definitions ch. 9, Regular Expressions — https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap09.html (2026-09-05)
- Python 3 `re` module docs — https://docs.python.org/3/library/re.html (2026-09-05)
- Matt Might, "Parsing regular expressions with recursive descent" — https://matt.might.net/articles/parsing-regex-with-recursive-descent/ (2026-09-05)
- Bob Nystrom, *Crafting Interpreters*, "Parsing Expressions" — https://craftinginterpreters.com/parsing-expressions.html (2026-09-05)
- Wikipedia, "Thompson's construction" — https://en.wikipedia.org/wiki/Thompson%27s_construction (2026-09-05)
- Y. Manoj Kumar, "Thompson Construction" scribe notes (transcribes Dragon book §3.7.4) — https://cse.iitkgp.ac.in/~bivasm/notes/scribe/11CS10055.pdf (2026-09-05)
- Jules Jacobs, "From regex to NFA and back" (2021-04-29) — https://julesjacobs.com/notes/nfa/nfa.pdf (2026-09-05)
- Olivier Danvy and Lasse R. Nielsen, "Defunctionalization at Work", BRICS RS-01-23 (2001) — https://www.brics.dk/RS/01/23/BRICS-RS-01-23.pdf (2026-09-05; cited only to note it is about matchers, not construction)
- Google RE2, compile.cc — https://raw.githubusercontent.com/google/re2/main/re2/compile.cc (2026-09-05)
- Aurèle Barrière and Clément Pit-Claudel, "Linear Matching of JavaScript Regular Expressions", PLDI 2024 — https://arxiv.org/pdf/2311.17620 (2026-09-05)
- Denis Kyashif, "Implementing a Regular Expression Engine" (2019-02-17) — https://deniskyashif.com/2019/02/17/implementing-a-regular-expression-engine/ (2026-09-05)
- abstractsyntaxseed.com, "Implementing a NFA — Building a Regex Engine Part 2" (2022-02-03) — https://www.abstractsyntaxseed.com/blog/regex-engine/implementing-a-nfa (2026-09-05)
- Andrew Gallant, "Regex engine internals as a library" (2023-07-05) — https://burntsushi.net/regex-internals/ (2026-09-05)
- xysun, "Regex parsing: Thompson's algorithm" (2014-05-18) — https://xysun.github.io/posts/regex-parsing-thompsons-algorithm.html and https://github.com/xysun/regex (2026-09-05)
- nitely, re3.py gist — https://gist.github.com/nitely/d04b725f4dca1dd49d7ab43a40f6b44b (2026-09-05)
- Rosetta Code, "McNaughton-Yamada-Thompson algorithm" — https://rosettacode.org/wiki/McNaughton-Yamada-Thompson_algorithm (2026-09-05)
- Every Algorithm, "Thompson's Construction Algorithm" (2024-01-25) — https://every-algorithm.github.io/2024/01/25/thompsons_construction_algorithm.html (2026-09-05)
- GraceKeane/thompsons-construction — https://github.com/GraceKeane/thompsons-construction (2026-09-05)
- sh4dy, "Building a regex engine" (2025-05-01) — https://sh4dy.com/2025/05/01/regex_engine/ (2026-09-05; fetch blocked, search snippet only)
- MaxGCoding, "Implementing Thompsons Construction: Building NFA from Regular Expressions" (2024-10-15) — https://www.maxgcoding.com/ast-to-nfa (2026-09-05)
- Dmitry Soshnikov, "Automata Theory: inside a RegExp machine" course page — https://dmitrysoshnikov.com/courses/automata-theory-building-a-regexp-machine/ (2026-09-05; lecture 11 is titled around "avoid infinite loops!" on ε-transitions; Medium articles were 403)
