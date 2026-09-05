# The block contract

Every fenced block in a techbook declares what it is and how it should be checked.
`verify.py` enforces this before anything runs, and **an undeclared code block is a
hard error** — not a silent skip.

The reason for the strictness: `mdbook test` silently *tests* untagged blocks and
`mdx` silently *skips* them, and in both cases the author cannot tell by looking at
the page which examples were actually checked. A reader of this book can, because
every listing renders with its verification status in its caption.

## Modes — exactly one per block

| Mode | Use for | Passes when |
|---|---|---|
| `run` | the default: code the reader could paste and execute | exits 0, **and** its real output matches the ` ```output ` block that follows, if there is one |
| `check` | code that must compile or parse but has nothing to print | the toolchain exits 0 |
| `expect-error` | a deliberate error demonstration | it **fails**, and if `expect="…"` is given, that text appears in stderr |
| `norun` | real code that genuinely cannot run here | always reported as unverified, with its reason, in the publish report |
| `literal` | not executable code at all: pseudocode, a config fragment, an exercise stub, a diagram | never executed, never linted |

`literal` and `norun` both require `why="…"`. Without that requirement `literal`
becomes the place unverified code goes to hide, which defeats the whole gate.

**Never tag an error demonstration `literal` or `norun`.** "This must fail" is an
assertion, and a valuable one — it catches the case where a language change makes
your cautionary example silently start working. `expect-error` keeps that guarantee.

## Modifiers

| Modifier | Meaning |
|---|---|
| `env=NAME` | share a session with every earlier `run` block having the same `env`, across the whole book in chapter order (python, node and bash only) |
| `file=path` | the listing **is** that file: `verify.py` requires `code/…` to exist and match the block exactly (`--sync-code` writes it). `code/` is on the import path when blocks run, so a later listing can `import` an earlier file the way a reader's copy would |
| `caption="…"` | the listing caption, rendered under the code |
| `highlight=3,7-9` | lines to emphasise |
| `expect="…"` | for `expect-error`: substring that must appear in stderr |
| `timeout=N` | seconds; default 30 |
| `net` | permit network egress. Off by default; the sandbox denies it otherwise |
| `slow` | excluded from the fast pass |
| `nondet=output` | run it, diff it, but never propose a correction |
| `nondet=command` | do not run at all unless `VERIFY_NONDET=1` |
| `why="…"` | required on `literal` and `norun` |

### `env` is what makes a chapter read as a narrative

A book's listings are usually one continuous session: chapter 3 defines a function
that chapter 5 calls. Without `env`, every block is executed in isolation and the
second one fails on a name it should have.

````markdown literal why="shows the markdown an author writes, so it must not execute"
```python run env=scanner
def tokenize(src):
    return src.split()
```

Now we can use it.

```python run env=scanner
print(tokenize("a b c"))
```

```output
['a', 'b', 'c']
```
````

Only `run` blocks join the prefix. `check` never executed, and `expect-error`
deliberately blew up, so neither leaves state behind.

## Output blocks

A ` ```output ` fence immediately after a `run` or `expect-error` block is the
expected output, and it is the assertion. This is the doctest idea: the output shown
to the reader *is* the test oracle.

Do not write output by hand and hope. Write the block, run `verify.py`, and let it
tell you what the code actually prints. If what it prints differs from what the book
claims, that is a finding, and it is exactly the finding this system exists to
surface.

### Drift, and why nothing is edited in place

When real output differs from the book, `verify.py` writes
`src/chNN-name.md.corrected` and prints a diff. It never rewrites your chapter.
Accepting the change is a separate, deliberate step:

```bash literal why="operator commands, run by a human against a real book directory"
python3 scripts/verify.py ./my-book            # see the diff
python3 scripts/verify.py ./my-book --promote  # accept the corrections
```

Before promoting, ask whether the difference is *information* or *noise*. A changed
number is information — the example may be wrong. A changed timestamp or temp path is
noise, and the fix is a normaliser, not a promoted literal.

## Non-determinism

Three escalating tools, in order of preference:

1. **Normalise it.** `verify.py` already rewrites timestamps, temp paths, hex addresses, durations, and ANSI codes before diffing. Most non-determinism disappears here.
2. **`nondet=output`.** The block runs and must still exit 0, but its output is never diffed and never auto-corrected. Use when the output is genuinely unstable but running it still proves something.
3. **`nondet=command`.** The block does not run at all under a normal pass. Use only when running it is actively harmful or impossible — it mutates shared state, costs money, or takes twenty minutes.

### The hazard normalisation creates

Normalisation is what makes a diff stable, and it is also a hole. Once durations
normalise to `<DUR>`, **any** timing in the book compares equal to any other, so a
hand-invented number passes the gate exactly as a measured one does. The same is true
of timestamps and addresses.

So: never write a timing, a date, or an address by hand. Run the block, read what it
printed, and paste that. `verify.py` will not catch you here, and a benchmark table
that was never measured is worse than no table — it is a claim the book cannot support
and the reader cannot check.

Prose *about* those numbers is unprotected too. If the text says "ten times the input
costs ten times the work", compute the ratio from the real output before writing the
sentence. Numbers cited from another chapter get the same treatment.

A block that fails intermittently is re-run three times before it is declared broken.
If the results differ, `verify.py` refuses to pass it and asks you to choose. It will
not silently tag it for you, because an auto-applied `nondet` is how a real bug gets
buried.

## Dependencies

Every import is resolved against a pinned manifest **before** anything executes:

- Python: `verify/python/pyproject.toml`
- Node: `verify/node/package.json`

An import that is neither in the standard library nor pinned is a hard failure.

This is not bureaucracy. Around a fifth of package names suggested by language models
do not exist, the fabrications recur across runs, and attackers register the popular
ones. A generated book is exactly the threat model. So the gate resolves names
offline and never installs to find out — because installing to find out *is* the
attack.

If a package is real and the book needs it, add it to the manifest deliberately. That
edit is the human decision the gate is asking for.

## Sandbox

Blocks execute under `sandbox-exec` with writes confined to the book's
`.verify/work/` and **network denied**. A block that needs the network must say `net`.

If a block fails with `SANDBOX-DENIED`, the fix is to tag that block `net` — never to
loosen the profile for everything.

Language environments are materialised *outside* the sandbox and only the interpreter
runs inside it. This is deliberate: `uv run` panics under a minimal seatbelt profile
(astral-sh/uv#16664), and pre-creating the environment sidesteps it entirely.

## What to do when a block fails

Ordered cheapest first. The rule underneath all of them: **never downgrade a failure
to a skip.**

1. **Output drift only** — code ran fine, printed something else. Read the diff. If it is a timestamp or a path, add a normaliser. If it is a real value, the example was wrong; that is the system working.
2. **Genuine bug in the example** — fix the code, not the tag. This is the entire point.
3. **Environment or dependency failure** — a `verify/` problem, not a book problem. Pin the dependency.
4. **Flaky** — choose a normaliser or `nondet=output`, with a written reason.
5. **`SANDBOX-DENIED`** — add `net` to that block if the network is genuinely needed.
6. **Genuinely cannot run here** — `norun why="…"`. It will appear in the publish report with your reason attached, so the skip stays visible rather than quietly passing.
