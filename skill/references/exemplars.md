# What the best technical books actually do

The house style says how a sentence should read. This says how a *book* is built,
drawn from the books working programmers keep recommending to each other twenty
years on. Each entry names the book, the device, and the rule it becomes here.
Writers read this before drafting; the rubric's dimensions come from it.

## Contents

- [The devices, and where they come from](#the-devices-and-where-they-come-from)
- [Rules for the writer](#rules-for-the-writer)
- [Anti-patterns the same books warn about](#anti-patterns-the-same-books-warn-about)
- [Sources](#sources)

## The devices, and where they come from

### Every line of code is in the book, and it was written before the prose

*Crafting Interpreters* (Nystrom). "If you type in all of the code in the book, you
get two complete, working interpreters. No tricks." Nystrom built both interpreters
first, then sliced them into chapters with a build script that extracted snippets
from the real source files, and a test suite that tracked which tests should pass by
which chapter. Prose came last, chapter by chapter: outline, draft, edit, then
**read aloud for cadence**.

*Writing an Interpreter in Go* (Ball) is praised for the same reason: "from 0 lines
of code to a fully working interpreter, step by step, with all code shown," no
third-party libraries, every step covered by a test the reader can run.

**Rule here:** the chapter's code exists and runs under `verify.py` *before* a
paragraph of prose is written about it. Listings are `file=`-backed. The reader can
type in the book and get the spine project.

### Say where the code goes

*Crafting Interpreters* marks every snippet with a location: "*lox/Scanner.java*,
add after *scanToken()*", "create new file", "replace 3 lines". *The Rust Book*
prefixes every listing with `Filename: src/main.rs` and numbers it "Listing 12-4",
then refers to it by number in the prose.

**Rule here:** a listing that modifies an existing file says so in the sentence
before it. Prose refers to listings by number, never "the code above".

### State the crux before solving it

*Operating Systems: Three Easy Pieces* (Arpaci-Dusseau). "Anytime we are trying to
solve a problem, we first try to state what the most important issue is; such a crux
of the problem is explicitly called out in the text." Their other devices: **timelines**
("we'll explain how a system works by showing its behavior over time"), **asides**
(relevant but not essential) kept distinct from **tips** (general lessons that
transfer), and real code rather than pseudocode: "for virtually all examples, you
should be able to type them up yourself and run them."

**Rule here:** each chapter has one crux box, stated as a problem, before the first
listing that attacks it. When behaviour unfolds in time (a scheduler, a network
round-trip, a GC cycle), draw the timeline; do not narrate it.

### Show the machine's real output, including the failures

*The Rust Book* pastes compiler output verbatim, build lines included, and teaches
by reading the error with the reader. *Fluent Python* (Ramalho) writes its examples
as doctests so "you can verify the correctness of most of the code in the book by
typing `python3 -m doctest`". Kernighan's editorial rule, from the Lua and Qt
documentation teams, runs the other way: if you cannot explain a feature cleanly,
the feature is wrong.

**Rule here:** every `output` block is captured, never typed. Every error the book
warns about is an `expect-error` block showing the real message. If a listing is hard
to explain, change the listing, not the explanation.

### A pearl grows from an irritant

*Programming Pearls* (Bentley). Each column: a real problem someone brought him, the
first solution, the better solutions, the **principles** extracted, then problems for
the reader and annotated further reading. The order is fixed: irritant, attempt,
insight, principle. Never principle first.

*Eloquent JavaScript* (Haverbeke) does the same at sentence scale: a purpose
statement before each example saying what to look for, and it admits difficulty
where it exists: "Thinking about programs like this takes some practice."

**Rule here:** the concrete case opens, the principle closes. The sentence before a
listing tells the reader what to watch for in it. A hard thing is called hard.

### An opinionated aside, and an annotated reading list

*Fluent Python* ends every chapter with a **Soapbox**, "an entertaining, informative,
and opinionated aside," and a **Further Reading** where each reference gets a
sentence on what it adds. *Crafting Interpreters* ends with **Challenges** and a
**Design Note** on a decision the language could have made differently. *Designing
Data-Intensive Applications* (Kleppmann) closes each chapter with a summary of what
is now true and a reference list that runs to dozens of primary sources.

**Rule here:** the going-deeper section is annotated: each source gets one sentence
on why it is there. One opinion per chapter is owned outright, in the author's voice,
and marked as opinion.

### Make the history legible

OSTEP again: "One of our goals in writing this book is to make the paths of history
as clear as possible... seeing how the sausage was made is nearly as important as
understanding what the sausage is good for." DDIA reads "as if a smart colleague is
filling you in on the fundamentals as well as the intricacies of their field."

**Rule here:** when an idea has an origin, name it, date it, and cite it. Thompson
1968 is a citation; "the classic approach" is not.

### One idea per page

Julia Evans (*Wizard Zines*) spends hours on each page "making sure that every single
one explains one or two important ideas as succinctly and clearly as possible," and
picks fundamentals "that haven't changed much in the last 10 years." Her drafts go to
readers, and the confusing pages get redrawn.

**Rule here:** one idea per section. If a section teaches two, split it. Prefer the
part of the topic that will still be true in ten years.

### Chesterton's fences

Bendersky's critique of *Crafting Interpreters*: early code carries "subtle
provisions for the future," which "perplex readers implementing in alternative
languages." The one recurring complaint about an otherwise faultless book.

**Rule here:** if a listing contains something the current chapter does not need,
say in one sentence which chapter needs it. Never leave a fence unexplained.

## Rules for the writer

In the order they bite during drafting:

1. **Code first.** Write and run the chapter's code, `file=`-backed, before prose.
2. **Crux box** before the first listing that attacks the problem.
3. **Purpose sentence** before each listing; **why** after it, never what.
4. **Location hint** for any listing that edits an existing file.
5. **Refer to listings by number.**
6. **Real output, real errors.** No typed output blocks. Every warned-about failure is an `expect-error` block.
7. **Timeline diagrams** for anything that happens over time.
8. **Explain every fence.** Code the chapter does not need yet is named as such.
9. **Own one opinion** per chapter, in first person, labelled.
10. **Annotate further reading.** One sentence per source.
11. **Cite origins.** Who, when, where.
12. **Read it aloud** before handing it to the editor. Where you stumble, the reader will.

## Anti-patterns the same books warn about

- **"How" without "why".** King's critique of K&R: it teaches how, and readers who need why go elsewhere. Every mechanism gets its reason.
- **Pseudocode.** OSTEP refuses it; so does this skill. If it cannot run, tag it `literal` with a `why` and expect the reviewer to ask.
- **A reference list with no annotations.** A wall of citations is a place to get lost, not a path.
- **Humour that does not teach.** OSTEP's dialogues review material; Nystrom's asides anticipate a confusion. A joke that carries no content is cut.
- **Hiding difficulty.** A book that makes everything look easy fails the first reader who finds it hard, and they conclude the fault is theirs.

## Sources

- Nystrom, *Crafting "Crafting Interpreters"*, 2020. <https://journal.stuffwithstuff.com/2020/04/05/crafting-crafting-interpreters/>
- Nystrom, *Crafting Interpreters*, ch. 4 "Scanning". <https://craftinginterpreters.com/scanning.html>
- Bendersky, review of *Crafting Interpreters*, 2022. <https://eli.thegreenplace.net/2022/book-review-crafting-interpreters-by-robert-nystrom/>
- Arpaci-Dusseau, *Operating Systems: Three Easy Pieces*, preface. <https://pages.cs.wisc.edu/~remzi/OSTEP/preface.pdf>
- Ball, *Writing an Interpreter in Go*. <https://interpreterbook.com/>
- Klabnik & Nichols, *The Rust Programming Language*, ch. 12.2. <https://doc.rust-lang.org/book/ch12-02-reading-a-file.html>
- Haverbeke, *Eloquent JavaScript*, ch. 3. <https://eloquentjavascript.net/03_functions.html>
- Ramalho, *Fluent Python*, 2nd ed., preface (Soapbox, Further Reading, doctest).
- Bentley, *Programming Pearls*, 2nd ed., preface (column structure).
- Evans, *Wizard Zines*. <https://jvns.ca/>
- "Ask HN: What are some of the best written programming books?" <https://news.ycombinator.com/item?id=9757609>
- alexwlchan, *Doing my own syntax highlighting*, 2025 (restrained highlighting). <https://alexwlchan.net/2025/syntax-highlighting/>
