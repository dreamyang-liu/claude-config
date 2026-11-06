#!/usr/bin/env python3
"""comment-lint: deterministic surface checks for the code-comments skill.

Standard library only. The linter reads comments and docstrings in Python,
shell and SQL files and checks the measurable rules in SKILL.md. These are
tags, ASCII, lengths, Args blocks, history and caller phrases, vague words,
semicolons, sentence length, step numbering, Markdown and commented-out code.
It cannot check whether a comment explains why, passes the change test or the
recovery test, or agrees with the code. A clean run means only that the
configured patterns did not match.

Usage:
    comment-lint.py [--json] [--baseline N] [--disable rule1,rule2] PATH ...
    comment-lint.py --list-rules
    comment-lint.py --selftest

Exit status: 1 when hard findings exceed --baseline, 0 otherwise.
Advisory findings never change the exit status.

Suppress a line with a trailing comment `# comment-lint: ignore`.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
import textwrap
import tokenize
import warnings
from dataclasses import asdict, dataclass

HARD, ADV = "hard", "advisory"
IFACE = "SKILL.md: Interface comments"
IMPL = "SKILL.md: Implementation comments"
TAGS = "SKILL.md: Tags"
HOMES = "SKILL.md: Where other explanations go"
WORDING = "SKILL.md: Wording"
SCOPE = "SKILL.md: Scope and maintenance"

# rule id -> (severity, source, message)
RULES = {
    "args-block": (HARD, IFACE,
                   "Args, Returns, Raises or Yields block. Write the contract in sentences. The "
                   "signature and the type hints give the names and the types."),
    "todo-owner": (HARD, TAGS,
                   "TODO without an owner or an issue. Write TODO(<owner>) or TODO(<issue URL>)."),
    "banned-tag": (HARD, TAGS,
                   "Banned tag. Do not write FIXME, XXX, HACK, or a comment that starts with NOTE:. "
                   "Write a TODO with an owner, or state the fact."),
    "non-ascii": (HARD, SCOPE,
                  "Non-ASCII character. Write comments in ASCII. Do not use Unicode arrows, dashes, "
                  "math symbols or CJK characters."),
    "docstring-length": (HARD, SCOPE,
                         "Docstring over the limit: 20 lines for a file docstring, 5 for a function "
                         "or class. Move the rest to docs/."),
    "comment-run": (HARD, SCOPE,
                    "Run of whole-line comments over 2 lines. Shorten it, or move the content to "
                    "docs/."),
    "step-numbering": (ADV, IMPL,
                       "Step numbering over straight-line code. If the flow needs numbers, extract "
                       "helper functions with clear names."),
    "history": (ADV, IMPL + "; " + HOMES,
                "Possible history or review reference. Git keeps the history. Write the constraint, "
                "not the story."),
    "caller-names": (ADV, IFACE + "; " + IMPL,
                     "Names the callers. grep finds them. Leave them out."),
    "hedge-todo": (ADV, IMPL,
                   "Hedge. Find the fact and state it, or write a TODO with an owner."),
    "commented-out-code": (ADV, IMPL,
                           "Comment parses as Python code. Remove commented-out code."),
    "semicolon": (ADV, WORDING,
                  "Semicolon joins two facts. Write two sentences."),
    "long-sentence": (ADV, WORDING,
                      "Sentence over 25 words. Divide it."),
    "vague-word": (ADV, WORDING,
                   "Vague word. Write what the code does."),
    "markdown-in-comment": (ADV, WORDING,
                            "Markdown heading or table in a comment. Do not use Markdown structure in "
                            "an inline comment."),
}

EXTENSIONS = {".py": "py", ".sh": "sh", ".bash": "sh", ".sql": "sql"}
MARKERS = {"py": "#", "sh": "#", "sql": "--"}
MAX_FILE_DOC = 20
MAX_DEF_DOC = 5
MAX_RUN = 2
MAX_WORDS = 25
ARGS_BLOCK = {"Args:", "Arguments:", "Returns:", "Raises:", "Yields:"}

IGNORE = re.compile(r"(?:#|--)\s*comment-lint:\s*ignore\s*$")
INLINE_CODE = re.compile(r"(`+)(.+?)\1")
NON_ASCII = re.compile(r"[^\x00-\x7f]")
TODO = re.compile(r"\bTODO\b")
TODO_OWNER = re.compile(r"\s*\(\S[^)]*\)")
BANNED = re.compile(r"\b(?:FIXME|XXX|HACK)\b")
NOTE_START = re.compile(r"^\s*note:", re.I)
HISTORY = re.compile(r"\b(?:(?:we|it|this|that|they|which|code)\s+used\s+to|used\s+to\s+be|previously|"
                     r"removed|fixed\s+the\s+bug|(?:new|old)\s+version|as\s+suggested|(?:per|in)\s+review|"
                     r"legacy)\b", re.I)
CALLER = re.compile(r"\b(?:called\s+(?:by|from)|used\s+by)\b", re.I)
HEDGE = re.compile(r"\b(?:should\s+probably|revisit(?:ed|s|ing)?)\b", re.I)
VAGUE = re.compile(r"\b(?:handles?|robust|reliable|supports|ensure|simply|just|easily|obviously|utilize|"
                   r"leverage|facilitate|various|and/or)\b|\betc\.", re.I)
SEMICOLON = re.compile(r";")
STEP = re.compile(r"^(?:#+|--+)\s*(?:step\s*)?\d+[.:)](?:\s|$)", re.I)
HEADING = re.compile(r"^#{2,6}\s+\S")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
SENTENCE_END = re.compile(r"(?<=[.?!])\s+")
WORD_CHAR = re.compile(r"[^\W_]")
SH_FUNCTION = re.compile(r"^\s*(?:function\s+)?[A-Za-z_][\w-]*\s*\(\)\s*\{?\s*$|"
                         r"^\s*function\s+[A-Za-z_][\w-]*\s*\{?\s*$")
WORD_RULES = (("history", HISTORY), ("caller-names", CALLER), ("hedge-todo", HEDGE),
              ("vague-word", VAGUE), ("semicolon", SEMICOLON))
CODE_NODES = (ast.Assign, ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.Return)
DOC_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    col: int
    rule: str
    severity: str
    message: str
    excerpt: str


@dataclass(frozen=True)
class Line:
    """One source line of a comment or docstring. COL is the 1-based column of TEXT."""
    no: int
    col: int
    comment: str
    text: str


@dataclass(frozen=True)
class Unit:
    """A block the rules apply to. KIND is module, def, run or inline."""
    kind: str
    lines: tuple


# --------------------------------------------------------------------------- extraction


def _comment_line(no, col, raw, marker):
    comment = raw[col:].rstrip()
    body = comment[len(marker):].lstrip(marker[0])
    if body.startswith(":"):
        body = body[1:]
    text = body.strip()
    return Line(no=no, col=col + 1 + len(comment) - len(body.lstrip()), comment=comment, text=text)


def _runs(lines):
    units, group = [], []
    for ln in lines:
        if group and ln.no != group[-1].no + 1:
            units.append(Unit(kind="run", lines=tuple(group)))
            group = []
        group.append(ln)
    if group:
        units.append(Unit(kind="run", lines=tuple(group)))
    return units


def _comment_units(comments, marker):
    """Units for (line number, column, source line) triples. The shebang is skipped."""
    whole, units = [], []
    for no, col, raw in comments:
        if no == 1 and raw.startswith("#!"):
            continue
        line = _comment_line(no=no, col=col, raw=raw, marker=marker)
        if raw[:col].strip():
            units.append(Unit(kind="inline", lines=(line,)))
        else:
            whole.append(line)
    return units + _runs(whole)


def _inline_marker(raw, marker):
    """Column of the first MARKER outside quotes and after whitespace, or -1."""
    quote = None
    i = 0
    while i < len(raw):
        ch = raw[i]
        if quote:
            if ch == "\\" and quote == '"':
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif raw.startswith(marker, i) and i > 0 and raw[i - 1] in " \t":
            return i
        i += 1
    return -1


def _reclassify(unit, source, opening, functions):
    """Mark the opening block as the file docstring, and a block above a shell function as its own."""
    if unit.kind != "run":
        return unit
    first, last = unit.lines[0].no, unit.lines[-1].no
    starts_file = first == 1 or (first == 2 and source[0].startswith("#!"))
    if opening and starts_file:
        return Unit(kind="module", lines=unit.lines)
    if functions and last < len(source) and SH_FUNCTION.match(source[last]):
        return Unit(kind="def", lines=unit.lines)
    return unit


def _marker_units(text, marker, opening, functions):
    source = text.splitlines()
    comments = []
    for no, raw in enumerate(source, 1):
        stripped = raw.lstrip()
        if stripped.startswith(marker):
            comments.append((no, len(raw) - len(stripped), raw))
        else:
            col = _inline_marker(raw, marker)
            if col >= 0:
                comments.append((no, col, raw))
    units = _comment_units(comments, marker=marker)
    return [_reclassify(u, source=source, opening=opening, functions=functions) for u in units]


def _docstring_expr(node):
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[0]
    return None


def _docstring_unit(expr, kind, source):
    span = expr.end_lineno - expr.lineno + 1
    values = expr.value.value.splitlines() or [""]
    lines = []
    for i in range(span):
        no = expr.lineno + i
        raw = source[no - 1] if no <= len(source) else ""
        text = values[i] if i < len(values) else ""
        col = raw.find(text) + 1 if text.strip() and text in raw else 1
        lines.append(Line(no=no, col=col, comment=text, text=text))
    return Unit(kind=kind, lines=tuple(lines))


def _python_units(text):
    comments = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                comments.append((tok.start[0], tok.start[1], tok.line.rstrip("\r\n")))
    except (tokenize.TokenError, SyntaxError):
        return _marker_units(text, marker="#", opening=False, functions=False)
    units = _comment_units(comments, marker="#")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return units
    source = text.splitlines()
    for node in ast.walk(tree):
        expr = _docstring_expr(node) if isinstance(node, DOC_NODES) else None
        if expr is not None:
            kind = "module" if isinstance(node, ast.Module) else "def"
            units.append(_docstring_unit(expr, kind=kind, source=source))
    return units


def _units(text, lang):
    if lang == "py":
        return _python_units(text)
    return _marker_units(text, marker=MARKERS[lang], opening=True, functions=lang == "sh")


# --------------------------------------------------------------------------- checks


def _mask(text):
    """Replace each backtick span with a placeholder word of equal length."""
    return INLINE_CODE.sub(lambda m: "x" * len(m.group(0)), text)


def _sentences(text):
    """Yield (start offset, sentence) pairs. The splitter cuts after '. ', '? ' and '! '."""
    start = 0
    for m in SENTENCE_END.finditer(text):
        yield start, text[start:m.start()]
        start = m.end()
    yield start, text[start:]


def _is_prose(text):
    stripped = text.strip()
    return stripped.endswith(".") and not any(c in stripped[:-1] for c in "(=.")


def _parses_as_code(text):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(textwrap.dedent(text))
    except (SyntaxError, ValueError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, CODE_NODES) or (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            return True
    return False


def _check_line(ln, is_doc, is_comment, emit):
    if is_doc and ln.text.strip() in ARGS_BLOCK:
        emit("args-block", ln)
    m = NON_ASCII.search(ln.text)
    if m:
        emit("non-ascii", ln, offset=m.start())
    masked = _mask(ln.text)
    for m in TODO.finditer(masked):
        if not TODO_OWNER.match(masked, m.end()):
            emit("todo-owner", ln, offset=m.start())
    for m in BANNED.finditer(masked):
        emit("banned-tag", ln, offset=m.start())
    if NOTE_START.match(masked):
        emit("banned-tag", ln)
    for rule, rx in WORD_RULES:
        for m in rx.finditer(masked):
            emit(rule, ln, offset=m.start())
    if is_comment:
        if STEP.match(ln.comment):
            emit("step-numbering", ln)
        if HEADING.match(ln.comment) or TABLE_ROW.match(ln.text):
            emit("markdown-in-comment", ln)


def _check_sentences(unit, emit):
    joined = "\n".join(_mask(ln.text) for ln in unit.lines)
    for start, sentence in _sentences(joined):
        words = sum(1 for t in sentence.split() if WORD_CHAR.search(t))
        if words > MAX_WORDS:
            emit("long-sentence", unit.lines[joined[:start].count("\n")], extra="%d words." % words)


def _check_commented_code(unit, emit):
    code_lines = [ln for ln in unit.lines if ln.text and not _is_prose(ln.text)]
    if not code_lines:
        return
    if _parses_as_code("\n".join(ln.text for ln in code_lines)):
        emit("commented-out-code", code_lines[0])
        return
    for ln in code_lines:
        if _parses_as_code(ln.text):
            emit("commented-out-code", ln)


def _check_unit(unit, lang, emit):
    first, count = unit.lines[0], len(unit.lines)
    if unit.kind == "module" and count > MAX_FILE_DOC:
        emit("docstring-length", first, extra="%d lines, limit %d." % (count, MAX_FILE_DOC))
    elif unit.kind == "def" and count > MAX_DEF_DOC:
        emit("docstring-length", first, extra="%d lines, limit %d." % (count, MAX_DEF_DOC))
    elif unit.kind == "run" and count > MAX_RUN:
        emit("comment-run", first, extra="%d lines." % count)
    is_doc = lang == "py" and unit.kind in ("module", "def")
    for ln in unit.lines:
        _check_line(ln, is_doc=is_doc, is_comment=unit.kind in ("run", "inline"), emit=emit)
    _check_sentences(unit, emit)
    if lang == "py" and unit.kind == "run":
        _check_commented_code(unit, emit)


def _lang(filename):
    return EXTENSIONS.get(os.path.splitext(filename)[1].lower(), "py")


def lint(text, filename="<stdin>", disabled=()):
    """Findings for one source text. The file extension selects the comment syntax."""
    lang = _lang(filename)
    ignored = {no for no, raw in enumerate(text.splitlines(), 1) if IGNORE.search(raw)}
    findings = []

    def emit(rule, ln, offset=0, extra=""):
        if rule in disabled or ln.no in ignored:
            return
        excerpt = ln.comment.strip()
        if len(excerpt) > 80:
            excerpt = excerpt[:77] + "..."
        message = " ".join(x for x in (RULES[rule][2], extra) if x)
        findings.append(Finding(file=filename, line=ln.no, col=ln.col + offset, rule=rule,
                                severity=RULES[rule][0], message=message, excerpt=excerpt))

    for unit in _units(text, lang):
        _check_unit(unit, lang=lang, emit=emit)
    findings.sort(key=lambda f: (f.file, f.line, f.col, f.rule))
    return findings


# --------------------------------------------------------------------------- paths


def _collect(paths):
    files = []
    for path in paths:
        if not os.path.isdir(path):
            files.append(path)
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d != "__pycache__")
            files += [os.path.join(dirpath, f) for f in sorted(filenames)
                      if os.path.splitext(f)[1].lower() in EXTENSIONS]
    return files


def lint_paths(paths, disabled=()):
    """Findings for files and directories. A directory is walked for .py, .sh and .sql files."""
    findings = []
    for path in _collect(paths):
        with open(path, encoding="utf-8") as fh:
            findings += lint(fh.read(), filename=path, disabled=disabled)
    return findings


def report(findings, as_json, baseline):
    hard = sum(1 for f in findings if f.severity == HARD)
    adv = len(findings) - hard
    if as_json:
        print(json.dumps({"hard": hard, "advisory": adv, "baseline": baseline,
                          "findings": [asdict(f) for f in findings]}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print('%s:%d:%d: %s %s: %s  "%s"' % (f.file, f.line, f.col, f.severity, f.rule,
                                                f.message, f.excerpt))
        print("%d hard, %d advisory (baseline %d)" % (hard, adv, baseline))
    return 1 if hard > baseline else 0


def list_rules():
    print("%-22s %-9s %s" % ("rule", "severity", "source"))
    for rid, (severity, source, _) in RULES.items():
        print("%-22s %-9s %s" % (rid, severity, source))


# --------------------------------------------------------------------------- selftest

CLEAN_PY = '''\
#!/usr/bin/env python3
"""Count the words in a file.

The caller passes a path. The function returns the count as an int.
"""
import sys

LIMIT_BYTES = 1048576  #: 1 MiB. Arbitrary, large enough for the inputs we have seen.


def count_words(path):
    """The number of whitespace-separated words in the file at PATH."""
    with open(path, encoding="utf-8") as fh:
        # The file fits in memory. The caller limits the size to LIMIT_BYTES.
        return len(fh.read().split())


# TODO(mliu): add a streaming mode.
if __name__ == "__main__":
    sys.exit(count_words(sys.argv[1]))
'''

CLEAN_SH = '''\
#!/bin/sh
# Build the wheel and copy it to dist/.
# The caller runs it from the repository root.
set -eu

# pip needs the build module. The image does not ship it.
python3 -m pip install build
python3 -m build --wheel  # TODO(mliu): pin the build version.
echo "# not a comment"
'''

CLEAN_SQL = '''\
-- Jobs that a worker can claim.
-- The lease columns are in seconds since the epoch.
CREATE TABLE jobs (
    id BIGSERIAL PRIMARY KEY,
    lease_until BIGINT NOT NULL, -- 0 means no lease. The worker compares it with now().
    state TEXT NOT NULL DEFAULT 'queued -- not a comment'
);
'''

_LONG_DOC = '"""Title.\n' + "line\n" * 19 + '"""\n'
_OK_DOC = '"""Title.\n' + "line\n" * 18 + '"""\n'
_LONG_DEF = 'def f():\n    """Title.\n' + "    a\n" * 4 + '    """\n'
_OK_DEF = 'class A:\n    """Title.\n' + "    a\n" * 3 + '    """\n'
_LONG_OPENING = "#!/bin/sh\n" + "# line\n" * 21 + "echo hi\n"
_OK_OPENING = "#!/bin/sh\n" + "# line\n" * 20 + "echo hi\n"
_WORDS_26 = "# " + " ".join(["word"] * 26) + ".\n"
_WORDS_25 = "# " + " ".join(["word"] * 25) + ".\n"

# (extension, source text, rules that must appear, rules that must not appear)
SELFTEST_CASES = [
    ("py", CLEAN_PY, set(), set(RULES)),
    ("sh", CLEAN_SH, set(), set(RULES)),
    ("sql", CLEAN_SQL, set(), set(RULES)),
    ("py", 'def f():\n    """Do x.\n\n    Args:\n        a: thing\n    """\n', {"args-block"}, set()),
    ("py", '"""Module.\n\nReturns:\n    nothing\n"""\n', {"args-block"}, set()),
    ("py", 'def f():\n    """Return the count of x in y."""\n', set(), {"args-block"}),
    ("py", "# Args:\n", set(), {"args-block"}),
    ("py", "# TODO: fix this\n", {"todo-owner"}, set()),
    ("py", "x = 1  # TODO fix this\n", {"todo-owner"}, set()),
    ("py", "# TODO(mliu): fix this\n", set(), {"todo-owner"}),
    ("py", "# TODO(https://github.com/o/r/issues/1): fix this\n", set(), {"todo-owner"}),
    ("py", "# FIXME broken\n", {"banned-tag"}, set()),
    ("py", "# XXX\n", {"banned-tag"}, set()),
    ("py", "x = 1  # HACK around it\n", {"banned-tag"}, set()),
    ("py", "# NOTE: the lease is in seconds\n", {"banned-tag"}, set()),
    ("py", "# Note that the lease is in seconds\n", set(), {"banned-tag"}),
    ("py", "# The arrow \u2192 is not ASCII\n", {"non-ascii"}, set()),
    ("py", '"""Caf\u00e9."""\n', {"non-ascii"}, set()),
    ("py", 'x = "\u00e9"  # ASCII comment\n', set(), {"non-ascii"}),
    ("py", _LONG_DOC, {"docstring-length"}, set()),
    ("py", _OK_DOC, set(), {"docstring-length"}),
    ("py", _LONG_DEF, {"docstring-length"}, set()),
    ("py", _OK_DEF, set(), {"docstring-length"}),
    ("sh", _LONG_OPENING, {"docstring-length"}, {"comment-run"}),
    ("sh", _OK_OPENING, set(), {"docstring-length", "comment-run"}),
    ("sql", "-- a\n" * 21 + "SELECT 1;\n", {"docstring-length"}, {"comment-run"}),
    ("py", "# a\n# b\n# c\nx = 1\n", {"comment-run"}, set()),
    ("py", "# a\n# b\nx = 1\n", set(), {"comment-run"}),
    ("py", "#!/usr/bin/env python3\n# a\n# b\nx = 1\n", set(), {"comment-run"}),
    ("py", "#: a\n#: b\n#: c\nX = 1\n", {"comment-run"}, set()),
    ("py", "# a\nx = 1\n# b\n# c\n", set(), {"comment-run"}),
    ("sh", "echo hi\n# a\n# b\n# c\necho x\n", {"comment-run"}, set()),
    ("sh", "#!/bin/sh\n# a\n# b\n# c\necho x\n", set(), {"comment-run"}),
    ("sh", "#!/bin/sh\n\n# a\n# b\n# c\nfoo() {\n  echo\n}\n", set(), {"comment-run", "docstring-length"}),
    ("sh", "#!/bin/sh\n\n" + "# a\n" * 6 + "function foo {\n  echo\n}\n", {"docstring-length"}, set()),
    ("sql", "SELECT 1;\n-- a\n-- b\n-- c\nSELECT 2;\n", {"comment-run"}, set()),
    ("sql", "-- a\n-- b\n-- c\nSELECT 1;\n", set(), {"comment-run"}),
    ("py", "# Step 1: load the config\nx = 1\n", {"step-numbering"}, set()),
    ("py", "# 1. load the config\nx = 1\n", {"step-numbering"}, set()),
    ("py", "# 2) load the config\nx = 1\n", {"step-numbering"}, set()),
    ("py", "# 3.5 s is the timeout\nx = 1\n", set(), {"step-numbering"}),
    ("sql", "-- 1. load\nSELECT 1;\n-- 2. store\nSELECT 2;\n", {"step-numbering"}, set()),
    ("py", "# We used to release the lease first.\n", {"history"}, set()),
    ("py", "# Removed the old path as suggested in review.\n", {"history"}, set()),
    ("py", "# Legacy flag, kept for the old version.\n", {"history"}, set()),
    ("py", "# Release the lease after the commit.\n", set(), {"history"}),
    ("py", "# The worker is used to compute the mean.\n", set(), {"history"}),
    ("py", "# Called by the worker at each heartbeat.\n", {"caller-names"}, set()),
    ("py", "# Used by run() and stop().\n", {"caller-names"}, set()),
    ("py", "# The worker reads it at each heartbeat.\n", set(), {"caller-names"}),
    ("py", "# This should probably be revisited.\n", {"hedge-todo"}, set()),
    ("py", "# Revisit after the Go runtime update.\n", {"hedge-todo"}, set()),
    ("py", "# The pool should hold 4 workers.\n", set(), {"hedge-todo"}),
    ("py", "# x = compute(y)\n", {"commented-out-code"}, set()),
    ("py", "# import os\n", {"commented-out-code"}, set()),
    ("py", "# return result\n", {"commented-out-code"}, set()),
    ("py", "# Compute it.\n# result = compute(y)\n", {"commented-out-code"}, set()),
    ("py", "# if x:\n#     run(x)\n", {"commented-out-code"}, set()),
    ("py", "# Compute the mean over the window.\n", set(), {"commented-out-code"}),
    ("py", "# type: ignore\n# noqa: E501\n", set(), {"commented-out-code"}),
    ("py", "x = 1  # compute(y)\n", set(), {"commented-out-code"}),
    ("py", "# Open the file; read it.\n", {"semicolon"}, set()),
    ("py", '"""Open the file; read it."""\n', {"semicolon"}, set()),
    ("py", "# Use `a; b` in the shell.\n", set(), {"semicolon"}),
    ("sql", "-- col: seconds; arbitrary.\nSELECT 1;\n", {"semicolon"}, set()),
    ("py", _WORDS_26, {"long-sentence"}, set()),
    ("py", _WORDS_25, set(), {"long-sentence"}),
    ("py", '"""Title.\n\n' + " ".join(["word"] * 13) + "\n" + " ".join(["word"] * 13) + '.\n"""\n',
     {"long-sentence"}, set()),
    ("py", "# This handles the retry.\n", {"vague-word"}, set()),
    ("py", "# Just a wrapper, etc.\n", {"vague-word"}, set()),
    ("py", '"""Ensure the lease is robust and/or reliable."""\n', {"vague-word"}, set()),
    ("py", "# The worker retries 3 times.\n", set(), {"vague-word"}),
    ("py", "# Use `handle` from the pool.\n", set(), {"vague-word"}),
    ("py", "## Section\nx = 1\n", {"markdown-in-comment"}, set()),
    ("py", "x = 1  # | a | b |\n", {"markdown-in-comment"}, set()),
    ("py", "# Section\nx = 1\n", set(), {"markdown-in-comment"}),
    ("py", "########\nx = 1\n", set(), {"markdown-in-comment"}),
    ("sh", 'echo "# TODO x"\n', set(), {"todo-owner"}),
    ("sh", "echo hi # TODO fix\n", {"todo-owner"}, set()),
    ("sql", "SELECT 'a -- b' -- TODO fix\n", {"todo-owner"}, set()),
    ("sql", "SELECT 'a -- TODO b';\n", set(), {"todo-owner"}),
    ("py", "# FIXME broken  # comment-lint: ignore\n", set(), {"banned-tag"}),
    ("sh", "# FIXME broken  # comment-lint: ignore\necho hi\n", set(), {"banned-tag"}),
    ("sql", "SELECT 1; -- FIXME broken -- comment-lint: ignore\n", set(), {"banned-tag"}),
]


def selftest():
    failed = 0
    for ext, text, must, must_not in SELFTEST_CASES:
        got = {f.rule for f in lint(text, filename="sample." + ext)}
        miss, extra = must - got, must_not & got
        if miss or extra:
            failed += 1
            print("FAIL [%s] %r\n  missing=%s unexpected=%s got=%s" % (ext, text[:70], sorted(miss),
                                                                     sorted(extra), sorted(got)))
    print("selftest: %d/%d passed" % (len(SELFTEST_CASES) - failed, len(SELFTEST_CASES)))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic checks for the code-comments skill.")
    ap.add_argument("paths", nargs="*", help="files or directories (walked for .py, .sh and .sql)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--baseline", type=int, default=0, help="tolerate N hard findings")
    ap.add_argument("--disable", default="", help="comma-separated rule ids to silence")
    ap.add_argument("--list-rules", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.list_rules:
        list_rules()
        return 0
    if not args.paths:
        ap.error("give at least one file or directory")
    disabled = {d.strip() for d in args.disable.split(",") if d.strip()}
    unknown = disabled - set(RULES)
    if unknown:
        ap.error("unknown rule id(s): %s" % ", ".join(sorted(unknown)))
    findings = lint_paths(args.paths, disabled=disabled)
    return report(findings, as_json=args.json, baseline=args.baseline)


if __name__ == "__main__":
    sys.exit(main())
