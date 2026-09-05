# Chapter 1: Shapes of a Chapter

<span class="newthought">Every chapter</span> opens with a concrete problem, not a
promise about what the chapter will cover. This one opens with a broken program.

<div class="orient">
<h3>What you'll learn</h3>
<ul>
<li>Read a fenced block's contract and know whether its output was verified</li>
<li>Tell a sidenote from a callout, and know when each earns its place</li>
<li>Predict what a snippet prints before running it</li>
</ul>
<h3>Assumes you know</h3>
<p>Basic Python syntax. Nothing else.</p>
<p class="meta">~20 min · 4 exercises</p>
</div>

## The problem

Here is a function that looks right and is wrong.<label for="sn-1" class="margin-toggle sidenote-number"></label>
<input type="checkbox" id="sn-1" class="margin-toggle">
<span class="sidenote">The bug is subtle enough that it survived code review twice in
the original codebase this is drawn from.</span>

```python run env=ch1 file=code/average.py caption="A first attempt at a running average." highlight=3
def average(values):
    total = sum(values)
    return total / len(values)

print(average([1, 2, 3, 4]))
```

```output
2.5
```

That works. Now watch what happens on the empty list.

```python expect-error expect="ZeroDivisionError"
def average(values):
    return sum(values) / len(values)

average([])
```

<div class="callout">
<div class="title">This trips people up</div>
<p>An empty sequence is not an error in <code>sum</code> — it returns <code>0</code>
quite happily. The failure surfaces one operation later, in the division, which is
why the traceback points somewhere the reader did not expect.</p>
</div>

<details>
<summary>Predict: what does <code>average([2])</code> return — <code>2</code> or <code>2.0</code>?</summary>

<p><code>2.0</code>. True division always produces a float in Python 3, even when the
operands divide evenly. This matters the moment you compare the result to an integer
with <code>is</code> rather than <code>==</code>.</p>

</details>

## A mental model

<figure>
<svg viewBox="0 0 640 150" role="img" aria-labelledby="dia1-t">
  <title id="dia1-t">Values flow into sum, then into division by the count</title>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--dia-muted)"/>
    </marker>
  </defs>
  <g fill="var(--dia-fill)" stroke="var(--dia-fg)" stroke-width="1.5">
    <rect x="16" y="48" width="128" height="52" rx="4"/>
    <rect x="256" y="48" width="128" height="52" rx="4"/>
    <rect x="496" y="48" width="128" height="52" rx="4"/>
  </g>
  <g font-family="var(--font-ui)" font-size="14" fill="var(--dia-fg)" text-anchor="middle">
    <text x="80" y="79">values</text>
    <text x="320" y="79">sum()</text>
    <text x="560" y="79">/ len()</text>
  </g>
  <g stroke="var(--dia-muted)" stroke-width="1.5" marker-end="url(#arrow)" fill="none">
    <path d="M 148 74 L 250 74"/>
    <path d="M 388 74 L 490 74"/>
  </g>
</svg>
<figcaption>Figure 1-1. The count is read separately from the sum, so an empty input
only fails at the second step.</figcaption>
</figure>

| Input | `sum` | `len` | Result |
|-------|------:|------:|--------|
| `[1,2,3,4]` | 10 | 4 | `2.5` |
| `[2]` | 2 | 1 | `2.0` |
| `[]` | 0 | 0 | raises |

## Practice

<div class="exercises">
<div class="exercise">
<span class="label">Exercise</span>
<p>Fill the single blank so the function returns <code>None</code> for empty input.</p>

```python literal why="an exercise stub the reader completes; it is intentionally incomplete"
def average(values):
    if ____:
        return None
    return sum(values) / len(values)
```

<details><summary>Solution</summary>
<p><code>not values</code>. Prefer it over <code>len(values) == 0</code>: it reads as
the question being asked, and it works for any sequence.</p>
</details>
</div>

<div class="exercise">
<span class="label">Exercise</span>
<p>Now write it from scratch, raising <code>ValueError</code> instead.</p>
</div>
</div>

## What to remember

- `sum` of an empty sequence is `0`, not an error
- Errors often surface one step after the operation that caused them
- Nested lists work too:
  - like this
  - and this
