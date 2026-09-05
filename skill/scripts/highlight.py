#!/usr/bin/env python3
"""
highlight.py — render-time syntax highlighting with no dependencies.

Runs inside render.py, so the coloured spans are in the HTML itself: the book
reads the same with JavaScript off, in print, and in the single-file build, and
nothing is fetched from a CDN at read time.

The palette is deliberately small. Following the best-read technical books
(Crafting Interpreters colours eight classes on a grey base; alexwlchan colours
four), only these classes exist:

    c   comment           s   string           n   number / constant
    k   keyword           t   type / builtin   f   name being defined
    d   decorator / attribute / key            p   shell or REPL prompt
    o   output line inside a console listing (dimmed)

A language the tokenizer does not know gets comments, strings and numbers only.
Every token boundary is at a character; no span ever crosses a newline, so the
caller can wrap lines (for `highlight=` line emphasis) after highlighting.

    >>> highlight("x = 1  # one", "python")
    'x = <span class="n">1</span>  <span class="c"># one</span>'
"""

from __future__ import annotations

import html
import re

# ── keyword tables ───────────────────────────────────────────────────────────

KW = {
    "python": """False None True and as assert async await break class continue def
        del elif else except finally for from global if import in is lambda nonlocal
        not or pass raise return try while with yield match case""".split(),
    "javascript": """abstract arguments async await break case catch class const continue
        debugger default delete do else enum export extends false finally for from
        function if implements import in instanceof interface let new null of package
        private protected public return static super switch this throw true try typeof
        undefined var void while with yield as type declare namespace readonly keyof
        satisfies""".split(),
    "rust": """as async await break const continue crate dyn else enum extern false fn
        for if impl in let loop match mod move mut pub ref return self Self static
        struct super trait true type unsafe use where while""".split(),
    "go": """break case chan const continue default defer else fallthrough for func go
        goto if import interface map package range return select struct switch type
        var true false nil iota""".split(),
    "c": """auto break case char const continue default do double else enum extern
        float for goto if inline int long register restrict return short signed sizeof
        static struct switch typedef union unsigned void volatile while _Bool NULL
        true false bool nullptr class namespace template typename public private
        protected virtual override new delete this using try catch throw constexpr
        static_cast dynamic_cast reinterpret_cast const_cast operator explicit
        friend mutable noexcept""".split(),
    "java": """abstract assert boolean break byte case catch char class const continue
        default do double else enum extends final finally float for goto if implements
        import instanceof int interface long native new package private protected
        public return short static strictfp super switch synchronized this throw
        throws transient try var void volatile while true false null record sealed
        permits yield""".split(),
    "bash": """if then else elif fi for while until do done case esac function in
        select time coproc return exit export local readonly declare unset shift
        source alias set unalias trap eval exec break continue""".split(),
    "sql": """select from where and or not in is null as join left right inner outer
        full on group by order having limit offset insert into values update set
        delete create table index view drop alter add column primary key foreign
        references unique default check constraint distinct union all exists between
        like case when then else end begin commit rollback transaction with
        recursive returning explain analyze vacuum if""".split(),
    "ruby": """alias and begin break case class def defined? do else elsif end ensure
        false for if in module next nil not or redo rescue retry return self super
        then true undef unless until when while yield require require_relative
        attr_reader attr_writer attr_accessor puts print p lambda proc""".split(),
}
KW["typescript"] = KW["javascript"]
KW["cpp"] = KW["c"]
KW["kotlin"] = KW["java"] + "fun val when object data sealed companion".split()

TYPES = {
    "python": """int float str bytes bool list dict set tuple frozenset object type
        range enumerate zip map filter len print open input isinstance issubclass
        hasattr getattr setattr sorted reversed sum min max abs round any all iter
        next repr id hash super property staticmethod classmethod Exception
        ValueError TypeError KeyError IndexError RuntimeError StopIteration
        RecursionError AttributeError NameError ZeroDivisionError AssertionError
        NotImplementedError OSError FileNotFoundError ImportError""".split(),
    "javascript": """Array Object String Number Boolean Map Set Promise Symbol Math
        JSON Date RegExp Error TypeError RangeError console document window
        parseInt parseFloat setTimeout setInterval fetch require module process
        Uint8Array ArrayBuffer BigInt""".split(),
    "rust": """i8 i16 i32 i64 i128 isize u8 u16 u32 u64 u128 usize f32 f64 bool char
        str String Vec Option Some None Result Ok Err Box Rc Arc RefCell Cell HashMap
        HashSet BTreeMap VecDeque Iterator IntoIterator Default Clone Copy Debug
        Display PartialEq Eq PartialOrd Ord Hash Send Sync Drop Fn FnMut FnOnce
        println print eprintln format vec assert assert_eq panic todo unimplemented
        dbg matches write writeln""".split(),
    "go": """bool byte rune int int8 int16 int32 int64 uint uint8 uint16 uint32 uint64
        uintptr float32 float64 complex64 complex128 string error any append cap
        close copy delete len make new panic print println recover""".split(),
    "c": """size_t ssize_t uint8_t uint16_t uint32_t uint64_t int8_t int16_t int32_t
        int64_t FILE printf fprintf sprintf snprintf scanf malloc calloc realloc free
        memcpy memset strlen strcmp strcpy std string vector map unordered_map
        cout cin endl""".split(),
    "java": """String Integer Long Double Float Boolean Character Object List ArrayList
        Map HashMap Set HashSet Optional System Math StringBuilder Exception
        RuntimeException Thread Runnable""".split(),
    "bash": """echo printf cd ls cat grep sed awk find xargs sort uniq head tail wc
        chmod chown mkdir rm cp mv touch curl wget tar ssh git python python3 pip
        node npm cargo rustc go make docker test read true false""".split(),
    "ruby": """Integer Float String Array Hash Symbol Proc Struct Kernel Object
        Comparable Enumerable""".split(),
}
TYPES["typescript"] = TYPES["javascript"] + "string number boolean any unknown never void Record Partial".split()
TYPES["cpp"] = TYPES["c"]
TYPES["kotlin"] = TYPES["java"]

ALIASES = {
    "py": "python", "python3": "python", "js": "javascript", "mjs": "javascript",
    "jsx": "javascript", "ts": "typescript", "tsx": "typescript", "rs": "rust",
    "golang": "go", "sh": "bash", "shell": "bash", "zsh": "bash", "console": "console",
    "terminal": "console", "text": "text", "txt": "text", "plain": "text",
    "output": "text", "h": "c", "cc": "cpp", "cxx": "cpp", "c++": "cpp", "hpp": "cpp",
    "yml": "yaml", "htm": "html", "xml": "html", "svg": "html", "rb": "ruby",
    "kt": "kotlin", "jsonc": "json", "json5": "json", "postgres": "sql",
    "postgresql": "sql", "sqlite": "sql", "mysql": "sql", "dockerfile": "bash",
    "makefile": "bash", "diff": "diff", "patch": "diff",
}

NUMBER = r"(?<![\w.])(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?)(?:[a-zA-Z_][a-zA-Z0-9_]*)?(?![\w.])"
IDENT = r"[A-Za-z_][A-Za-z0-9_]*"

# Per-language token grammars. Order matters: the first alternative to match
# at a position wins. Each entry is (class, regex). `None` class = plain text.
DQ = r'"(?:\\.|[^"\\\n])*"?'
SQ = r"'(?:\\.|[^'\\\n])*'?"
BQ = r"`(?:\\.|[^`\\])*`?"

GRAMMARS: dict[str, list[tuple[str | None, str]]] = {
    "python": [
        ("c", r"#[^\n]*"),
        ("s", r"(?i:[rbuf]{0,2})(?:\"\"\"[\s\S]*?(?:\"\"\"|$)|'''[\s\S]*?(?:'''|$))"),
        ("s", r"(?i:[rbuf]{0,2})(?:" + DQ + "|" + SQ + ")"),
        ("d", r"@" + IDENT + r"(?:\." + IDENT + r")*"),
        ("p", r"^(?:>>>|\.\.\.)(?= |$)"),
        ("def", r"\b(?:def|class)\s+" + IDENT),
        ("n", NUMBER),
        ("w", IDENT),
    ],
    "javascript": [
        ("c", r"//[^\n]*|/\*[\s\S]*?(?:\*/|$)"),
        ("s", BQ + "|" + DQ + "|" + SQ),
        ("s", r"(?<=[=(,:;!&|?{}\[])\s*/(?:\\.|\[[^\]]*\]|[^/\\\n\[])+/[gimsuyd]*"),
        ("d", r"@" + IDENT),
        ("def", r"\b(?:function|class|interface|type|enum)\s+" + IDENT),
        ("n", NUMBER),
        ("w", IDENT + r"\$?|\$" + IDENT),
    ],
    "rust": [
        ("c", r"//[^\n]*|/\*[\s\S]*?(?:\*/|$)"),
        ("s", r"b?r#*\"[\s\S]*?\"#*|b?" + DQ + r"|b?'(?:\\.|[^'\\\n])'"),
        ("d", r"#!?\[[^\]\n]*\]"),
        ("def", r"\b(?:fn|struct|enum|trait|type|mod|union)\s+" + IDENT),
        ("t", r"\b[A-Z][A-Za-z0-9_]*\b"),
        ("n", NUMBER),
        ("w", IDENT + r"!?|'" + IDENT),
    ],
    "go": [
        ("c", r"//[^\n]*|/\*[\s\S]*?(?:\*/|$)"),
        ("s", BQ + "|" + DQ + "|" + SQ),
        ("def", r"\b(?:func|type)\s+(?:\([^)]*\)\s*)?" + IDENT),
        ("n", NUMBER),
        ("w", IDENT),
    ],
    "c": [
        ("c", r"//[^\n]*|/\*[\s\S]*?(?:\*/|$)"),
        ("d", r"^\s*#\s*\w+(?:[ \t]+<[^>\n]*>)?"),
        ("s", DQ + "|" + SQ),
        ("def", r"\b(?:struct|union|enum|class|namespace)\s+" + IDENT),
        ("n", NUMBER),
        ("w", IDENT),
    ],
    "java": [
        ("c", r"//[^\n]*|/\*[\s\S]*?(?:\*/|$)"),
        ("s", r"\"\"\"[\s\S]*?(?:\"\"\"|$)|" + DQ + "|" + SQ),
        ("d", r"@" + IDENT),
        ("def", r"\b(?:class|interface|enum|record)\s+" + IDENT),
        ("t", r"\b[A-Z][A-Za-z0-9_]*\b"),
        ("n", NUMBER),
        ("w", IDENT),
    ],
    "bash": [
        ("c", r"(?<![\$\\])#[^\n]*"),
        ("s", DQ + "|" + SQ),
        ("d", r"\$(?:\{[^}\n]*\}|" + IDENT + r"|[@#?$!*0-9])"),
        ("def", r"\b(?:function)\s+" + IDENT + r"|" + IDENT + r"(?=\s*\(\)\s*\{)"),
        ("n", NUMBER),
        ("w", IDENT),
    ],
    "sql": [
        ("c", r"--[^\n]*|/\*[\s\S]*?(?:\*/|$)"),
        ("s", SQ),
        ("n", NUMBER),
        ("w", IDENT),
    ],
    "ruby": [
        ("c", r"#[^\n]*"),
        ("s", DQ + "|" + SQ + r"|:" + IDENT),
        ("d", r"@@?" + IDENT + r"|\$" + IDENT),
        ("def", r"\b(?:def|class|module)\s+" + IDENT + r"(?:[?!])?"),
        ("t", r"\b[A-Z][A-Za-z0-9_]*\b"),
        ("n", NUMBER),
        ("w", IDENT + r"[?!]?"),
    ],
    "json": [
        ("d", r'"(?:\\.|[^"\\\n])*"(?=\s*:)'),
        ("s", DQ),
        ("k", r"\b(?:true|false|null)\b"),
        ("n", NUMBER),
    ],
    "yaml": [
        ("c", r"(?<![\$\\])#[^\n]*"),
        ("d", r"^\s*-?\s*[A-Za-z0-9_.\-\"']+(?=\s*:(?:\s|$))"),
        ("s", DQ + "|" + SQ),
        ("k", r"\b(?:true|false|null|yes|no|on|off|~)\b"),
        ("n", NUMBER),
        ("t", r"&" + IDENT + r"|\*" + IDENT + r"|!!" + IDENT),
    ],
    "toml": [
        ("c", r"#[^\n]*"),
        ("t", r"^\s*\[\[?[^\]\n]*\]\]?"),
        ("d", r"^\s*[A-Za-z0-9_.\-\"']+(?=\s*=)"),
        ("s", r"\"\"\"[\s\S]*?(?:\"\"\"|$)|'''[\s\S]*?(?:'''|$)|" + DQ + "|" + SQ),
        ("k", r"\b(?:true|false)\b"),
        ("n", NUMBER + r"|\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?"),
    ],
    "css": [
        ("c", r"/\*[\s\S]*?(?:\*/|$)"),
        ("s", DQ + "|" + SQ),
        ("k", r"@[a-zA-Z-]+"),
        ("d", r"^\s*[a-zA-Z-]+(?=\s*:)|--[a-zA-Z0-9-]+"),
        ("n", r"#[0-9a-fA-F]{3,8}\b|" + NUMBER + r"(?:%|px|rem|em|ch|vw|vh|ms|s|deg|fr)?"),
        ("t", r"^[^{\n]+(?=\s*\{)"),
    ],
    "html": [
        ("c", r"<!--[\s\S]*?(?:-->|$)"),
        ("k", r"</?[A-Za-z][\w:-]*|/?>"),
        ("d", r"\b[A-Za-z_:][\w:.-]*(?==)"),
        ("s", DQ + "|" + SQ),
    ],
    "diff": [
        ("c", r"^(?:diff|index|---|\+\+\+|@@)[^\n]*"),
        ("s", r"^\+[^\n]*"),
        ("n", r"^-[^\n]*"),
    ],
    "text": [],
}
GRAMMARS["typescript"] = GRAMMARS["javascript"]
GRAMMARS["cpp"] = GRAMMARS["c"]
GRAMMARS["kotlin"] = GRAMMARS["java"]
GENERIC = [
    ("c", r"//[^\n]*|/\*[\s\S]*?(?:\*/|$)|#[^\n]*|--[^\n]*"),
    ("s", DQ + "|" + SQ),
    ("n", NUMBER),
    ("w", IDENT),
]

_COMPILED: dict[str, re.Pattern] = {}


def _grammar(lang: str) -> re.Pattern | None:
    if lang in _COMPILED:
        return _COMPILED[lang]
    rules = GRAMMARS.get(lang, GENERIC)
    if not rules:
        _COMPILED[lang] = None
        return None
    parts = [f"(?P<{cls}_{i}>{rx})" for i, (cls, rx) in enumerate(rules)]
    pat = re.compile("|".join(parts), re.M)
    _COMPILED[lang] = pat
    return pat


def canonical(lang: str) -> str:
    lang = (lang or "").strip().lower()
    return ALIASES.get(lang, lang)


def _span(cls: str, text: str) -> str:
    """Escape and wrap, never letting a span cross a newline."""
    esc = html.escape(text, quote=False)
    if "\n" not in esc:
        return f'<span class="{cls}">{esc}</span>'
    return "\n".join(f'<span class="{cls}">{ln}</span>' if ln else ""
                     for ln in esc.split("\n"))


def _code(text: str, lang: str) -> str:
    pat = _grammar(lang)
    if pat is None:
        return html.escape(text, quote=False)
    kws = set(KW.get(lang, ()))
    types = set(TYPES.get(lang, ()))
    ci = lang == "sql"
    out: list[str] = []
    pos = 0
    for m in pat.finditer(text):
        if m.start() > pos:
            out.append(html.escape(text[pos:m.start()], quote=False))
        cls = m.lastgroup.rsplit("_", 1)[0]
        tok = m.group(0)
        if cls == "w":
            probe = tok.lower() if ci else tok
            if probe in kws:
                out.append(_span("k", tok))
            elif tok in types or (lang == "rust" and tok.endswith("!")):
                out.append(_span("t", tok))
            else:
                out.append(html.escape(tok, quote=False))
        elif cls == "def":
            # keyword, whitespace, then the name being introduced
            m2 = re.match(r"^(\S+)(\s+(?:\([^)]*\)\s*)?)(.+)$", tok, re.S)
            if m2:
                out.append(_span("k", m2.group(1)))
                out.append(html.escape(m2.group(2), quote=False))
                out.append(_span("f", m2.group(3)))
            else:
                out.append(_span("f", tok))
        else:
            out.append(_span(cls, tok))
        pos = m.end()
    if pos < len(text):
        out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


PROMPT = re.compile(r"^(\s*)(\$|%|>|❯|#|PS>|>>>|\.\.\.)(\s)(.*)$")


def highlight(text: str, lang: str) -> str:
    """Return escaped HTML for `text`, with token spans, no span crossing a line."""
    lang = canonical(lang)
    if lang in ("text", "output", ""):
        return html.escape(text, quote=False)

    if lang == "console":
        # `$ command` lines are shell; anything else is output and is dimmed.
        out = []
        for ln in text.split("\n"):
            m = PROMPT.match(ln)
            if m and m.group(2) not in (">>>", "..."):
                out.append(html.escape(m.group(1)) + _span("p", m.group(2)) + m.group(3)
                           + _code(m.group(4), "bash"))
            elif m:
                out.append(html.escape(m.group(1)) + _span("p", m.group(2)) + m.group(3)
                           + _code(m.group(4), "python"))
            elif ln.strip():
                out.append(_span("o", ln))
            else:
                out.append("")
        return "\n".join(out)

    if lang == "bash":
        # A shell listing whose lines all start with `$ ` is a session, not a script.
        lines = text.split("\n")
        prompted = [ln for ln in lines if ln.strip()]
        if prompted and all(PROMPT.match(ln) and PROMPT.match(ln).group(2) in ("$", "%", "❯")
                            for ln in prompted):
            out = []
            for ln in lines:
                m = PROMPT.match(ln)
                out.append((html.escape(m.group(1)) + _span("p", m.group(2)) + m.group(3)
                            + _code(m.group(4), "bash")) if m else "")
            return "\n".join(out)

    return _code(text, lang)


if __name__ == "__main__":
    import doctest
    import sys
    fails, _ = doctest.testmod()
    if len(sys.argv) > 2:
        print(highlight(open(sys.argv[1]).read(), sys.argv[2]))
    sys.exit(1 if fails else 0)
