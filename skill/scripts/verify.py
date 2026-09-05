#!/usr/bin/env python3
"""
verify.py — the code gate for a techbook project.

Walks src/*.md, extracts every fenced block, enforces the block contract, executes
what should be executed inside a seatbelt sandbox, diffs real output against the
book's claimed output, and refuses to let a book publish with unverified code.

On output drift it never edits the book in place. It writes <chapter>.md.corrected
and prints a diff; `--promote` is the separate, deliberate step that accepts them.

Usage:
    verify.py <book-dir> [--strict] [--promote] [--no-cache] [--only chNN] [--json]

Exit codes: 0 all good · 1 verification failures · 2 lint errors · 3 bad invocation
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:                      # stdlib from 3.11; absence is reported, never swallowed
    import tomllib
except ImportError:       # pragma: no cover - only on 3.10 and older
    tomllib = None

# ── The block contract ────────────────────────────────────────────────────────

MODES = {"run", "check", "expect-error", "literal", "norun"}

# Languages we know how to execute or typecheck. A block in one of these MUST
# declare a mode -- an untagged block is a lint error, never a silent skip.
RUNNABLE_LANGS = {
    "python": "python", "py": "python", "python3": "python",
    "javascript": "node", "js": "node", "node": "node", "mjs": "node",
    "typescript": "node", "ts": "node",
    "bash": "bash", "sh": "bash", "shell": "bash", "zsh": "bash",
    "rust": "rust", "rs": "rust",
    "go": "go",
}

# Fences that are prose furniture, not code. They need no mode tag.
PROSE_LANGS = {"output", "text", "", "console", "diff", "ascii"}

VALID_MODIFIERS = {
    # execution
    "env", "file", "net", "slow", "timeout", "deps", "nondet", "why", "expect",
    # presentation only -- consumed by render.py, ignored here
    "caption", "highlight", "filename",
}

DEFAULT_TIMEOUT = 30


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Block:
    chapter: str          # file stem, e.g. "ch03-scanning"
    path: Path
    line: int             # 1-indexed line of the opening fence
    end_line: int         # 1-indexed line of the closing fence
    lang: str             # as written in the info string
    mode: str
    tags: dict
    body: str
    expected: str | None = None       # body of the following ```output block
    expected_span: tuple | None = None  # (start_line, end_line) of that block
    # filled in by execution
    status: str = "pending"
    actual: str = ""
    stderr: str = ""
    exit_code: int | None = None
    note: str = ""
    cached: bool = False

    @property
    def runner(self) -> str | None:
        return RUNNABLE_LANGS.get(self.lang.lower())

    @property
    def env(self) -> str:
        return self.tags.get("env") or f"__solo_{self.chapter}_{self.line}"

    @property
    def ident(self) -> str:
        return f"{self.chapter}:{self.line}"


@dataclass
class Report:
    lint_errors: list = field(default_factory=list)
    blocks: list = field(default_factory=list)
    drifted: dict = field(default_factory=dict)   # chapter -> corrected text


# ── Parsing ───────────────────────────────────────────────────────────────────

FENCE_RE = re.compile(r"^(?P<indent>\s{0,3})(?P<fence>```+|~~~+)(?P<info>.*)$")


def parse_info(info: str) -> tuple[str, dict]:
    """Split a fence info string into (lang, tags).

    Handles  python run env=ch1 timeout=10  and  literal why="config sketch".
    """
    info = info.strip()
    if not info:
        return "", {}
    # tokenize respecting quotes
    tokens, cur, quote = [], "", None
    for chunk in info:
        if quote:
            if chunk == quote:
                quote = None
            else:
                cur += chunk
        elif chunk in "\"'":
            quote = chunk
        elif chunk.isspace():
            if cur:
                tokens.append(cur)
                cur = ""
        else:
            cur += chunk
    if cur:
        tokens.append(cur)
    if not tokens:
        return "", {}
    lang, rest = tokens[0], tokens[1:]
    tags = {}
    for tok in rest:
        if "=" in tok:
            k, _, v = tok.partition("=")
            tags[k] = v
        else:
            tags[tok] = True
    return lang, tags


def parse_chapter(path: Path) -> tuple[list[Block], list[str]]:
    """Extract blocks from one markdown file. Returns (blocks, lint_errors)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[Block] = []
    errors: list[str] = []
    stem = path.stem

    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        fence = m.group("fence")
        lang, tags = parse_info(m.group("info"))
        start = i
        # find the closing fence of at least the same length
        j = i + 1
        while j < len(lines):
            m2 = FENCE_RE.match(lines[j])
            if m2 and m2.group("fence")[0] == fence[0] and len(m2.group("fence")) >= len(fence) \
                    and not m2.group("info").strip():
                break
            j += 1
        if j >= len(lines):
            errors.append(f"{stem}:{start+1}: unterminated fence")
            break
        body = "\n".join(lines[start + 1:j])

        modes_present = [t for t in tags if t in MODES]
        lang_l = lang.lower()

        if lang_l == "output":
            # Attach to the block immediately above: only blank lines may sit
            # between them. render.py uses the same rule, so what verify.py
            # checks is exactly what the reader sees paired on the page.
            attached = False
            if blocks and blocks[-1].mode in ("run", "expect-error"):
                b = blocks[-1]
                gap = lines[b.end_line:start]
                if all(not ln.strip() for ln in gap):
                    if b.expected is not None:
                        errors.append(
                            f"{stem}:{start+1}: second ```output block for the block at line {b.line}")
                    b.expected = body
                    b.expected_span = (start + 1, j + 1)
                    attached = True
            if not attached:
                errors.append(
                    f"{stem}:{start+1}: ```output block must immediately follow a `run` or "
                    f"`expect-error` block (blank lines only in between)")
            i = j + 1
            continue

        if lang_l in PROSE_LANGS:
            i = j + 1
            continue

        # From here on the block is code-shaped and must declare a mode.
        if len(modes_present) > 1:
            errors.append(
                f"{stem}:{start+1}: block declares multiple modes ({', '.join(modes_present)}); "
                f"exactly one is allowed")
            i = j + 1
            continue

        if not modes_present:
            known = lang_l in RUNNABLE_LANGS
            errors.append(
                f"{stem}:{start+1}: ```{lang} block has no mode tag. "
                + (f"Add one of: run, check, expect-error, norun, or literal why=\"...\"."
                   if known else
                   f"`{lang}` is not an executable language here, so tag it "
                   f"`literal why=\"...\"` to say why it is prose.")
            )
            i = j + 1
            continue

        mode = modes_present[0]
        unknown = set(tags) - MODES - VALID_MODIFIERS
        if unknown:
            errors.append(
                f"{stem}:{start+1}: unknown tag(s) {', '.join(sorted(unknown))}")

        if mode == "literal" and not isinstance(tags.get("why"), str):
            errors.append(
                f"{stem}:{start+1}: `literal` requires why=\"...\" so it cannot become "
                f"a dumping ground for code nobody checked")

        if mode == "norun" and not isinstance(tags.get("why"), str):
            errors.append(
                f"{stem}:{start+1}: `norun` requires why=\"...\" -- the reason is printed "
                f"in the publish report so the skip stays visible")

        if mode in ("run", "check", "expect-error") and lang_l not in RUNNABLE_LANGS:
            errors.append(
                f"{stem}:{start+1}: mode `{mode}` on unsupported language `{lang}`. "
                f"Supported: {', '.join(sorted(set(RUNNABLE_LANGS)))}")

        if "timeout" in tags and not (isinstance(tags["timeout"], str) and tags["timeout"].isdigit()):
            errors.append(
                f"{stem}:{start+1}: timeout must be a number of seconds, e.g. timeout=30")

        if "env" in tags and lang_l in RUNNABLE_LANGS and \
                RUNNABLE_LANGS.get(lang_l) not in SENTINEL_EMIT:
            errors.append(
                f"{stem}:{start+1}: env= is only supported for "
                f"{', '.join(sorted(SENTINEL_EMIT))} listings; `{lang}` blocks run in isolation")

        nondet = tags.get("nondet")
        if nondet not in (None, "output", "command"):
            errors.append(
                f"{stem}:{start+1}: nondet must be `output` or `command`, got `{nondet}`")

        blocks.append(Block(
            chapter=stem, path=path, line=start + 1, end_line=j + 1,
            lang=lang, mode=mode, tags=tags, body=body,
        ))
        i = j + 1

    return blocks, errors


# ── Dependency allowlist gate ────────────────────────────────────────────────
# LLM-suggested packages are hallucinated ~20% of the time and the fabrications
# recur, which makes them predictable slopsquatting targets. So we resolve every
# import against a pinned manifest *before* running anything, and we never
# install to find out.

PY_IMPORT_RE = re.compile(r"^\s*(?:import\s+([\w.]+)|from\s+([\w.]+)\s+import)", re.M)
JS_IMPORT_RE = re.compile(
    r"""(?:require\(\s*['"]([^'"]+)['"]\s*\)|from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"])""")


def python_stdlib() -> set[str]:
    return set(getattr(sys, "stdlib_module_names", set())) | {"__future__"}


def node_builtins() -> set[str]:
    try:
        out = subprocess.run(
            ["node", "-e", "console.log(require('module').builtinModules.join('\\n'))"],
            capture_output=True, text=True, timeout=15)
        return set(out.stdout.split())
    except Exception:
        return set()


class ManifestError(Exception):
    """The dependency manifest could not be read. Never swallowed: an unreadable
    manifest silently pins nothing, which fails every third-party import with a
    message about the wrong thing."""


def pinned_python(book: Path) -> set[str]:
    names: set[str] = set()
    pyproject = book / "verify" / "python" / "pyproject.toml"
    if not pyproject.exists():
        return names

    if tomllib is None:
        raise ManifestError(
            f"reading {pyproject.relative_to(book)} needs Python 3.11+ for tomllib, "
            f"but this is Python {sys.version_info.major}.{sys.version_info.minor}. "
            f"Without it nothing can be pinned, so every third-party import would "
            f"fail the dependency gate for the wrong reason. Re-run on 3.11+.")
    try:
        data = tomllib.loads(pyproject.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ManifestError(f"{pyproject.relative_to(book)} is not valid TOML: {e}") from e
    except OSError as e:
        raise ManifestError(f"{pyproject.relative_to(book)} could not be read: {e}") from e

    deps = data.get("project", {}).get("dependencies", []) or []
    for d in deps:
        names.add(re.split(r"[<>=!~\[; ]", d.strip())[0].replace("-", "_").lower())
    return names


def pinned_node(book: Path) -> set[str]:
    pkg = book / "verify" / "node" / "package.json"
    if not pkg.exists():
        return set()
    try:
        data = json.loads(pkg.read_text())
    except json.JSONDecodeError as e:
        raise ManifestError(f"{pkg.relative_to(book)} is not valid JSON: {e}") from e
    except OSError as e:
        raise ManifestError(f"{pkg.relative_to(book)} could not be read: {e}") from e
    names = set()
    for key in ("dependencies", "devDependencies"):
        names |= set(data.get(key, {}) or {})
    return names


def dep_gate(blocks: list[Block], book: Path) -> list[str]:
    errors = []
    try:
        py_ok = python_stdlib() | pinned_python(book)
        node_ok = node_builtins() | pinned_node(book)
    except ManifestError as e:
        # Report and stop. Continuing with an empty allowlist would blame every
        # third-party import for a problem that is entirely in the manifest.
        return [f"dependency manifest: {e}"]
    local_py = {p.stem for p in (book / "code").rglob("*.py")} if (book / "code").exists() else set()

    for b in blocks:
        if b.mode not in ("run", "check", "expect-error"):
            continue
        if b.runner == "python":
            for m in PY_IMPORT_RE.finditer(b.body):
                mod = (m.group(1) or m.group(2)).split(".")[0]
                if mod.lower() not in py_ok and mod not in local_py and not mod.startswith("_"):
                    errors.append(
                        f"{b.ident}: imports `{mod}`, which is neither in the standard library "
                        f"nor pinned in verify/python/pyproject.toml. If the package is real, "
                        f"pin it deliberately; if it is not, this is exactly the failure the "
                        f"gate exists to catch.")
        elif b.runner == "node":
            for m in JS_IMPORT_RE.finditer(b.body):
                spec = m.group(1) or m.group(2) or m.group(3)
                if spec.startswith((".", "/", "node:")):
                    continue
                pkg_name = "/".join(spec.split("/")[:2]) if spec.startswith("@") \
                    else spec.split("/")[0]
                if pkg_name not in node_ok:
                    errors.append(
                        f"{b.ident}: imports `{pkg_name}`, not a node builtin and not pinned "
                        f"in verify/node/package.json.")
    return errors


# ── code/ must agree with the book ───────────────────────────────────────────
# Crafting Interpreters' guarantee: the prose cannot drift from code that really
# compiles, because the snippets come from the same source the test suite runs.
# We keep the block as the author's working surface and enforce the pairing, so
# `file=` stops being decoration on the listing header.

def code_file_gate(blocks: list[Block], book: Path, sync: bool) -> list[str]:
    errors: list[str] = []
    for b in blocks:
        decl = b.tags.get("file") or b.tags.get("filename")
        if not isinstance(decl, str) or not decl:
            continue
        path = (book / decl.split("#")[0]).resolve()
        try:
            path.relative_to(book)
        except ValueError:
            errors.append(f"{b.ident}: file={decl} escapes the book directory")
            continue

        if sync:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(b.body.rstrip() + "\n", encoding="utf-8")
            continue

        if not path.exists():
            errors.append(
                f"{b.ident}: declares file={decl}, but that file does not exist. "
                f"Either write it (verify.py --sync-code does this) or drop the tag "
                f"-- a filename header the reader cannot open is a promise the book "
                f"does not keep.")
            continue

        on_disk = path.read_text(encoding="utf-8").strip()
        if on_disk != b.body.strip():
            errors.append(
                f"{b.ident}: the listing and {decl} have diverged. The book must not "
                f"show code that differs from the file it names; reconcile them, or "
                f"re-run with --sync-code if the block is correct.")
    return errors


# ── Output normalisation ──────────────────────────────────────────────────────

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
NORMALISERS = [
    (re.compile(r"/(?:private/)?(?:tmp|var/folders)/[^\s'\"]+"), "<TMP>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<TIME>"),
    (re.compile(r"0x[0-9a-fA-F]{6,}"), "<ADDR>"),
    (re.compile(r"\b\d+(?:\.\d+)?\s?(?:ms|µs|us|ns|seconds?|secs?|s)\b"), "<DUR>"),
    (re.compile(r"(?m)^\s*File \"[^\"]+\", line \d+"), 'File "<PATH>", line <N>'),
]


def normalise(text: str) -> str:
    text = ANSI_RE.sub("", text)
    for pat, repl in NORMALISERS:
        text = pat.sub(repl, text)
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


# ── Execution ─────────────────────────────────────────────────────────────────

SENTINEL = "__TECHBOOK_BLOCK_BOUNDARY_9f3a__"

SENTINEL_EMIT = {
    "python": f'\nprint("{SENTINEL}")\n',
    "node": f'\nconsole.log("{SENTINEL}");\n',
    "bash": f'\necho "{SENTINEL}"\n',
}

SANDBOX_AVAILABLE = bool(shutil.which("sandbox-exec"))

SEATBELT = """(version 1)
(deny default)
(allow process-exec process-fork signal)
(allow sysctl-read mach-lookup)
(allow file-read* file-read-metadata)
(allow file-write* (subpath "{work}"))
(allow file-write-data (literal "/dev/null") (literal "/dev/stdout") (literal "/dev/stderr"))
{network}
"""


def build_profile(work: Path, allow_net: bool) -> str:
    return SEATBELT.format(
        work=str(work.resolve()),
        network="(allow network*)" if allow_net else "(deny network*)",
    )


def env_prefix(block: Block, all_blocks: list[Block]) -> str:
    """All prior executed blocks sharing this env, concatenated in document order.

    A book's listings are a narrative, not independent units -- chapter 3's snippet
    usually assumes the function defined in chapter 2's. Only `run` blocks join the
    prefix: `check` never executed, and `expect-error` deliberately blew up.
    """
    if "env" not in block.tags:
        return ""
    parts = []
    for b in all_blocks:
        if b is block:
            break
        if b.tags.get("env") == block.tags["env"] and b.mode == "run" and b.runner == block.runner:
            parts.append(b.body)
    return "\n".join(parts)


def cache_key(block: Block, prefix: str, book: Path) -> str:
    h = hashlib.sha256()
    h.update(block.body.encode())
    h.update(prefix.encode())
    h.update(block.mode.encode())
    h.update(str(sorted(block.tags.items())).encode())
    h.update(str(block.runner).encode())
    for manifest in ("verify/python/pyproject.toml", "verify/node/package.json"):
        p = book / manifest
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:24]


def run_block(block: Block, all_blocks: list[Block], book: Path,
              use_cache: bool) -> None:
    runner = block.runner
    prefix = env_prefix(block, all_blocks)

    if block.mode in ("literal", "norun"):
        block.status = "skipped" if block.mode == "literal" else "unverified"
        block.note = str(block.tags.get("why", ""))
        return

    if block.tags.get("nondet") == "command" and not os.environ.get("VERIFY_NONDET"):
        block.status = "unverified"
        block.note = "nondet=command; set VERIFY_NONDET=1 to run"
        return

    key = cache_key(block, prefix, book)
    cache_dir = book / ".verify" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{key}.json"

    data = None
    if use_cache and cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            block.actual, block.stderr, block.exit_code = data["out"], data["err"], data["code"]
            block.cached = True
        except (ValueError, KeyError, TypeError):
            data = None                      # corrupt entry: fall through and re-run
    if data is None:
        out, err, code = execute(block, prefix, book)
        block.actual, block.stderr, block.exit_code = out, err, code
        # Environmental failures are not results. Caching a missing toolchain or a
        # timeout would make installing the toolchain look like it changed nothing.
        environmental = code in (124, 127) or ("denied" in err.lower() and "sandbox" in err.lower())
        if not environmental:
            tmp = cache_file.with_suffix(".tmp")
            tmp.write_text(json.dumps({"out": out, "err": err, "code": code}))
            os.replace(tmp, cache_file)

    judge(block)


def execute(block: Block, prefix: str, book: Path) -> tuple[str, str, int]:
    runner = block.runner
    work = book / ".verify" / "work"
    work.mkdir(parents=True, exist_ok=True)
    timeout = int(block.tags.get("timeout") or DEFAULT_TIMEOUT)

    with tempfile.TemporaryDirectory(dir=work) as td:
        tmp = Path(td)
        sentinel = SENTINEL_EMIT.get(runner, "")
        source = (prefix + sentinel + block.body) if prefix else block.body

        if runner == "python":
            f = tmp / "snippet.py"
            f.write_text(source)
            interp = python_interpreter(book)
            cmd = ([str(interp), "-X", "utf8", str(f)] if block.mode != "check"
                   else [str(interp), "-m", "py_compile", str(f)])
        elif runner == "node":
            f = tmp / "snippet.mjs"
            f.write_text(source)
            cmd = ["node", str(f)] if block.mode != "check" else ["node", "--check", str(f)]
        elif runner == "bash":
            f = tmp / "snippet.sh"
            f.write_text(source)
            cmd = ["bash", str(f)] if block.mode != "check" else ["bash", "-n", str(f)]
        elif runner == "rust":
            f = tmp / "snippet.rs"
            body = source if "fn main" in source else f"fn main() {{\n{source}\n}}"
            f.write_text(body)
            binp = tmp / "snippet"
            comp = sandboxed(["rustc", "--edition", "2021", "-o", str(binp), str(f)],
                             block, tmp, timeout, book)
            if comp[2] != 0 or block.mode == "check":
                return comp
            cmd = [str(binp)]
        elif runner == "go":
            f = tmp / "snippet.go"
            f.write_text(source)
            cmd = ["go", "run", str(f)] if block.mode != "check" else ["go", "vet", str(f)]
        else:
            return "", f"no runner for language `{block.lang}`", 127

        return sandboxed(cmd, block, tmp, timeout, book)


def python_interpreter(book: Path) -> Path:
    """Prefer the project venv. It is materialised OUTSIDE the sandbox by
    `verify.py --setup`, because `uv run` panics under a minimal seatbelt profile
    (astral-sh/uv#16664). Inside the sandbox we only ever exec the interpreter."""
    venv = book / "verify" / "python" / ".venv" / "bin" / "python3"
    return venv if venv.exists() else Path(sys.executable)


def sandboxed(cmd: list[str], block: Block, cwd: Path, timeout: int,
              book: Path | None = None) -> tuple[str, str, int]:
    allow_net = bool(block.tags.get("net"))
    profile = build_profile(cwd, allow_net)
    prof_file = cwd / "profile.sb"
    prof_file.write_text(profile)

    full = cmd
    if SANDBOX_AVAILABLE:
        full = ["sandbox-exec", "-f", str(prof_file)] + cmd

    # A minimal environment. Generated code is untrusted, and the parent shell
    # commonly holds API keys and cloud credentials; with one `net`-tagged block
    # those are an exfiltration path. Pass through only what toolchains need.
    keep = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "SHELL", "USER",
            "CARGO_HOME", "RUSTUP_HOME", "GOPATH", "GOROOT", "GOCACHE", "GOMODCACHE",
            "GOFLAGS", "NVM_DIR", "NODE_PATH", "VIRTUAL_ENV", "PYTHONPATH",
            "JAVA_HOME", "SDKMAN_DIR", "MISE_DATA_DIR", "XDG_CACHE_HOME")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE="1", NO_COLOR="1", TERM="dumb",
               HOME=str(cwd), TMPDIR=str(cwd), PYTHONIOENCODING="utf-8")
    # `file=`-backed listings live under code/ as real modules, so a later
    # listing can `import` an earlier one the way a reader's copy would.
    code_dir = (book / "code") if book else None
    if code_dir and code_dir.is_dir():
        env["PYTHONPATH"] = str(code_dir) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        env["NODE_PATH"] = str(code_dir) + (os.pathsep + env["NODE_PATH"] if env.get("NODE_PATH") else "")
    try:
        p = subprocess.run(full, capture_output=True, text=True,
                           timeout=timeout, cwd=cwd, env=env)
        # Tracebacks name the scratch file and the book directory. The reader
        # should see `snippet.py` and `code/backtrack.py`, not the author's
        # home directory, so the paths are trimmed at capture time.
        def trim(text: str) -> str:
            text = text.replace(str(cwd) + os.sep, "")
            if book is not None:
                text = text.replace(str(book) + os.sep, "")
            return text
        return trim(p.stdout), trim(p.stderr), p.returncode
    except subprocess.TimeoutExpired:
        return "", f"TIMEOUT after {timeout}s", 124
    except FileNotFoundError as e:
        return "", f"toolchain missing: {e}", 127


def judge(block: Block) -> None:
    """Decide pass/fail, and split the block's own output off the env prefix."""
    out = block.actual
    if SENTINEL in out:
        out = out.split(SENTINEL, 1)[1]
    block.actual = out

    denied = "sandbox" in block.stderr.lower() and "denied" in block.stderr.lower()
    # An expect-error block may legitimately demonstrate a PermissionError; only
    # the sandbox's own wording counts there.
    if denied or (block.mode != "expect-error" and block.exit_code == 1
                  and "Operation not permitted" in block.stderr):
        block.status = "sandbox-denied"
        block.note = ("blocked by the sandbox. If the example genuinely needs the network, "
                      "tag it `net`; do not loosen the global profile.")
        return

    if block.exit_code == 127:
        block.status = "toolchain-missing"
        block.note = block.stderr.strip()[:200]
        return

    if block.mode == "expect-error":
        if block.exit_code == 0:
            block.status = "fail"
            block.note = ("tagged expect-error but it succeeded. Either the example no longer "
                          "demonstrates the error, or the tag is wrong.")
            return
        want = block.tags.get("expect")
        if isinstance(want, str) and want not in block.stderr:
            block.status = "fail"
            block.note = f"failed, but stderr does not contain expected text {want!r}"
            return
        # If the book shows the error, the shown error must be the real one. A
        # cautionary example whose message has drifted teaches the wrong lesson.
        if block.expected is not None and block.tags.get("nondet") != "output":
            if normalise(block.stderr) != normalise(block.expected):
                block.status = "drift"
                block.note = "the error shown in the book is not the error it produces"
                return
        block.status = "pass"
        return

    if block.mode == "check":
        block.status = "pass" if block.exit_code == 0 else "fail"
        if block.status == "fail":
            block.note = block.stderr.strip()[:400]
        return

    # mode == run
    if block.exit_code != 0:
        block.status = "fail"
        block.note = (block.stderr.strip() or f"exit code {block.exit_code}")[:600]
        return

    # nondet=output is checked before any diffing: it promises the block runs but is
    # never auto-corrected, and that has to hold whether or not the book shows output.
    if block.tags.get("nondet") == "output":
        block.status = "pass"
        block.note = "nondet=output: ran and exited 0; output not diffed"
        return

    if block.expected is None:
        block.status = "pass" if not block.actual.strip() else "drift"
        if block.status == "drift":
            block.note = "produced output but the book shows none"
        return

    if normalise(block.actual) == normalise(block.expected):
        block.status = "pass"
    else:
        block.status = "drift"
        block.note = "real output differs from the book"


# ── Correction files ──────────────────────────────────────────────────────────

def write_corrections(book: Path, blocks: list[Block]) -> dict:
    """Rebuild each drifted chapter with real output spliced in. Never in place."""
    by_chapter: dict[str, list[Block]] = {}
    for b in blocks:
        if b.status == "drift":
            by_chapter.setdefault(b.chapter, []).append(b)

    corrected = {}
    for chapter, drifted in by_chapter.items():
        path = drifted[0].path
        lines = path.read_text(encoding="utf-8").splitlines()
        # apply bottom-up so earlier line numbers stay valid
        for b in sorted(drifted, key=lambda x: x.line, reverse=True):
            # The book shows what the code really printed. Normalisation exists to make
            # the *diff* stable, not to put <TIME> and <DUR> in front of a reader.
            source = b.stderr if b.mode == "expect-error" else b.actual
            real = "\n".join(ln.rstrip() for ln in source.strip().splitlines())
            new_block = ["```output", *real.splitlines(), "```"]
            if b.expected_span:
                s, e = b.expected_span
                lines[s - 1:e] = new_block
            else:
                lines[b.end_line:b.end_line] = ["", *new_block]
        out = "\n".join(lines) + "\n"
        target = path.with_suffix(".md.corrected")
        target.write_text(out, encoding="utf-8")
        corrected[chapter] = str(target)
    return corrected


def promote(book: Path) -> int:
    n = 0
    for c in sorted((book / "src").glob("*.md.corrected")):
        target = c.with_suffix("")          # strip .corrected -> .md
        if target.exists() and target.stat().st_mtime > c.stat().st_mtime:
            # The chapter was edited after this correction was written. Moving it
            # would silently revert those edits. Re-run verify to regenerate it.
            print(f"  SKIPPED {c.name}: {target.name} was modified after the correction "
                  f"was written; re-run verify.py to refresh it, then promote")
            c.unlink()
            continue
        shutil.move(str(c), str(target))
        print(f"  promoted {target.name}")
        n += 1
    if n == 0:
        print("Nothing to promote.")
    return n


# ── Reporting ─────────────────────────────────────────────────────────────────

SYMBOL = {"pass": "OK", "fail": "FAIL", "drift": "DRIFT", "unverified": "UNVERIFIED",
          "skipped": "literal", "sandbox-denied": "DENIED", "toolchain-missing": "NO-TOOL"}


def print_report(book: Path, blocks: list[Block], corrected: dict, strict: bool) -> int:
    counts: dict[str, int] = {}
    for b in blocks:
        counts[b.status] = counts.get(b.status, 0) + 1
    cached = sum(1 for b in blocks if b.cached)

    today = subprocess.run(["date", "+%F"], capture_output=True, text=True).stdout.strip()
    print(f"\nBook verification · {today}")
    print("─" * 62)
    if not SANDBOX_AVAILABLE:
        print("  WARNING: sandbox-exec not found; blocks ran UNSANDBOXED with network access")
    print(f"Blocks {len(blocks):>5} total   ({cached} from cache)")
    for status in ("pass", "skipped", "unverified", "drift", "fail",
                   "sandbox-denied", "toolchain-missing"):
        if counts.get(status):
            print(f"  {SYMBOL[status]:<12} {counts[status]:>4}")

    problems = [b for b in blocks
                if b.status in ("fail", "sandbox-denied", "toolchain-missing")]
    if problems:
        print("\nFailures")
        print("─" * 62)
        for b in problems:
            print(f"  {b.ident}  ({b.lang} {b.mode})  [{SYMBOL[b.status]}]")
            for ln in b.note.splitlines()[:8]:
                print(f"      {ln}")

    drifts = [b for b in blocks if b.status == "drift"]
    if drifts:
        print("\nOutput drift — review the diff, then re-run with --promote to accept")
        print("─" * 62)
        for b in drifts:
            print(f"  {b.ident}")
            shown = b.stderr if b.mode == "expect-error" else b.actual
            diff = difflib.unified_diff(
                normalise(b.expected or "").splitlines(),
                normalise(shown).splitlines(),
                fromfile="book says", tofile="actually prints", lineterm="")
            for ln in list(diff)[:20]:
                print(f"      {ln}")
        print("\n  corrected files written:")
        for chapter, p in corrected.items():
            print(f"    {p}")

    unver = [b for b in blocks if b.status == "unverified"]
    if unver:
        print("\nUnverified, by declaration — visible here so the skip is not silent")
        print("─" * 62)
        for b in unver:
            print(f"  {b.ident}: {b.note}")

    (book / ".verify").mkdir(exist_ok=True)
    (book / ".verify" / "report.json").write_text(json.dumps({
        "counts": counts,
        "sandboxed": SANDBOX_AVAILABLE,
        "blocks": [{k: v for k, v in asdict(b).items() if k != "path"} for b in blocks],
        "corrected": corrected,
    }, indent=2, default=str))

    hard_fail = bool(problems) or bool(drifts)
    if strict and unver:
        hard_fail = True
        print("\n--strict: unverified blocks are not acceptable for publish.")
    print()
    if hard_fail:
        print("NOT READY TO PUBLISH")
    else:
        print("All code verified.")
    return 1 if hard_fail else 0


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup(book: Path) -> None:
    """Materialise language projects OUTSIDE the sandbox."""
    py = book / "verify" / "python"
    if (py / "pyproject.toml").exists() and shutil.which("uv"):
        print("  syncing verify/python …")
        subprocess.run(["uv", "sync", "--quiet"], cwd=py, check=False)
    node = book / "verify" / "node"
    if (node / "package.json").exists() and shutil.which("npm"):
        if (node / "package-lock.json").exists():
            print("  installing verify/node …")
            subprocess.run(["npm", "ci", "--silent"], cwd=node, check=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", type=Path)
    ap.add_argument("--strict", action="store_true",
                    help="treat declared-unverified blocks as failures too")
    ap.add_argument("--promote", action="store_true",
                    help="accept .md.corrected files, then exit")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--only", help="restrict to chapters whose stem contains this")
    ap.add_argument("--sync-code", action="store_true",
                    help="write each file=-tagged listing out to the path it declares")
    ap.add_argument("--setup", action="store_true",
                    help="materialise language environments and exit")
    args = ap.parse_args()

    book = args.book.expanduser().resolve()
    src = book / "src"
    if not src.is_dir():
        print(f"error: {src} does not exist -- is {book} a techbook project?", file=sys.stderr)
        return 3

    if args.promote:
        return 0 if promote(book) >= 0 else 1
    if args.setup:
        setup(book)
        return 0

    chapters = sorted(p for p in src.glob("*.md")
                      if not p.name.endswith(".corrected.md") and p.stem != "SUMMARY")
    if not chapters:
        print(f"error: no chapters in {src}", file=sys.stderr)
        return 3

    # Every chapter is parsed even under --only, because an env= session may
    # begin in an earlier chapter and the prefix has to be complete.
    all_blocks: list[Block] = []
    lint: list[str] = []
    for ch in chapters:
        blocks, errs = parse_chapter(ch)
        all_blocks.extend(blocks)
        lint.extend(errs)
    selected = [b for b in all_blocks if not args.only or args.only in b.chapter]
    if args.only and not selected:
        print(f"error: no chapters matched {args.only!r} in {src}", file=sys.stderr)
        return 3

    lint.extend(dep_gate(all_blocks, book))
    lint.extend(code_file_gate(all_blocks, book, args.sync_code))

    if lint:
        print("Lint errors — nothing was executed")
        print("─" * 62)
        for e in lint:
            print(f"  {e}")
        print(f"\n{len(lint)} problem(s). Fix these first.")
        return 2

    setup(book)
    if not SANDBOX_AVAILABLE:
        print("WARNING: sandbox-exec not found on this machine. Blocks will run with no\n"
              "         filesystem or network confinement. Read the code before trusting this.\n")
    for b in selected:
        run_block(b, all_blocks, book, use_cache=not args.no_cache)

    corrected = write_corrections(book, selected)
    return print_report(book, selected, corrected, args.strict)


if __name__ == "__main__":
    sys.exit(main())
