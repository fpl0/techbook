# HTML and the Markdown subset

What `render.py` accepts, what it produces, and the constraints anyone editing
`book.css` has to hold to.

## Contents

- [The Markdown subset](#the-markdown-subset)
- [What gets built](#what-gets-built)
- [Design constraints](#design-constraints)
- [The typography, in numbers](#the-typography-in-numbers)
- [Accessibility floor](#accessibility-floor)

## The Markdown subset

`render.py` is a focused parser, not a CommonMark implementation. It takes no
dependencies, which is what lets a book build on a machine with nothing installed.
It supports exactly what chapters need:

| Supported | Notes |
|---|---|
| ATX headings `#`–`######` | `#` is the chapter title; `##` becomes a TOC entry and gets a permalink |
| Paragraphs | blank-line separated |
| Fenced code | with the block contract from `block-tags.md` |
| Lists | ordered, unordered, nested by indentation, task checkboxes |
| Pipe tables | with `:---:` alignment; wrapped in a horizontal scroller |
| Blockquotes | including nested markdown |
| Thematic breaks | `---`, `***` |
| Inline | `**bold**`, `*italic*`, `` `code` ``, `~~strike~~`, links, images, `<https://autolinks>` |
| Raw HTML blocks | passed through verbatim |

**Not supported, deliberately:** setext headings, reference links, HTML comments as
structure, footnote syntax (use sidenotes), and definition lists.

### Raw HTML is passed through, and fences inside it still work

A block-level HTML tag at the start of a line opens a passthrough region that runs to
the next blank line at nesting depth zero. Fenced code inside that region is still
rendered as a proper listing — which is what makes exercises and `<details>` solutions
containing code work.

A paragraph that merely *begins* with an inline tag (`<span>`, `<label>`) is still a
paragraph. Only block-level tags open a passthrough region.

### Escaping

Inline code spans and raw HTML tags are extracted before escaping, so neither gets
mangled. Everything else is HTML-escaped. `---` becomes an em dash, `--` an en dash,
`...` an ellipsis — so write those literally and let the renderer do it.

## What gets built

```text
build/
├── index.html          cover, front matter, contents
├── chNN-slug.html      one page per chapter — the primary reading experience
├── book.html           every chapter in one self-contained file
├── search.json         section-level index
└── assets/
    ├── book.css
    └── book.js
```

**Two output shapes, deliberately.** Per-chapter pages give better first paint,
stable citable URLs, and sane browser history. The single file is for offline
reading, Ctrl-F across the whole book, and print-to-PDF — and it inlines its CSS, JS
and search index so it works with no network and no sibling files.

Chapter files are ordered and numbered from their filename: `ch03-scanning.md` is
chapter 3, and its listings number `3-1`, `3-2`. Keep that convention.

## Design constraints

Hold these; they are why the book doesn't look like a docs site.

1. **No framework, no web fonts, no build step, no network at read time.** System font stacks only. A book that needs a CDN is a book that breaks on a plane.
2. **Fully readable with JavaScript disabled.** `book.js` adds theme memory, scrollspy, search, copy buttons and keyboard nav. It creates no content. Nothing in it is required to read the book.
3. **Every colour is defined on bare `:root` first**, then overridden under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, then again under `:root[data-theme="dark"]` so the toggle wins both directions. A colour whose only definition lives inside a media query is a bug.
4. **Wide content scrolls inside its own container.** Tables and code blocks get `overflow-x: auto`. The page body never scrolls horizontally.
5. **One accent hue.** Every link, rule, marker and active state is the same blue. Additional colour has to earn its place — the warn colour for misconception callouts is the only other one.
6. **Print CSS is the PDF story.** No LaTeX, no TinyTeX. Chrome's print engine plus `@page` rules produces a good PDF; `<details>` are forced open, sidenotes fold inline, and URLs are printed after their links.

## The typography, in numbers

| Property | Value | Why |
|---|---|---|
| Prose font | Iowan Old Style → Charter → Cambria → Georgia | serif for sustained reading; all system-installed |
| UI font | system sans | chrome, captions, headings |
| Code font | ui-monospace → SF Mono → Menlo | ligatures disabled — `!=` must not render as `≠` |
| Body size | `clamp(1.0625rem, 0.98rem + 0.42vw, 1.1875rem)` | 17px → 19px; books read larger than app UI |
| Line height | 1.65 unitless | long measures want 1.6–1.7 |
| Measure | 68ch | the 50–75 characters-per-line band; WCAG caps at 80 |
| Heading scale | 1.25 | h1 2.25rem, h2 1.6rem, h3 1.25rem, h4 1.0625rem uppercase |
| Heading margins | top 2.2em, bottom 0.5em | a heading must attach to the text below it |
| Code size | 0.875em, line-height 1.55, tab-size 4 | mono renders optically larger at equal px |
| Light ground | `#1a1a1a` on `#fdfdfb` | warm off-white; pure white on pure black is punishing |
| Dark ground | `#e6e3dd` on `#16171a` | same reasoning inverted |

Only four heading levels are styled. If a chapter needs `h5`, the chapter is
structured wrong.

## Accessibility floor

Non-negotiable, and cheap:

- Landmarks: `<header>`, `<nav>`, `<main>`, `<article>`. A skip link first in the body.
- One `<h1>` per page. No skipped heading levels.
- Every SVG carries `role="img"` and an `aria-labelledby` pointing at a real `<title>`.
- Every figure has a `<figcaption>`.
- Visible `:focus-visible` rings. Never `outline: none`.
- Heading permalinks are always visible under `@media (hover: none)` — a hover-only affordance is invisible on touch.
- Every animation and transition is disabled under `prefers-reduced-motion`.
- Body contrast is at least 7:1; captions and sidenotes at least 4.5:1.
