# Research brief — A Regex Engine From Scratch

**Reader.** A working programmer who writes regexes weekly and has never built an
engine. Knows Python well. Does not know automata theory and does not want a
course in it; wants to understand why `(a+)+b` hangs and how the engines that do
not hang are built.

**Not for.** People who want regex syntax taught, or a production engine.

**Spine project.** `tinyre`: a Python package grown across four chapters.
1. A backtracking matcher for literal, dot, concatenation and star, written
   recursively (in the lineage of Pike's matcher in *The Practice of
   Programming* and Kernighan's *Beautiful Code* chapter), and a demonstration
   of catastrophic backtracking with measured timings.
2. A recursive-descent parser for the teaching subset (adds `+`, `?`, `|`,
   parentheses) to an AST, then compilation to a Thompson NFA of split and
   character states.
3. Simulation of the NFA over the input as a set of states (Thompson 1968; Pike's
   VM; Russ Cox's account), with the linear-time bound demonstrated on the same
   pathological input, and the bug class of cycles through split states.
4. Making it trustworthy: differential testing against Python's `re` on a
   generated corpus, a benchmark done honestly, and what was given up
   (captures, backreferences, lookaround) with where the real engines go next
   (lazy DFA, RE2, Rust regex, Go regexp).

**Depth.** brief: 4 chapters, 1,500–2,200 words each, 4–7 verified listings each.

**Every claim about history, other engines, incidents or performance must carry
a primary-source URL**, recorded at the moment it is read.
