# Front matter

## Who this book is for

You write regular expressions every week. You have shipped one that hung a
service, or read a post-mortem about someone who did, and you would like to know
why the same pattern that runs in a millisecond on one input runs forever on
another. You are comfortable in Python: functions, recursion, dataclasses,
slicing. You have never taken a course in automata theory and are not going to
take one now.

## Who it is not for

If you want to learn regex *syntax*, this is the wrong book; it uses a subset of
eight constructs and never explains `\b` or lookbehind. If you need a production
engine with Unicode, capture groups and backreferences, this book explains why
those are hard and points you at the engines that do them, but it does not build
them.

## What you will build

A small package, `tinyre`, in four steps. Chapter 1 writes a matcher the way
Rob Pike did, recursively, and measures the cliff it falls off. Chapter 2 parses
patterns into a tree and compiles the tree into a machine. Chapter 3 runs that
machine so that every alternative is explored at once, in time proportional to
the input. Chapter 4 tests it against Python's own engine and says honestly what
was given up.

Every listing in this book was executed before it was published, and every
output block is what the code printed. The badge in each listing's header says
which kind of check it passed:

| Badge | Meaning |
|---|---|
| **verified** | ran, exited 0, and the output shown is the real output |
| **error demo** | ran and failed on purpose; the error shown is the real error |
| **illustrative** | an exercise stub or a fragment; not executable by design |

## How to read it

In order. Each chapter assumes the one before it, and the warm-up questions at
the top of chapters 2 to 4 reach back deliberately. Work the predict-then-reveal
boxes before you open them: the point of them is the moment you commit to an
answer. The exercises climb a ladder from filling one blank to writing something
new; if the last rung is too far, the third is enough.

A term in **bold** is being defined at that point, and every defined term is in
the glossary with the chapter that owns it.
