# Diagram kit

Every chapter earns at least one diagram. People learn better from words and pictures
than from words alone, and a diagram is the only part of a technical book that shows
*structure* rather than describing it.

Diagrams are **hand-authored inline SVG**, constrained to the primitives below.

## Why inline SVG and not Mermaid

Mermaid needs a megabyte of JavaScript from a CDN at read time, which breaks offline
reading, prints unreliably, and needs its own dark-mode configuration. D2, Graphviz
and PlantUML all need a binary or a runtime that a fresh machine will not have.

Inline SVG has none of those problems: it themes with CSS variables, prints
perfectly, is diffable in git, needs no JavaScript, and works with the network off.
The cost is that you lay it out yourself — which, at the four-to-eight-box scale a
book diagram should be, is not a real cost.

**ASCII diagrams in a `text` fence are underrated** and should be used freely for
memory layouts, stack frames, byte layouts, and tree structures. They copy as text,
print, and cost nothing.

## The constraints

Hold all of them, so that twenty diagrams across a book read as one visual system
rather than twenty separate drawings.

| Property | Value |
|---|---|
| Canvas | `viewBox="0 0 800 H"` — always 800 wide, height to fit |
| Grid | snap every coordinate to multiples of 8 |
| Stroke | `1.5` normal, `2.5` for emphasis. No other widths |
| Box corners | `rx="4"` |
| Label font | `var(--font-ui)` at 13–14px |
| Colours | only the five variables below |
| Arrowheads | one shared `<marker>` definition |

### The five colours

```text
--dia-fg       strokes and text
--dia-muted    connectors, secondary labels
--dia-accent   the one thing the diagram is about
--dia-warn     the failure path, the wrong branch
--dia-fill     box interiors
```

These are defined in `book.css` against the theme, so a diagram inverts for free in
dark mode. **Never hardcode a colour in a diagram.** `fill="#333"` is a bug: it
disappears against a dark background.

## The template

Copy this and adapt. It is the whole vocabulary.

```html literal why="diagram template for chapter writers; markup, not executable code"
<figure>
<svg viewBox="0 0 800 160" role="img" aria-labelledby="dia-3-1-title">
  <title id="dia-3-1-title">Source text flows through the scanner into a token stream</title>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--dia-muted)"/>
    </marker>
  </defs>

  <g fill="var(--dia-fill)" stroke="var(--dia-fg)" stroke-width="1.5">
    <rect x="24"  y="56" width="160" height="56" rx="4"/>
    <rect x="320" y="56" width="160" height="56" rx="4"/>
    <rect x="616" y="56" width="160" height="56" rx="4"/>
  </g>

  <g font-family="var(--font-ui)" font-size="14" fill="var(--dia-fg)"
     text-anchor="middle" dominant-baseline="middle">
    <text x="104" y="84">source</text>
    <text x="400" y="84">scanner</text>
    <text x="696" y="84">tokens</text>
  </g>

  <g stroke="var(--dia-muted)" stroke-width="1.5" fill="none" marker-end="url(#arrow)">
    <path d="M 188 84 L 314 84"/>
    <path d="M 484 84 L 610 84"/>
  </g>
</svg>
<figcaption>Figure 3-1. The scanner is the only stage that sees raw characters.</figcaption>
</figure>
```

Note the structure: geometry grouped by *role* (boxes, labels, connectors), with
shared attributes on the `<g>` rather than repeated per element. That is what keeps a
diagram editable.

## Rules

1. **`<title>` is required**, with a unique `id`, referenced by `aria-labelledby`. It must describe what the diagram *shows*, not what it is called. Ids must be unique across the whole book — use `dia-<chapter>-<n>-title`.
2. **The `<figcaption>` says what the diagram means.** If the caption only repeats the title, one of them is doing no work.
3. **Marker ids collide in the single-file build.** Every chapter is concatenated into one document, so either reuse the single shared `arrow` marker verbatim, or namespace yours as `arrow-ch3`.
4. **Four to eight boxes.** More than that and it is a diagram of a diagram; split it or use a table.
5. **No decoration.** No gradients, no shadows, no icons, no rounded-everything. Decorative extras measurably reduce learning.
6. **Label every edge that isn't obvious.** An unlabelled arrow between two boxes asserts a relationship without naming it.
7. **Wide diagrams** go in a `<figure class="fullwidth">` to use the sidenote rail.

## When not to draw

- The relationship is a sequence of two things. Say it in a sentence.
- The content is tabular. Use a table.
- You are drawing the code that is already on the page. Annotate the listing instead.
