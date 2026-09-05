# Design review: techbook HTML output

Reviewed: `skill/assets/book.css`, the page templates in `skill/scripts/render.py`
(`head`, `masthead`, `toc_html`, `chapter_page`, `cover_html`, `cover_cta`,
`index_page`, `glossary_page`, `single_page`, `render_listing`), the spec in
`skill/references/html-spec.md`, and the rendered fixture at
`fixtures/rich/build/` (`index.html`, `ch01-shapes.html`, `book.html`), viewed in
Chrome at 1440×900 light, 1440×900 dark, and 390×844 mobile, plus a headless-Chrome
print of `book.html` to PDF.

## Verdict

The bones are a book: one serif column on warm paper, an italic running head,
oldstyle figures, a real small-caps opener, hairline furniture instead of coloured
cards, and a listing that is a numbered figure with a caption. The skin is still a
website: a sticky app bar with "Contents · Search / · Auto", a Medium-style progress
line, a hero banner instead of a cover, grey pill backgrounds on every inline code
span, a per-listing toolbar, and a contents drawer that is clipped off the left edge
of a phone. Two things are outright broken (the mobile drawer, and `<details>` that
stay shut in print) and four colours fail WCAG AA at the sizes they are used; those
must go first, then the chrome must be cut back until only the paper is left.

## Still says website

| Tell | Where | Why it reads as web |
|---|---|---|
| Sticky app bar with three controls, one of them the word "Auto" | `.masthead` (book.css:205) and `masthead()` (render.py:561–575) | A book's running head carries the book and chapter title. "Auto" is a state label for a toggle nobody asked for; "Search /" is a keyboard hint shown on a phone. |
| 2px accent progress line under the header | `#progress` (book.css:246) and `wireScroll()` in book.js | This is Medium's reading-progress bar. Books signal position with page numbers or a section in the running head, not a loading strip. |
| Cover is a coloured hero strip under a sticky header | `.cover-hero` (book.css:760), `cover_html()`, and the masthead being emitted above it in `index_page()` (render.py:697–700) | A 308px tall band on a 900px viewport with a header above it is a landing-page hero, not a jacket. A cover fills the page and has no chrome on it. |
| "Begin with chapter 1 → · Contents" link pair, then a "Contents" heading 60px below | `cover_cta()` (render.py:672) and `.cover h2` (book.css:812) | A CTA row. The "Contents" link points at the heading immediately under it. |
| Inline `code` on a tinted pill | `p code, li code, td code … { background: var(--bg-code); padding; border-radius }` (book.css:416–420) | The single strongest docs-site signal. Crafting Interpreters and Butterick both set inline code as plain monospace; the face alone marks it. |
| Listing toolbar: file · lang · badge · Copy | `figcaption.bar` (book.css:453–470) and the `bar` list in `render_listing()` (render.py:156–163) | A header bar on every block is the GitHub/README idiom. Crafting Interpreters has no bar; the Rust Book puts "Filename:" as one italic line above the block. "python" on every block in a Python book is noise. |
| Double `<figcaption>` per figure | `render_listing()` emits `figcaption.bar` and `figcaption.caption` in one `<figure>` | Invalid HTML (one `figcaption` per `figure`) and screen readers announce two captions. |
| Output block hangs *after* the caption | `render_listing()` appends `.output-block` outside the `</figure>`; `.output-block { margin: -2em 0 2em }` (book.css:510) | The caption "Listing 1-1" lands between the code and its result, so the caption visually labels the code only and the output looks like an unrelated grey box. |
| Rules stacked on rules | listing `border-bottom` (book.css:450) + `.callout` `border-top` (book.css:564) + `.output-block` `border-bottom` (book.css:512) | Two hairlines 60px apart with nothing between them (see Listing 1-2 → "This trips people up"). Rules are meant to replace cards, not to become a ledger. |
| Table stretched to the full measure | `table { width: 100% }` (book.css:390) | A three-column table with 250px of whitespace between "Input" and "sum". Books set tables at content width. |
| Old-style figures in numeric table columns | `table { font-variant-numeric: tabular-nums oldstyle-nums }` (book.css:392) | "10 / 4 / 0" render as "1o / 4 / o". Old-style is for running text; tables want lining tabular figures (Bringhurst 3.2, Butterick "alternate figures"). |
| Visible `#` permalink at 35% on touch | `@media (hover: none) { .anchor { opacity: 0.35 } }` (book.css:701) | A grey hash after every heading on a phone. |
| Bullets indented 40px inside the measure | browser default `ul { padding-inline-start: 40px }` never overridden | Bullet text sits a full em right of paragraph text. Books hang the bullet in the margin and keep the text flush. |
| Contents drawer is a dropdown with a drop shadow | `.contents-drawer > .toc { position: absolute; box-shadow: 0 14px 40px … }` (book.css:263–279) | A menu. On a phone it also overflows the left edge (below). |
| Inline style in the template | `<p style="margin-top:2.5rem">` in `index_page()` (render.py:705) | Not a reader-facing tell, but it means the "read as a single page" line has no class and cannot be styled or hidden in print. |
| The spec disagrees with the stylesheet | `html-spec.md` says blue accent, sans UI font, 64ch, line-height 1.65, h4 uppercase, `#fdfdfb` paper, `#16171a` dark; `book.css` says oxblood, serif UI, 62ch, 1.58, warm paper, `#151413` | Anyone "holding to the spec" will regress the CSS. One of them has to be true. |

## Prioritised changes

### 1. MUST — Fix the contents drawer on phones (it is clipped off-screen)

Measured at 390px: the drawer panel is 351px wide, anchored `right: 0` to a
68px-wide summary at x≈175, so its left edge lands at **−109px**. The first third of
every chapter title is cut off (screenshot confirmed: "of a Chapter", "em", "model").

```css
@media (max-width: 720px) {
  .contents-drawer { position: static; }              /* stop anchoring to the summary */
  .contents-drawer > .toc {
    position: fixed;
    left: 0.75rem; right: 0.75rem; top: calc(var(--head-h) + 0.5rem);
    width: auto;
    max-height: calc(100dvh - var(--head-h) - 1.5rem);
    box-shadow: 0 10px 30px rgb(0 0 0 / 0.18);
  }
}
```

Why: a phone reader's only way to move between chapters is this drawer. It must be
a sheet under the header, not a menu hung from a button.

### 2. MUST — Force `<details>` open in print (they stay shut in the PDF)

The headless-Chrome PDF shows "▸ Predict: …" and "▸ Solution" closed. The rule
`details > :not(summary) { display: block !important }` (book.css:917) cannot open a
closed `<details>`; the content is hidden by the element's own slot, not by
`display`. Two fixes, use both:

```css
@media print {
  details::details-content { display: block !important; content-visibility: visible !important; }
  summary::before { content: ""; }        /* no disclosure triangle on paper */
}
```

```js
/* book.js */
window.addEventListener("beforeprint", function () {
  document.querySelectorAll("details:not([open])").forEach(function (d) {
    d.setAttribute("data-was-closed", ""); d.open = true;
  });
});
window.addEventListener("afterprint", function () {
  document.querySelectorAll("details[data-was-closed]").forEach(function (d) {
    d.open = false; d.removeAttribute("data-was-closed");
  });
});
```

Why: the spec promises "`<details>` are forced open" for the PDF. Today every
solution and checkpoint answer is missing from the printed book.

### 3. MUST — Raise four colours to WCAG AA at the sizes they are used

Measured on `#faf8f2` paper / `#f3f1ea` code ground:

| Token | Now | Contrast | Used at | Fix | New contrast |
|---|---|---|---|---|---|
| `--fg-faint` | `#857f75` | 3.74 (3.51 on code) | 14.4px bar labels, `.orient .meta`, `.toc h2` (bold), `.chapter-nav .dir`, `.who`, `kbd`, search `.where` | `#6b655b` | 5.44 / 5.11 |
| `--tok-c` (comments) | `#948b7c` | 2.98 on code | 15.2px italic | `#6f6a60` | 4.76 |
| `--tok-p` (prompt) | `#a59d8e` | 2.38 on code | 15.2px | `#7f786a` (and keep `user-select: none`) | 3.87 — acceptable only because a prompt is decoration; if it must pass, use `--tok-c` |
| `--tok-c` dark | `#7f776b` | 3.93 on `#1c1a18` | 15.2px italic | `#958d80` | 5.29 |

```css
:root { --fg-faint: #6b655b; --tok-c: #6f6a60; --tok-p: #7f786a; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --tok-c: #958d80; --tok-p: #8f877a; } }
:root[data-theme="dark"] { --tok-c: #958d80; --tok-p: #8f877a; }
```

Why: the spec's own floor is "captions and sidenotes at least 4.5:1". Comments are
the most-read token in a teaching listing; at 2.98:1 they are the least legible thing
on the page. Crafting Interpreters' comment grey sits near 4.6:1.

### 4. MUST — One `<figcaption>` per figure; put the output inside the figure, before the caption

`render_listing()` currently emits:

```html
<figure class="listing"><figcaption class="bar">…</figcaption><pre>…</pre>
<figcaption class="caption">Listing 1-1. …</figcaption></figure>
<div class="output-block"><div class="label">Output</div><pre>2.5</pre></div>
```

Change to:

```html
<figure class="listing" id="listing-1-1">
  <div class="bar">…</div>                       <!-- not a figcaption -->
  <pre><code class="language-python">…</code></pre>
  <pre class="output" aria-label="Output">2.5</pre>
  <figcaption><span class="num">Listing 1-1.</span> A first attempt at a running average.</figcaption>
</figure>
```

and in `render_listing`, thread `expected` into the figure before the caption
instead of appending after `</figure>`. CSS:

```css
figure.listing > .bar { /* same rules as figcaption.bar today */ }
figure.listing > pre.output {
  background: var(--bg-output);
  color: var(--fg-muted);
  border-top: 1px dashed var(--rule-strong);
  white-space: pre-wrap;
  padding-top: 0.7rem;
}
figure.listing > pre.output::before {
  content: "output";
  display: block;
  font: italic 0.85rem var(--font-prose);
  color: var(--fg-faint);
  margin-bottom: 0.25rem;
}
.output-block { /* delete */ }
```

Why: HTML permits one `figcaption`; two makes screen readers announce the toolbar as
the caption. And the caption belongs *under the whole figure* — code and its result
are one exhibit, which is exactly how Crafting Interpreters and the Rust Book
present a run.

### 5. MUST — Reconcile `html-spec.md` with `book.css`

The spec table lists a blue accent, a sans UI font, 64ch, 1.65 leading, an uppercase
h4, `#fdfdfb`/`#1a1a1a` paper and `#16171a`/`#e6e3dd` dark. None of those are in the
CSS. Rewrite "The typography, in numbers" to the shipped values (or the values below
after changes 6–8), and change item 5 of "Design constraints" from "the same blue" to
"the same oxblood (`--accent`)".

Why: the spec is the document the CSS "claims to follow"; today it is a trap for the
next editor.

### 6. SHOULD — Shorten the measure; it is 78 characters, not 66–70

Measured at 1440px: `main` is 655px; Iowan Old Style at 19px averages 8.43px/char →
78 cpl (`--measure: 62ch` because Iowan's `0` is narrow). The spec promises 66–70.

```css
:root { --measure: 56ch; }   /* → 592px → ~70 cpl in Iowan; ~64 code columns at 15.2px */
```

If 64 code columns is too few, let listings and tables overhang the text column
rather than widening prose:

```css
@media (min-width: 1081px) {
  figure.listing, .table-wrap { margin-left: -1.1rem; margin-right: -1.1rem; }
}
```

Why: Bringhurst 2.1.2 (45–75, 66 ideal), Butterick "line length" (45–90, aim for the
middle). At 78 the eye loses the return sweep on the empty-rail side of a 1440 screen.

### 7. SHOULD — Centre the text column when the rail is empty

The grid centres `text + gap + rail` as one block, so the prose column's centre is at
x≈572 on a 1440 viewport (centre 720). On a chapter with one sidenote the page reads
as left-aligned. Pad the shell so the text is centred and the rail overhangs right:

```css
@media (min-width: 1081px) {
  .shell { padding-left: calc(var(--rail-right) + 2.5rem + 1.5rem); }
}
```

Why: Tufte's asymmetry is earned only when the margin is *used*. Gwern and Tufte CSS
both fill their margins; a book with occasional sidenotes should read centred.

### 8. SHOULD — Strip the listing toolbar to what a book prints

Drop the language label when the book has a dominant language (compute the mode of
`lang` across chapters in `render.py`, pass it into `render_listing`, and only emit
`.lang` when it differs). Move the verification mark into the caption. Make the copy
button an absolutely-positioned affordance on the `pre`, not a bar item. The result
is: filename (if any), code, output, caption.

```html
<figure class="listing" id="listing-1-1">
  <div class="file">code/average.py</div>
  <pre>…<button class="copy" type="button" aria-label="Copy listing 1-1">Copy</button></pre>
  <figcaption><span class="num">Listing 1-1.</span> A first attempt at a running average.
    <span class="tag verified" title="This listing was executed and its output checked">✓</span></figcaption>
</figure>
```

```css
figure.listing > .file {
  font: 0.85rem/1.4 var(--font-code);
  color: var(--fg-muted);
  padding: 0.45rem 1.1rem 0;
}
figure.listing > pre { position: relative; }
button.copy { position: absolute; top: 0.4rem; right: 0.6rem; }
figcaption .tag.verified { color: var(--ok); font-style: normal; margin-left: 0.4em; }
figcaption .tag.error-demo::before { content: "✗ raises"; color: var(--warn); }
```

Why: Crafting Interpreters shows *no* per-block chrome; the Rust Book shows one
italic "Filename:" line. "verified" repeated on every listing is a claim the book
should make once (in the front matter) and mark quietly thereafter.

### 9. SHOULD — Remove the pill background from inline code

```css
p code, li code, td code, h2 code, h3 code, dd code { background: none; padding: 0; border-radius: 0; }
code { font-size: 0.88em; }
```

Why: Butterick ("monospaced fonts") and Crafting Interpreters both rely on the
face alone. The pills fragment every sentence that mentions an identifier (see "sum
of an empty sequence is 0, not an error").

### 10. SHOULD — Make the running head a running head

Replace "Search /" and "Auto" with what a reader recognises, hide the keyboard hint
where there is no keyboard, and use the scrollspy to put the current section on the
right where a recto running head goes. Drop the progress bar.

```html
<header class="masthead">
  <span class="crumb"><a class="book" href="index.html">A Rich Fixture</a><span class="sep"> · </span>Shapes of a Chapter</span>
  <span class="spacer"></span>
  <span class="section" id="running-section" aria-live="off"></span>
  <details class="contents-drawer"><summary>Contents</summary>…</details>
  <button id="search-toggle" type="button" aria-keyshortcuts="/">Search<kbd>/</kbd></button>
  <button id="theme-toggle" type="button" aria-label="Colour scheme: automatic">Theme</button>
</header>
```

```css
.masthead kbd { display: none; }
@media (hover: hover) and (pointer: fine) { .masthead kbd { display: inline; } }
.masthead .section { font-style: italic; color: var(--fg-faint); margin-right: 1rem; }
#progress { display: none; }
```

In `wireScroll()`, when `active` changes, set `running-section.textContent` to the
active heading's text. Label the theme button "Theme" and put the current state in
the `aria-label` and `title` only; cycle the visible label to "Light"/"Dark" *after*
a click if you must, never "Auto" at rest.

Why: a running head tells the reader where they are (book · chapter § section); a
progress bar tells them how much scrolling remains. The former is bookish, the
latter is Medium.

### 11. SHOULD — Make the cover a cover

Hide the masthead on the cover page, let the jacket fill the viewport, put the
byline on it, and replace the two-link CTA with a single line.

```python
# index_page(): add a body class so the cover can drop the chrome
head("Cover", …)  →  head("Cover", …, extra='<style>body{}</style>') # or pass a body class through head()
```

```css
body.cover-page .masthead { position: static; background: var(--cover-bg); border: 0; color: var(--cover-fg); }
.cover-hero { min-height: calc(100svh - var(--head-h)); align-content: center; }
.cover-cta { margin: 2rem 0 3rem; }
.cover-cta a + a { display: none; }         /* the "Contents" link points 60px down */
```

And give the jacket something to hold: the title top-left or bottom-left rather than
dead-centre, with a 1px inset rule (`outline: 1px solid rgb(247 243 234 / 0.3); outline-offset: -1.5rem`) so the block reads as a jacket rather than a banner.

Why: the jacket colour is the right instinct; a coloured strip under a sticky header
is a hero. Standard Ebooks and O'Reilly PDFs put nothing above the cover.

### 12. SHOULD — Tables: content width, lining figures, header spacing

```css
table { width: auto; max-width: 100%; font-variant-numeric: tabular-nums lining-nums; }
th, td { padding: 0.45em 1.2em 0.45em 0; }
th[style*="right"], td[style*="right"] { padding-right: 1.2em; }
```

Why: measured "10 / 4 / 0" columns render as "1o / 4 / o" with old-style figures.
Bringhurst 3.2: "Use tabular lining figures in tables." A full-width table with three
short columns is a spreadsheet, not a book table.

### 13. SHOULD — Hang the bullets; hyphenate on narrow screens

```css
ul, ol { padding-left: 1.3em; }
li { padding-left: 0.1em; }
@media (max-width: 720px) { p, li, .sidenote { hyphens: auto; } }
```

Why: measured 46 cpl at 390px with no hyphenation and `text-wrap: pretty` only;
the rag on narrow lines is visibly rough ("is wrong." alone on a line). `lang="en"`
is already set so `hyphens: auto` works.

### 14. SHOULD — Drop the visible `#` on touch; make headings self-linking

```css
.anchor { position: absolute; left: -1.2em; opacity: 0; }
h2, h3, h4 { position: relative; }
@media (hover: none) { .anchor { opacity: 0; } }
```

Plus in `render_markdown`, emit the anchor *before* the heading text
(`<a class="anchor" …>#</a>The problem`) so it hangs in the left margin on hover
like gwern.net, instead of trailing the title.

Why: a 10px-wide trailing `#` is neither a tap target (measured 10×27) nor a
typographic mark. Hidden-until-hover in the gutter is the convention that does not
disturb the title.

### 15. SHOULD — Hide the empty chapter nav and give a chapter an ending

`ch01-shapes.html` ends with `<nav class="chapter-nav"></nav>`: a rule, 7rem of
paper, and nothing. In `chapter_page()` emit the nav only when it has a link, and
always offer the way home:

```python
nav = []
if prev_ch or next_ch:
    nav = ['<nav class="chapter-nav" aria-label="Chapter navigation">', …, '</nav>']
else:
    nav = ['<nav class="chapter-nav" aria-label="Chapter navigation">'
           '<a class="prev" href="index.html"><span class="dir">Contents</span></a></nav>']
```

Why: the end of a chapter is where a reader decides to continue. A lone hairline is
not an ending.

### 16. SHOULD — Soften dark-mode ink and separate the code ground

Measured dark: `--fg` is 14.5:1 on `#151413`, and the code block is 1.06:1 from the
page, so listings are defined only by their hairlines.

```css
:root[data-theme="dark"], :root:not([data-theme="light"]) /* inside the media query */ {
  --fg: #d8d2c6;        /* 12.2:1, less halation on OLED */
  --bg-code: #221f1c;   /* 1.12:1 — visible as a block, not a slab */
  --bg-output: #1c1a18;
}
```

Why: Butterick and every e-reader dark theme step the white down from full paper
brightness; long-form dark reading at 14:1 causes halation.

### 17. SHOULD — Print: a readable measure and page furniture

The A4 PDF sets 10.5pt across a 174mm text block: ~105 characters per line. Fix the
measure, and add page numbers and a running head (Chrome supports `@page` margin
boxes as of v131):

```css
@media print {
  @page { size: A4; margin: 22mm 25mm 24mm;
          @top-right { content: string(chapter); font: italic 9pt "Iowan Old Style", Georgia, serif; color: #444; }
          @bottom-center { content: counter(page); font: 9pt "Iowan Old Style", Georgia, serif; } }
  body { font-size: 11pt; line-height: 1.5; }
  main { max-width: 128mm; }                 /* ≈ 70 cpl at 11pt Iowan */
  h1 { string-set: chapter content(); }
  figure.listing { break-inside: avoid; }
  .cover-hero { border: 0; }
  .cover-hero h1 { font-size: 34pt; }
  .cover-hero .subtitle { font-size: 14pt; }
}
```

Why: the PDF is the "print story" per the spec. No page numbers, no running head,
and a 105-character line is not an acceptable book page.

### 18. NICE — Guard small caps against synthesis

Iowan Old Style on macOS has real `smcp` (verified: the width does not change with
`font-synthesis: none`), but Palatino, Book Antiqua and Georgia do not, and the
stack falls through to them on Windows.

```css
.newthought { font-variant-caps: small-caps; font-synthesis-small-caps: none; letter-spacing: 0.04em; }
```

With that, a font lacking small caps shows the phrase in lowercase rather than
fake caps; if you would rather see caps than nothing, use
`text-transform: uppercase; font-size: 0.82em; letter-spacing: 0.08em` on a
fallback via `@supports not (font-variant-caps: small-caps)`, but never synthesised
small caps (Butterick, "small caps").

### 19. NICE — Sidenote numbers as real text, and drop the dead toggle

The number is generated twice in CSS (`.sidenote-number::after`, `.sidenote::before`)
and the `<label for="sn-1">` is empty, so assistive tech reads a nameless label and
no superscript. Emit the number in the markup (`<sup class="sn-ref"><a href="#sn-1-note">1</a></sup>`)
and drop `input.margin-toggle`, which is `display: none` everywhere and never
toggles anything (mobile already shows the note inline).

### 20. NICE — Figure captions to match listing captions

```css
figcaption .num, figcaption > b:first-child { font-style: normal; font-weight: 700; color: var(--fg); }
```

and have `render_markdown` wrap "Figure 1-1." in `<span class="num">` as
`render_listing` does for listings, so the two kinds of exhibit share one caption
style.

### 21. NICE — Contents-page blurb should stop at the first paragraph

The cover's chapter blurb currently reads "…This one opens with a broken program.
What you'll learn…", having harvested the orientation box. Take the first `<p>` of
the body only.

### 22. NICE — Search dialog

`dialog#search input { outline: none }` violates the spec's own "never
`outline: none`". Style the focus instead:

```css
dialog#search input:focus-visible { outline: 0; box-shadow: inset 0 -2px 0 var(--accent); }
```

Also add `<button type="button" aria-label="Close" formmethod="dialog">` for touch
users; Esc is not discoverable on a phone.

## Measurements

| Measurement | Value | Verdict |
|---|---|---|
| Body font (resolved) | Iowan Old Style, 19px, line-height 30px (1.58) | Good size; leading at the low end for 78 cpl |
| Measure at 1440px | 655px = 62ch = **78 cpl** | Too long; target 66–70 |
| Code columns at 1440px | 67 at 15.2px | Fine; keep ≥ 64 after narrowing |
| h1 / h2 / h3 / body | 44 / 24 / 21.9 italic / 19px | Hierarchy is clear; h3 italic-bold is a good book move |
| Smallest text on page | 13.07px (`code` inside a 15.2px context) | Borderline; the 14.4px bar labels are the practical floor |
| Caption / bar / meta size | 14.4px | OK once the colour passes AA |
| `--fg` on paper | 15.8:1 | Good |
| `--fg-muted` on paper | 6.5:1 | Good |
| `--fg-faint` on paper / code | **3.74 / 3.51** | Fails AA for text under 24px |
| `--tok-c` on code ground | **2.98** | Fails |
| `--tok-p` on code ground | **2.38** | Fails (decorative, `user-select: none`) |
| `--accent` / `--ok` / `--warn` on paper | 7.0 / 5.9 / 5.6 | Pass |
| Dark `--fg` on `#151413` | 14.5:1 | Too bright for sustained dark reading |
| Dark code ground vs page | 1.06:1 | Block is invisible without its rules |
| Mobile body | 17.3px, 46 cpl, no hyphenation | Size right; rag rough |
| Mobile masthead controls | 38px tall | Below the 44px Apple/WCAG 2.5.5 target |
| Mobile copy button | 36×29px | Below target |
| Mobile checkpoint summary | 331×64px | Good |
| Mobile contents drawer | left edge at **−109px** | Broken |
| Heading permalink `#` | 10×27px at 35% opacity on touch | Not a target, not a mark |
| Print body | 10.5pt on 174mm ≈ 105 cpl, no page numbers | Not acceptable as a PDF |
| Print `<details>` | closed | Broken |
| Real small caps in Iowan | yes (`smcp` present) | Good; guard fallbacks |

## What is already right and must not be regressed

- **The palette.** Warm paper `#faf8f2`, near-black ink, one oxblood accent, and a
  restrained token set. The oxblood jacket is a genuine identity; keep it the same
  in both themes as the CSS already does.
- **Serif body at 19px with oldstyle figures and `text-wrap: pretty`.** The prose
  looks like a book page the moment there is no chrome in the frame.
- **Real small caps on the opening phrase** (`font-variant-caps` with a font that
  has them). Keep the guard from change 18 so it never becomes fake.
- **Italic bold h3, upright h2, no uppercase anywhere.** The heading scale is quiet
  and correct.
- **Hairlines instead of cards** for orientation, crux, callout, tip and aside.
  The only colour is the label word. Do not add backgrounds.
- **The listing as a numbered figure with a caption beneath** and the yellow
  line-emphasis band that runs edge to edge. The eight-token palette on a muted
  base is the right restraint.
- **Full-bleed listings and output on phones** (`margin-left/right: -1.15rem`).
- **`<details>` as the checkpoint mechanism with a CSS triangle**, and the drawer
  as a `<details>` so contents work without JavaScript.
- **Dark theme defined three times** (bare `:root`, media query, `[data-theme]`)
  exactly as the spec demands; nothing lives only inside a media query.
- **Every SVG has `role="img"` and a real `<title>`; every figure has a caption;
  a skip link is first in the body; `prefers-reduced-motion` kills every
  transition; `:focus-visible` rings are visible.**
- **Ligatures off in code, `tab-size: 4`, `overflow-x: auto`, no horizontal page
  scroll at 390px** (measured `scrollWidth` = 390).
- **Print already** goes black-on-white, prints URLs after external links, folds
  sidenotes inline, hides chrome, and breaks each chapter to a new page.
