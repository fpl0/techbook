#!/usr/bin/env python3
"""
render.py — turn a techbook project's Markdown into the book.

Emits a multi-page site (index.html + one page per chapter) and a single
self-contained book.html for offline reading, Ctrl-F across everything, and
print-to-PDF. Plus search.json.

No dependencies, no network, no build step. The Markdown subset supported here
is exactly the subset the skill tells chapter writers to emit: ATX headings,
paragraphs, nested lists, fenced code carrying the block contract, blockquotes,
pipe tables, thematic breaks, raw HTML passthrough (for sidenotes, callouts,
<details> and inline SVG), and inline emphasis/code/links/images.

Usage:
    render.py <book-dir> [--out build] [--no-single]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from verify import parse_info, FENCE_RE, MODES, RUNNABLE_LANGS  # noqa: E402


# ── inline ────────────────────────────────────────────────────────────────────

INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
ITALIC = re.compile(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])", re.S)
STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S)
AUTOLINK = re.compile(r"<((?:https?)://[^>\s]+)>")
RAW_TAG = re.compile(r"</?[A-Za-z][\w-]*(?:\s[^<>]*)?/?>")
TAG_RE = re.compile(r"<(/?)([A-Za-z][\w-]*)[^<>]*?(/?)>")
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


def inline(text: str) -> str:
    """Render inline Markdown. Raw HTML tags are preserved verbatim."""
    slots: list[str] = []

    def stash(s: str) -> str:
        slots.append(s)
        return f"\x00{len(slots) - 1}\x00"

    # code spans first — nothing inside them is Markdown
    text = INLINE_CODE.sub(
        lambda m: stash(f"<code>{html.escape(m.group(2).strip())}</code>"), text)
    # then raw HTML tags, so escaping below can't mangle them
    text = RAW_TAG.sub(lambda m: stash(m.group(0)), text)

    # Links and images are extracted BEFORE the global escape. Escaping first
    # would turn `?a=1&b=2` into `?a=1&amp;b=2`, and escaping the captured URL
    # again yields `&amp;amp;` -- a broken href. Autolinks likewise have to be
    # seen while their angle brackets are still angle brackets.
    text = IMAGE.sub(
        lambda m: stash(
            f'<img src="{html.escape(m.group(2), quote=True)}" '
            f'alt="{html.escape(m.group(1), quote=True)}"'
            + (f' title="{html.escape(m.group(3), quote=True)}"' if m.group(3) else "")
            + ">"),
        text)
    text = LINK.sub(
        lambda m: stash(
            f'<a href="{html.escape(m.group(2), quote=True)}"'
            + (' target="_blank" rel="noopener"'
               if m.group(2).startswith("http") else "")
            + f">{inline(m.group(1))}</a>"),
        text)
    text = AUTOLINK.sub(
        lambda m: stash(
            f'<a href="{html.escape(m.group(1), quote=True)}" '
            f'target="_blank" rel="noopener">{html.escape(m.group(1))}</a>'), text)

    text = html.escape(text, quote=False)

    text = BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", text)
    text = STRIKE.sub(lambda m: f"<del>{m.group(1)}</del>", text)

    # typographic niceties, applied only outside code/html
    text = text.replace("---", "—").replace("--", "–").replace("...", "…")

    for i, s in enumerate(slots):
        text = text.replace(f"\x00{i}\x00", s)
    return text


# ── slugs ─────────────────────────────────────────────────────────────────────

def slugify(text: str, seen: dict | None = None) -> str:
    s = re.sub(r"<[^>]+>", "", text)
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    s = re.sub(r"[\s_]+", "-", s) or "section"
    if seen is not None:
        base, n = s, 2
        while s in seen:
            s = f"{base}-{n}"
            n += 1
        seen[s] = True
    return s


# ── document model ────────────────────────────────────────────────────────────

@dataclass
class Heading:
    level: int
    text: str
    slug: str


@dataclass
class Chapter:
    stem: str
    number: int | None
    title: str
    body_html: str
    headings: list = field(default_factory=list)
    sections: list = field(default_factory=list)   # for search.json
    blurb: str = ""


# ── block rendering ───────────────────────────────────────────────────────────

LISTING_TAGS = {
    "run": ("verified", "verified"),
    "check": ("verified", "compiles"),
    "expect-error": ("error-demo", "error demo"),
    "norun": ("unverified", "not run here"),
    "literal": ("unverified", "illustrative"),
}


def render_listing(lang: str, mode: str, tags: dict, body: str,
                   number: str | None, expected: str | None) -> str:
    cls, label = LISTING_TAGS.get(mode, ("unverified", mode))
    filename = tags.get("file") or tags.get("filename")
    if isinstance(filename, str):
        filename = filename.split("#")[0]

    bar = ['<figcaption class="bar">']
    if filename:
        bar.append(f'<span class="file">{html.escape(str(filename))}</span>')
    bar.append(f'<span class="lang">{html.escape(lang)}</span>')
    bar.append('<span class="spacer"></span>')
    bar.append(f'<span class="tag {cls}">{label}</span>')
    bar.append('<button class="copy" type="button">Copy</button>')
    bar.append("</figcaption>")

    # line highlighting
    hl = tags.get("highlight")
    lines = body.split("\n")
    if isinstance(hl, str):
        wanted: set[int] = set()
        for part in hl.split(","):
            if "-" in part:
                a, _, b = part.partition("-")
                try:
                    wanted |= set(range(int(a), int(b) + 1))
                except ValueError:
                    pass
            else:
                try:
                    wanted.add(int(part))
                except ValueError:
                    pass
        rendered = "\n".join(
            (f'<span class="hl-line">{html.escape(ln)}</span>' if i + 1 in wanted
             else html.escape(ln))
            for i, ln in enumerate(lines))
    else:
        rendered = html.escape(body)

    lang_class = f' class="language-{html.escape(lang)}"' if lang else ""
    out = [f'<figure class="listing" id="listing-{number}">' if number
           else '<figure class="listing">']
    out += bar
    out.append(f"<pre><code{lang_class}>{rendered}</code></pre>")
    if number:
        cap = tags.get("caption")
        cap_txt = f" {inline(str(cap))}" if isinstance(cap, str) else ""
        out.append(f'<figcaption class="caption">'
                   f'<span class="num">Listing {number}.</span>{cap_txt}</figcaption>')
    out.append("</figure>")

    if expected is not None:
        out.append('<div class="output-block"><div class="label">Output</div>'
                   f"<pre>{html.escape(expected)}</pre></div>")
    return "\n".join(out)


TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += ch
    cells.append(cur.strip())
    return cells


def render_markdown(md: str, chapter_stem: str, chapter_no: int | None,
                    seen_slugs: dict) -> tuple[str, list[Heading], list[dict]]:
    lines = md.split("\n")
    out: list[str] = []
    headings: list[Heading] = []
    sections: list[dict] = []
    cur_section = {"heading": "", "slug": "", "text": []}
    listing_n = 0
    i = 0

    def flush_section():
        if cur_section["heading"] or cur_section["text"]:
            txt = " ".join(cur_section["text"]).strip()
            if txt or cur_section["heading"]:
                sections.append({
                    "heading": cur_section["heading"] or "(intro)",
                    "slug": cur_section["slug"],
                    "text": re.sub(r"\s+", " ", txt)[:1200],
                })
        cur_section["heading"], cur_section["slug"], cur_section["text"] = "", "", []

    while i < len(lines):
        line = lines[i]

        # blank
        if not line.strip():
            i += 1
            continue

        # fenced code
        m = FENCE_RE.match(line)
        if m and m.group("info").strip() != "" or (m and m.group("info").strip() == ""):
            fence = m.group("fence")
            lang, tags = parse_info(m.group("info"))
            j = i + 1
            while j < len(lines):
                m2 = FENCE_RE.match(lines[j])
                if (m2 and m2.group("fence")[0] == fence[0]
                        and len(m2.group("fence")) >= len(fence)
                        and not m2.group("info").strip()):
                    break
                j += 1
            body = "\n".join(lines[i + 1:j])
            mode = next((t for t in tags if t in MODES), None)

            if lang.lower() == "output":
                # already consumed by the preceding listing; skip stray ones
                i = j + 1
                continue

            # look ahead for an attached output block
            expected = None
            k = j + 1
            while k < len(lines) and not lines[k].strip():
                k += 1
            if k < len(lines):
                m3 = FENCE_RE.match(lines[k])
                if m3:
                    lang3, _ = parse_info(m3.group("info"))
                    if lang3.lower() == "output":
                        e = k + 1
                        while e < len(lines):
                            m4 = FENCE_RE.match(lines[e])
                            if m4 and not m4.group("info").strip():
                                break
                            e += 1
                        expected = "\n".join(lines[k + 1:e])
                        j = e

            number = None
            if mode in ("run", "check", "expect-error") and chapter_no is not None:
                listing_n += 1
                number = f"{chapter_no}-{listing_n}"
            out.append(render_listing(lang, mode or "literal", tags, body,
                                      number, expected))
            cur_section["text"].append(body[:400])
            i = j + 1
            continue

        # raw HTML block — passthrough verbatim (callouts, orient boxes, details, SVG).
        # Block-level tags only: a paragraph that merely *opens* with <span> or <label>
        # is still a paragraph, and inline() preserves its tags.
        if re.match(r"^\s*<(?:div|section|figure|details|aside|table|svg|ul|ol|nav|"
                    r"blockquote|dl|pre|header|footer|form|math|h[1-6])\b", line, re.I) \
                or re.match(r"^\s*</", line):
            def depth_of(s: str) -> int:
                # Count real tags. Counting bare angle brackets treats a void
                # element written without a slash (<img>, <br>, <hr>, <input>)
                # as an unclosed tag, which inflates the depth forever and makes
                # the passthrough swallow the rest of the chapter.
                d = 0
                for t in TAG_RE.finditer(s):
                    closing, name, selfclose = t.group(1), t.group(2).lower(), t.group(3)
                    if closing:
                        d -= 1
                    elif not selfclose and name not in VOID_ELEMENTS:
                        d += 1
                return d
            block = [line]
            depth_open = depth_of(line)
            j = i + 1
            # consume until a blank line at depth 0 -- but never swallow a fenced
            # block. Exercises and <details> solutions wrap real code, and that
            # code still has to go through the listing renderer.
            while j < len(lines):
                if not lines[j].strip() and depth_open <= 0:
                    break
                fm = FENCE_RE.match(lines[j])
                if fm and fm.group("info").strip():
                    break
                block.append(lines[j])
                depth_open += depth_of(lines[j])
                j += 1
            raw = "\n".join(block)
            out.append(raw)
            cur_section["text"].append(re.sub(r"<[^>]+>", " ", raw)[:400])
            i = j
            continue

        # heading
        hm = re.match(r"^(#{1,6})\s+(.*)$", line)
        if hm:
            level = len(hm.group(1))
            text = hm.group(2).strip().rstrip("#").strip()
            slug = slugify(text, seen_slugs)
            flush_section()
            if level >= 2:
                cur_section["heading"] = text
                cur_section["slug"] = slug
            headings.append(Heading(level, text, slug))
            anchor = (f'<a class="anchor" href="#{slug}" aria-label="Link to this section">'
                      f"#</a>") if level >= 2 else ""
            out.append(f'<h{level} id="{slug}">{inline(text)}{anchor}</h{level}>')
            i += 1
            continue

        # thematic break
        if re.match(r"^\s*(?:\*\s*){3,}$|^\s*(?:-\s*){3,}$|^\s*(?:_\s*){3,}$", line):
            out.append("<hr>")
            i += 1
            continue

        # table
        if "|" in line and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1]):
            header = split_row(line)
            aligns = []
            for cell in split_row(lines[i + 1]):
                left, right = cell.startswith(":"), cell.endswith(":")
                aligns.append("center" if left and right else
                              "right" if right else "left" if left else None)
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].strip() and "|" in lines[j]:
                rows.append(split_row(lines[j]))
                j += 1
            t = ['<div class="table-wrap"><table><thead><tr>']
            for n, cell in enumerate(header):
                a = f' style="text-align:{aligns[n]}"' if n < len(aligns) and aligns[n] else ""
                t.append(f"<th{a}>{inline(cell)}</th>")
            t.append("</tr></thead><tbody>")
            for row in rows:
                t.append("<tr>")
                for n, cell in enumerate(row):
                    a = f' style="text-align:{aligns[n]}"' if n < len(aligns) and aligns[n] else ""
                    t.append(f"<td{a}>{inline(cell)}</td>")
                t.append("</tr>")
                cur_section["text"].append(" ".join(row))
            t.append("</tbody></table></div>")
            out.append("".join(t))
            i = j
            continue

        # blockquote
        if line.lstrip().startswith(">"):
            quoted = []
            j = i
            while j < len(lines) and (lines[j].lstrip().startswith(">") or
                                      (lines[j].strip() and quoted)):
                quoted.append(re.sub(r"^\s*>\s?", "", lines[j]))
                j += 1
            inner, _, _ = render_markdown("\n".join(quoted), chapter_stem, None, seen_slugs)
            out.append(f"<blockquote>{inner}</blockquote>")
            cur_section["text"].append(" ".join(quoted))
            i = j
            continue

        # lists
        lm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if lm:
            block, j = [], i
            while j < len(lines):
                if not lines[j].strip():
                    # a blank line ends the list unless the next line is indented
                    if j + 1 < len(lines) and re.match(r"^\s{2,}\S", lines[j + 1]):
                        block.append("")
                        j += 1
                        continue
                    break
                if re.match(r"^(\s*)([-*+]|\d+[.)])\s+", lines[j]) or \
                        re.match(r"^\s{2,}\S", lines[j]):
                    block.append(lines[j])
                    j += 1
                else:
                    break
            out.append(render_list(block, chapter_stem, seen_slugs))
            cur_section["text"].append(" ".join(
                re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", b) for b in block))
            i = j
            continue

        # paragraph
        para, j = [], i
        while j < len(lines) and lines[j].strip():
            if FENCE_RE.match(lines[j]) or re.match(r"^#{1,6}\s", lines[j]) or \
                    re.match(r"^(\s*)([-*+]|\d+[.)])\s+", lines[j]) or \
                    lines[j].lstrip().startswith(">") or \
                    re.match(r"^\s*<(?:div|section|figure|details|aside|svg)\b", lines[j], re.I):
                break
            para.append(lines[j])
            j += 1
        if para:
            text = " ".join(x.strip() for x in para)
            out.append(f"<p>{inline(text)}</p>")
            cur_section["text"].append(text)
            i = j
        else:
            i += 1

    flush_section()
    return "\n\n".join(out), headings, sections


def render_list(block: list[str], stem: str, seen: dict) -> str:
    """Render one list block, handling nesting by indentation."""
    if not block:
        return ""
    first = re.match(r"^(\s*)([-*+]|\d+[.)])\s+", block[0])
    base_indent = len(first.group(1))
    ordered = bool(re.match(r"\d", first.group(2)))
    tag = "ol" if ordered else "ul"

    items: list[list[str]] = []
    for line in block:
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m and len(m.group(1)) <= base_indent:
            items.append([m.group(3)])
        elif items:
            items[-1].append(line[base_indent:] if len(line) > base_indent else line.strip())
        # a stray line before any item is dropped

    out = [f"<{tag}>"]
    for item in items:
        head = item[0]
        rest = [x for x in item[1:]]
        # a task-list checkbox
        cb = re.match(r"^\[([ xX])\]\s+(.*)$", head)
        prefix = ""
        if cb:
            checked = " checked" if cb.group(1).lower() == "x" else ""
            prefix = f'<input type="checkbox" disabled{checked}> '
            head = cb.group(2)
        nested_src = "\n".join(rest).rstrip()
        if nested_src.strip():
            inner, _, _ = render_markdown(nested_src, stem, None, seen)
            # unwrap a lone paragraph so simple continuations stay inline
            inner = re.sub(r"^<p>(.*)</p>$", r"\1", inner.strip(), flags=re.S) \
                if inner.strip().count("<p>") == 1 and inner.strip().startswith("<p>") \
                and inner.strip().endswith("</p>") else inner
            out.append(f"<li>{prefix}{inline(head)}\n{inner}</li>")
        else:
            out.append(f"<li>{prefix}{inline(head)}</li>")
    out.append(f"</{tag}>")
    return "\n".join(out)


# ── page assembly ─────────────────────────────────────────────────────────────

def head(title: str, book_title: str, css: str, inline_assets: bool,
         extra: str = "") -> str:
    style = f"<style>\n{css}\n</style>" if inline_assets else \
        '<link rel="stylesheet" href="assets/book.css">'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · {html.escape(book_title)}</title>
<script>
(function(){{try{{var t=localStorage.getItem("techbook-theme");
if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t);}}catch(e){{}}}})();
</script>
{style}
{extra}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>"""


def masthead(book_title: str, crumb: str, home: str = "index.html") -> str:
    return f"""<header class="masthead">
  <span class="crumb"><a href="{home}">{html.escape(book_title)}</a> &nbsp;›&nbsp; {html.escape(crumb)}</span>
  <span class="spacer"></span>
  <button id="search-toggle" type="button" aria-label="Search (press /)">Search <kbd>/</kbd></button>
  <button id="theme-toggle" type="button">Auto</button>
</header>
<div id="progress"></div>"""


SEARCH_DIALOG = """<dialog id="search" aria-label="Search the book">
  <input id="search-input" type="search" placeholder="Search the book…" autocomplete="off">
  <ul id="search-results"></ul>
</dialog>"""


def toc_html(chapters: list[Chapter], current: str | None,
             single: bool = False) -> str:
    out = ['<nav class="toc" aria-label="Table of contents"><h2>Contents</h2><ol>']
    for ch in chapters:
        href = f"#{ch.stem}" if single else f"{ch.stem}.html"
        active = (ch.stem == current)
        num = f'<span class="chap-num">{ch.number}</span>' if ch.number else ""
        cur = ' aria-current="page"' if active and not single else ""
        out.append(f'<li><a href="{href}"{cur}>{num}{html.escape(ch.title)}</a>')
        if active or single:
            subs = [h for h in ch.headings if h.level == 2]
            if subs:
                out.append('<ol class="sub">')
                for h in subs:
                    out.append(f'<li><a href="#{h.slug}">{html.escape(h.text)}</a></li>')
                out.append("</ol>")
        out.append("</li>")
    out.append("</ol></nav>")
    return "\n".join(out)


def chapter_page(ch: Chapter, chapters: list[Chapter], book: dict,
                 css: str, js: str) -> str:
    idx = chapters.index(ch)
    prev_ch = chapters[idx - 1] if idx > 0 else None
    next_ch = chapters[idx + 1] if idx < len(chapters) - 1 else None

    rel = []
    if prev_ch:
        rel.append(f'<link rel="prev" href="{prev_ch.stem}.html">')
    if next_ch:
        rel.append(f'<link rel="next" href="{next_ch.stem}.html">')

    nav = ['<nav class="chapter-nav">']
    if prev_ch:
        nav.append(f'<a class="prev" href="{prev_ch.stem}.html">'
                   f'<span class="dir">Previous</span>'
                   f'<span class="t">{html.escape(prev_ch.title)}</span></a>')
    if next_ch:
        nav.append(f'<a class="next" href="{next_ch.stem}.html">'
                   f'<span class="dir">Next</span>'
                   f'<span class="t">{html.escape(next_ch.title)}</span></a>')
    nav.append("</nav>")

    return "\n".join([
        head(ch.title, book["title"], css, False, "\n".join(rel)),
        masthead(book["title"], ch.title),
        '<div class="shell">',
        toc_html(chapters, ch.stem),
        '<main id="main">',
        ch.body_html,
        "\n".join(nav),
        "</main>",
        "</div>",
        SEARCH_DIALOG,
        '<script src="assets/book.js"></script>',
        "</body></html>",
    ])


def index_page(chapters: list[Chapter], book: dict, css: str) -> str:
    items = ['<ol class="contents">']
    for ch in chapters:
        blurb = f'<span class="blurb">{inline(ch.blurb)}</span>' if ch.blurb else ""
        items.append(
            f'<li><a href="{ch.stem}.html">'
            f'<span class="n">{ch.number if ch.number else ""}</span>'
            f'<span class="t">{html.escape(ch.title)}{blurb}</span></a></li>')
    items.append("</ol>")

    front = book.get("front_matter_html", "")
    sub = f'<p class="subtitle">{inline(book["subtitle"])}</p>' if book.get("subtitle") else ""

    return "\n".join([
        head("Contents", book["title"], css, False),
        masthead(book["title"], "Contents"),
        '<div class="shell">',
        toc_html(chapters, None),
        '<main id="main" class="cover">',
        f'<h1>{html.escape(book["title"])}</h1>',
        sub,
        front,
        "<h2>Contents</h2>",
        "\n".join(items),
        f'<p style="margin-top:2.5rem"><a href="book.html">Read as a single page</a> '
        f"— everything in one file, for offline reading, search across the whole book, "
        f"or printing.</p>",
        "</main>",
        "</div>",
        SEARCH_DIALOG,
        '<script src="assets/book.js"></script>',
        "</body></html>",
    ])


def single_page(chapters: list[Chapter], book: dict, css: str, js: str,
                index: list) -> str:
    parts = [
        head(book["title"], book["title"], css, True),
        masthead(book["title"], "Complete", home="#top"),
        '<div class="shell book-single" id="top">',
        toc_html(chapters, None, single=True),
        '<main id="main">',
        f'<h1>{html.escape(book["title"])}</h1>',
    ]
    if book.get("subtitle"):
        parts.append(f'<p class="subtitle">{inline(book["subtitle"])}</p>')
    for ch in chapters:
        parts.append(f'<section class="chapter" id="{ch.stem}">')
        parts.append(ch.body_html)
        parts.append("</section>")
    parts += [
        "</main>", "</div>", SEARCH_DIALOG,
        # A listing containing </script> would otherwise close this tag early and
        # dump raw JSON into the page. Escaping < covers </script>, <!-- and <![CDATA[.
        f"<script>window.__TECHBOOK_INDEX__="
        f"{json.dumps(index).replace('<', chr(92) + 'u003c')};</script>",
        f"<script>\n{js}\n</script>",
        "</body></html>",
    ]
    return "\n".join(parts)


# ── main ──────────────────────────────────────────────────────────────────────

def load_book_meta(book: Path) -> dict:
    meta = {"title": book.name.replace("-", " ").title(), "subtitle": ""}
    y = book / "book.yaml"
    if y.exists():
        # deliberately tiny: top-level `key: value` only, no dependency
        for line in y.read_text().splitlines():
            m = re.match(r"^([a-z_]+):\s*(.+?)\s*$", line)
            if m and m.group(1) in ("title", "subtitle"):
                meta[m.group(1)] = m.group(2).strip().strip("\"'")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", type=Path)
    ap.add_argument("--out", default="build")
    ap.add_argument("--no-single", action="store_true")
    args = ap.parse_args()

    book_dir = args.book.expanduser().resolve()
    src = book_dir / "src"
    if not src.is_dir():
        print(f"error: {src} does not exist", file=sys.stderr)
        return 2

    assets_src = Path(__file__).parent.parent / "assets"
    css = (assets_src / "book.css").read_text()
    js = (assets_src / "book.js").read_text()

    out = book_dir / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(exist_ok=True)
    shutil.copy(assets_src / "book.css", out / "assets" / "book.css")
    shutil.copy(assets_src / "book.js", out / "assets" / "book.js")

    meta = load_book_meta(book_dir)
    chapters: list[Chapter] = []
    seen_slugs: dict = {}

    for path in sorted(src.glob("*.md")):
        if path.name.endswith(".corrected") or path.stem == "SUMMARY":
            continue   # SUMMARY.md is generated output, not a chapter
        text = path.read_text(encoding="utf-8")
        nm = re.match(r"^ch(\d+)", path.stem)
        number = int(nm.group(1)) if nm else None
        tm = re.search(r"^#\s+(.*)$", text, re.M)
        title = tm.group(1).strip() if tm else path.stem
        title = re.sub(r"^Chapter\s+\d+[:.]?\s*", "", title).strip()
        body, headings, sections = render_markdown(text, path.stem, number, seen_slugs)
        # first paragraph as the contents blurb
        blurb = ""
        for s in sections:
            if s["text"]:
                blurb = s["text"][:150].rstrip() + ("…" if len(s["text"]) > 150 else "")
                break
        chapters.append(Chapter(path.stem, number, title, body, headings,
                                sections, blurb))

    if not chapters:
        print(f"error: no chapters in {src}", file=sys.stderr)
        return 2

    # search index
    index = []
    for ch in chapters:
        for s in ch.sections:
            index.append({
                "chapter": ch.title,
                "heading": s["heading"],
                "href": f"{ch.stem}.html" + (f"#{s['slug']}" if s["slug"] else ""),
                "text": s["text"],
            })
    (out / "search.json").write_text(json.dumps(index, indent=0))

    for ch in chapters:
        (out / f"{ch.stem}.html").write_text(chapter_page(ch, chapters, meta, css, js))
    (out / "index.html").write_text(index_page(chapters, meta, css))

    single_index = [dict(e, href="#" + e["href"].split("#")[-1]
                         if "#" in e["href"] else "#" + e["href"].replace(".html", ""))
                    for e in index]
    if not args.no_single:
        (out / "book.html").write_text(single_page(chapters, meta, css, js, single_index))

    # An mdBook-shaped SUMMARY.md next to the sources, so adopting a real toolchain
    # later costs one command rather than a restructure.
    summary = ["# Summary", ""]
    for ch in chapters:
        summary.append(f"- [{ch.title}](./{ch.stem}.md)")
    (src / "SUMMARY.md").write_text("\n".join(summary) + "\n")

    words = sum(len(re.sub(r"<[^>]+>", " ", c.body_html).split()) for c in chapters)
    print(f"Rendered {len(chapters)} chapters · ~{words:,} words → {out}")
    for ch in chapters:
        print(f"  {ch.number or '·':>2}  {ch.title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
