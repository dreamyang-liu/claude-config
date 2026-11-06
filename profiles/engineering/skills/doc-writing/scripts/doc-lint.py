#!/usr/bin/env python3
"""doc-lint: mechanical checks for the doc-writing skill (SKILL.md).

Standard library only. The linter checks the rules of doc-writing/SKILL.md that
a program can see: document length, inline enumerations, list lead-ins, list
nesting depth, the vague-word table, must/shall mixing, Mermaid blocks, ASCII
art, figure captions, and the <title>, <desc> and opaque background of each
SVG figure. It cannot check that the point comes first, that a heading is
informative, or that a behavior statement agrees with the code.

The prose rules that the sibling linters already own (semicolons, sentence
length, passive voice, phrasal verbs, nominalization, wordy phrases) are not
repeated here. When the linter finds the sibling scripts in the same
repository (skills/asd-ste100/scripts/ste-lint.py and
skills/nasa-writing/scripts/nasa-lint.py), it runs them on the same Markdown
files and merges their findings with the rule id prefixed "ste:" or "nasa:".
Their severities are kept. Pass --no-delegate to skip this.

The linter never flags hedges or modality words (may, might, could, should),
although the "Vague words" table of SKILL.md lists "may, might, could (for
behavior)". The sibling linters treat modality as content, not style, and
doc-lint follows them. Review that row by hand.

Usage:
    doc-lint.py [--json] [--baseline N] [--disable rule1,rule2] [--no-delegate]
                PATH [PATH ...]        (files, or directories searched for *.md and *.svg)
    doc-lint.py --list-rules
    doc-lint.py --selftest

Exit status: 1 when hard findings exceed --baseline, 0 otherwise.
Advisory findings never change the exit status.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

HARD, ADV = "hard", "advisory"

SKILL = "doc-writing/SKILL.md"
MAX_LINES = 800
MAX_LIST_DEPTH = 2

# rule id -> (severity, source, message)
RULES = {
    "doc-length": (HARD, SKILL + " > Length, rule 1",
                   "A markdown document has at most %d lines. Split it, or cut what the code already shows."
                   % MAX_LINES),
    "inline-list": (ADV, SKILL + " > Lists: three or more items",
                    "Write three or more items as a vertical list, one item on each line."),
    "list-lead-in": (ADV, SKILL + " > Lists, rule 1",
                     "Introduce the list with a full sentence that says what the items are and ends with a colon."),
    "list-depth": (HARD, SKILL + " > Lists, rule 6",
                   "Do not nest lists more than two levels deep. Flatten the list or use a table."),
    "vague-word": (HARD, SKILL + " > Vague words",
                   "Vague word. Replace it with the measurable statement that the Vague words table gives."),
    "vague-size": (ADV, SKILL + " > Vague words, row 1",
                   "Size or speed word. Write the number and its unit, unless the word is exact in context."),
    "vague-word-zh": (ADV, SKILL + " > Chinese documents",
                      "模糊词。用具体的条件或数字替换，列举要写全，不用“等”。"),
    "obligation-mix": (HARD, SKILL + " > NASA, rule 10",
                       "The document uses both 'must' and 'shall'. Use one set of obligation words."),
    "mermaid": (HARD, SKILL + " > Diagrams, rule 1",
                "Mermaid block. Draw SVG. Do not use ASCII art or Mermaid instead."),
    "ascii-art": (ADV, SKILL + " > Diagrams, rule 1",
                  "This code block looks like ASCII art. Draw SVG, not ASCII art."),
    "figure-caption": (ADV, SKILL + " > Diagrams, rule 2",
                       "Write a one-sentence caption under the figure."),
    "svg-meta": (HARD, SKILL + " > Checklist > Diagrams",
                 "The SVG needs a <title>, a full <desc> and an opaque background rectangle."),
    "svg-parse": (HARD, SKILL + " > Checklist > Diagrams",
                  "The SVG does not parse as XML. Fix the file before you check it."),
}

# ----------------------------------------------------------------------------- terms

VAGUE_EN = [
    r"robust", r"reliable", r"safe", r"supports", r"handles", r"as appropriate", r"if needed",
    r"when necessary", r"etc\.?", r"and so on", r"and\s*/\s*or", r"ensur(?:e|es|ed|ing)",
    r"simply", r"just", r"easily", r"obviously", r"utili[sz](?:e|es|ed|ing)",
    r"leverag(?:e|es|ed|ing)", r"facilitat(?:e|es|ed|ing)", r"a number of", r"various",
]
VAGUE_SIZE_EN = [r"fast", r"slow", r"large", r"small", r"cheap"]
VAGUE_EN_RE = re.compile(r"(?<![\w-])(?:" + "|".join(VAGUE_EN) + r")(?![\w-])", re.I)
VAGUE_SIZE_RE = re.compile(r"(?<![\w-])(?:" + "|".join(VAGUE_SIZE_EN) + r")(?![\w-])", re.I)
VAGUE_ZH_RE = re.compile(r"一般|适当|[^、，,。；：:\s]+(?:、[^、，,。；：:]+)+\s*等(?=[。，,；：:）)\s]|$)")

MUST = re.compile(r"\bmust\b", re.I)
SHALL = re.compile(r"\bshall\b", re.I)

# a, b, and c  /  a, b, c  (items of at most 40 characters without other punctuation)
INLINE_EN = re.compile(r"\b[^,.;:]{1,40},\s+[^,.;:]{1,40},(?:\s+(?:and|or))?\s+[^,.;:]{1,40}")
INLINE_ZH = re.compile(r"[^、，,。；：:]+(?:、[^、，,。；：:]+){2,}")
SENT_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|(?<=[。！？])")

# ----------------------------------------------------------------------------- markdown

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*(\S*)")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])\s+(?:\[[ xX]\]\s+)?")
TABLE_ROW = re.compile(r"^\s*\|")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
QUOTE = re.compile(r"^\s{0,3}(?:>\s?)+")
INLINE_CODE = re.compile(r"(`+)(.+?)\1")
URL = re.compile(r"https?://\S+|www\.\S+")
LINK_TARGET = re.compile(r"\]\([^)\s]*(?:\s+\"[^\"]*\")?\)")
HTML_COMMENT = re.compile(r"<!--.*?-->")
HTML_TAG = re.compile(r"<[^>]+>")
CLOSING_TAG_LINE = re.compile(r"^\s*(?:</\w+\s*>\s*)+$")
IMAGE_MD = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+\.(?:svg|png))(?:\s+\"[^\"]*\")?\s*\)", re.I)
IMAGE_HTML = re.compile(r"<img\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
BOX_DRAWING = re.compile(r"[─-╿]")
ART_PATTERN = re.compile(r"-->|\+--|\|  ")
SVG_NS = "{http://www.w3.org/2000/svg}"


@dataclass
class Finding:
    file: str
    line: int
    col: int
    rule: str
    severity: str
    message: str
    excerpt: str


@dataclass
class Line:
    """One Markdown source line with its classification."""
    no: int
    raw: str
    kind: str          # blank, heading, item, table, prose, html, fence, code, comment
    text: str = ""     # masked prose text (headings, items, prose); cells for table rows
    indent: int = 0
    text_off: int = 0  # column offset of text in the raw line
    cells: tuple = ()
    cell_offs: tuple = ()


def _mask(line):
    """Replace code spans, URLs, link targets and comments so that they match no rule.

    A span becomes a placeholder word of equal length, so columns stay true.
    """
    def word(m):
        n = len(m.group(0))
        return "x" + "_" * (n - 1) if n > 1 else "x"

    line = HTML_COMMENT.sub(lambda m: " " * len(m.group(0)), line)
    line = INLINE_CODE.sub(word, line)
    line = LINK_TARGET.sub(lambda m: "]" + " " * (len(m.group(0)) - 1), line)
    line = URL.sub(word, line)
    return line


def _classify(text):
    """Return the list of Line objects and the list of fenced blocks.

    A fenced block is (open_line_no, info_string, [body lines]).
    """
    lines = text.splitlines()
    out, blocks = [], []
    i0 = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() in ("---", "..."):
                i0 = j + 1
                break
    for idx in range(i0):
        out.append(Line(idx + 1, lines[idx], "comment"))
    fence = None
    block = None
    in_comment = False
    for idx in range(i0, len(lines)):
        raw = lines[idx]
        n = idx + 1
        if fence:
            f = FENCE.match(raw)
            if f and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence) and not f.group(2):
                fence = None
                blocks.append(block)
                block = None
                out.append(Line(n, raw, "fence"))
            else:
                block[2].append(raw)
                out.append(Line(n, raw, "code"))
            continue
        if in_comment:
            if "-->" in raw:
                in_comment = False
            out.append(Line(n, raw, "comment"))
            continue
        stripped_raw = raw.strip()
        if stripped_raw.startswith("<!--") and "-->" not in raw:
            in_comment = True
            out.append(Line(n, raw, "comment"))
            continue
        f = FENCE.match(raw)
        if f:
            fence = f.group(1)
            block = (n, f.group(2).lower(), [])
            out.append(Line(n, raw, "fence"))
            continue
        q = QUOTE.match(raw)
        qoff = q.end() if q else 0
        body = raw[qoff:]
        masked = _mask(body)
        stripped = masked.strip()
        if not stripped:
            out.append(Line(n, raw, "blank"))
            continue
        if HEADING.match(masked):
            t = masked.lstrip(" #")
            out.append(Line(n, raw, "heading", text=t, text_off=qoff + len(masked) - len(t)))
            continue
        if TABLE_ROW.match(masked):
            if TABLE_SEP.match(masked):
                out.append(Line(n, raw, "table"))
            else:
                cells, offs, pos = [], [], masked.find("|") + 1
                for c in masked.strip().strip("|").split("|"):
                    lead = len(c) - len(c.lstrip())
                    cells.append(c.strip())
                    offs.append(qoff + pos + lead)
                    pos += len(c) + 1
                out.append(Line(n, raw, "table", cells=tuple(cells), cell_offs=tuple(offs)))
            continue
        li = LIST_ITEM.match(masked)
        if li:
            out.append(Line(n, raw, "item", text=masked[li.end():].rstrip(), indent=len(li.group(1)),
                            text_off=qoff + li.end()))
            continue
        if stripped.startswith("<") and not HTML_TAG.sub("", stripped).strip():
            out.append(Line(n, raw, "html", text=""))
            continue
        if stripped.startswith("<"):
            out.append(Line(n, raw, "html", text=HTML_TAG.sub(" ", masked)))
            continue
        out.append(Line(n, raw, "prose", text=masked, indent=len(masked) - len(masked.lstrip()), text_off=qoff))
    if block is not None:
        blocks.append(block)
    return out, blocks


def _excerpt(s):
    s = s.strip()
    return s if len(s) <= 80 else s[:77] + "..."


# ----------------------------------------------------------------------------- svg

def _local(tag):
    return tag.split("}", 1)[1] if isinstance(tag, str) and "}" in tag else tag


def _style_value(style, prop):
    m = re.search(r"(?:^|;)\s*" + prop + r"\s*:\s*([^;]+)", style or "")
    return m.group(1).strip() if m else None


def _num(s):
    try:
        return float(re.sub(r"[a-z%]+$", "", s.strip()))
    except (ValueError, AttributeError):
        return None


def _svg_problems(root):
    """Return the list of missing items in an SVG root element."""
    problems = []
    tags = [_local(el.tag) for el in root.iter()]
    if "title" not in tags:
        problems.append("no <title>")
    if "desc" not in tags:
        problems.append("no <desc>")
    vb = root.get("viewBox")
    vbw = vbh = None
    if vb:
        parts = vb.replace(",", " ").split()
        if len(parts) == 4:
            vbw, vbh = _num(parts[2]), _num(parts[3])
    if vbw is None:
        vbw, vbh = _num(root.get("width") or ""), _num(root.get("height") or "")
    if "background" in (root.get("style") or ""):
        return problems
    for el in root.iter():
        if _local(el.tag) != "rect":
            continue
        w, h = el.get("width", ""), el.get("height", "")
        full_w = w.strip() == "100%" or (vbw is not None and _num(w) is not None and _num(w) >= 0.98 * vbw)
        full_h = h.strip() == "100%" or (vbh is not None and _num(h) is not None and _num(h) >= 0.98 * vbh)
        if not (full_w and full_h):
            continue
        fill = el.get("fill") or _style_value(el.get("style"), "fill") or "black"
        fill_opacity = el.get("fill-opacity") or _style_value(el.get("style"), "fill-opacity") or "1"
        opacity = el.get("opacity") or _style_value(el.get("style"), "opacity") or "1"
        if fill.strip().lower() in ("none", "transparent"):
            continue
        if (_num(fill_opacity) or 1) == 0 or (_num(opacity) or 1) == 0:
            continue
        return problems
    problems.append("no opaque background <rect> that covers the viewBox")
    return problems


def lint_svg(path, disabled=()):
    """Check one SVG file. Returns a list of findings."""
    findings = []
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        if "svg-parse" not in disabled:
            findings.append(Finding(path, 1, 1, "svg-parse", HARD, RULES["svg-parse"][2], str(exc)))
        return findings
    if "svg-meta" in disabled:
        return findings
    problems = _svg_problems(root)
    if problems:
        findings.append(Finding(path, 1, 1, "svg-meta", HARD, RULES["svg-meta"][2], "; ".join(problems)))
    return findings


# ----------------------------------------------------------------------------- markdown rules

def lint(text, filename="<stdin>", disabled=(), base_dir=None):
    """Check one Markdown document. Returns a list of findings.

    base_dir is the directory for resolving relative SVG paths. None skips svg-meta.
    """
    findings = []
    lines, blocks = _classify(text)

    def emit(rule, line, col, excerpt, extra=""):
        if rule in disabled:
            return
        sev, _, msg = RULES[rule]
        if extra:
            msg = msg + " " + extra
        findings.append(Finding(filename, line, col, rule, sev, msg, _excerpt(excerpt)))

    total = len(text.splitlines())
    if total > MAX_LINES:
        emit("doc-length", 1, 1, "%d lines" % total)

    # ---- fenced blocks: mermaid, ascii-art
    for start, info, body in blocks:
        if info.startswith("mermaid"):
            emit("mermaid", start, 1, "```" + info)
        elif not info:
            art_lines = [ln for ln in body if BOX_DRAWING.search(ln) or ART_PATTERN.search(ln)]
            hits = sum(len(ART_PATTERN.findall(ln)) for ln in body)
            boxes = sum(len(BOX_DRAWING.findall(ln)) for ln in body)
            if len(art_lines) >= 3 and (boxes or hits >= 2):
                emit("ascii-art", start, 1, art_lines[0])

    # ---- line-based rules
    must_at = shall_at = None
    stack = []  # indents of the open list levels
    prev_nonblank = None  # Line
    svg_refs = []
    for i, ln in enumerate(lines):
        if ln.kind in ("blank", "comment", "code"):
            continue
        if ln.kind == "fence":
            prev_nonblank = ln
            continue
        texts = []  # (text, column offset)
        if ln.kind in ("heading", "item", "prose", "html"):
            texts.append((ln.text, ln.text_off))
        elif ln.kind == "table":
            texts.extend(zip(ln.cells, ln.cell_offs))

        # vague words and obligation words in every kind of text
        for t, off in texts:
            for m in VAGUE_EN_RE.finditer(t):
                emit("vague-word", ln.no, off + m.start() + 1, m.group(0))
            for m in VAGUE_SIZE_RE.finditer(t):
                emit("vague-size", ln.no, off + m.start() + 1, m.group(0))
            for m in VAGUE_ZH_RE.finditer(t):
                emit("vague-word-zh", ln.no, off + m.start() + 1, m.group(0))
            if must_at is None:
                m = MUST.search(t)
                if m:
                    must_at = (ln.no, off + m.start() + 1, m.group(0))
            if shall_at is None:
                m = SHALL.search(t)
                if m:
                    shall_at = (ln.no, off + m.start() + 1, m.group(0))

        # inline enumerations in prose and list items (not in table cells or headings)
        if ln.kind in ("item", "prose"):
            for sent in SENT_SPLIT.split(ln.text):
                if not sent or not sent.strip():
                    continue
                m = INLINE_EN.search(sent) or INLINE_ZH.search(sent)
                if m:
                    emit("inline-list", ln.no, ln.text_off + ln.text.find(sent) + m.start() + 1, m.group(0))

        # list structure
        if ln.kind == "item":
            n = ln.indent
            if not stack:
                stack.append(n)
                if prev_nonblank is not None and prev_nonblank.kind in ("prose", "html") \
                        and prev_nonblank.text.strip() \
                        and not prev_nonblank.text.rstrip().endswith((":", "：")):
                    emit("list-lead-in", ln.no, 1, ln.raw, "Previous line: \"%s\""
                         % _excerpt(prev_nonblank.text))
            elif n > stack[-1]:
                stack.append(n)
            elif n < stack[-1]:
                while stack and stack[-1] > n:
                    stack.pop()
                if not stack or stack[-1] != n:
                    stack.append(n)
            if len(stack) > MAX_LIST_DEPTH:
                emit("list-depth", ln.no, n + 1, ln.raw, "Level %d." % len(stack))
        elif ln.kind == "prose" and ln.indent == 0:
            stack = []
        elif ln.kind in ("heading", "table"):
            stack = []

        # figures: caption and SVG metadata
        images = [m.group(1) for m in IMAGE_MD.finditer(ln.raw)]
        images += [m.group(1) for m in IMAGE_HTML.finditer(ln.raw)]
        if images:
            j = i + 1
            while j < len(lines) and (lines[j].kind == "blank" or CLOSING_TAG_LINE.match(lines[j].raw)
                                      or lines[j].kind == "comment"):
                j += 1
            nxt = lines[j] if j < len(lines) else None
            if nxt is None or nxt.kind in ("heading", "item", "table", "fence") \
                    or (nxt.kind == "html" and not nxt.text.strip()) \
                    or IMAGE_MD.search(nxt.raw) or IMAGE_HTML.search(nxt.raw):
                emit("figure-caption", ln.no, 1, ln.raw)
            for src in images:
                if src.lower().endswith(".svg") and not URL.match(src):
                    svg_refs.append((ln.no, src))

        prev_nonblank = ln

    if must_at and shall_at:
        later = max(must_at, shall_at)
        emit("obligation-mix", later[0], later[1], later[2],
             "'must' at line %d, 'shall' at line %d." % (must_at[0], shall_at[0]))

    if base_dir is not None:
        seen = set()
        for line_no, src in svg_refs:
            p = os.path.normpath(os.path.join(base_dir, src.split("#")[0].split("?")[0]))
            if p in seen or not os.path.isfile(p):
                continue
            seen.add(p)
            for f in lint_svg(p, disabled):
                findings.append(Finding(filename, line_no, 1, f.rule, f.severity,
                                        f.message + " (%s)" % p, f.excerpt))

    findings.sort(key=lambda f: (f.file, f.line, f.col, f.rule))
    return findings


# ----------------------------------------------------------------------------- delegation

def find_repo_root():
    """Walk up from this script to the directory that holds the sibling linters."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "skills" / "asd-ste100" / "scripts" / "ste-lint.py").is_file() \
                and (parent / "skills" / "nasa-writing" / "scripts" / "nasa-lint.py").is_file():
            return parent
    return None


def delegate(md_files, root):
    """Run ste-lint and nasa-lint on the Markdown files and return their findings."""
    out = []
    if not md_files:
        return out
    jobs = [
        ("ste", root / "skills" / "asd-ste100" / "scripts" / "ste-lint.py", ["--json"],
         "violations", "level", "match"),
        ("nasa", root / "skills" / "nasa-writing" / "scripts" / "nasa-lint.py",
         ["--mode", "report", "--json"], "findings", "severity", "excerpt"),
    ]
    for prefix, script, flags, key, sev_key, ex_key in jobs:
        cmd = [sys.executable, str(script)] + flags + list(md_files)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            data = json.loads(proc.stdout)
        except (OSError, ValueError) as exc:
            print("doc-lint: %s failed (%s); its findings are not included" % (script.name, exc),
                  file=sys.stderr)
            continue
        for f in data.get(key, []):
            sev = f.get(sev_key, ADV)
            sev = HARD if sev in ("hard", "advisory-free") else ADV
            out.append(Finding(f.get("file", "?"), int(f.get("line", 0)), int(f.get("col", 0)),
                               prefix + ":" + f.get("rule", "?"), sev, f.get("message", ""),
                               _excerpt(str(f.get(ex_key, "")))))
    return out


# ----------------------------------------------------------------------------- cli

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
    print("%-16s %-9s %-36s %s" % ("rule", "severity", "source", "message"))
    for rid, (sev, src, msg) in RULES.items():
        print("%-16s %-9s %-36s %s" % (rid, sev, src, msg))
    print("%-16s %-9s %-36s %s" % ("ste:*", "(theirs)", "asd-ste100/scripts/ste-lint.py",
                                   "merged when found and --no-delegate is not given"))
    print("%-16s %-9s %-36s %s" % ("nasa:*", "(theirs)", "nasa-writing/scripts/nasa-lint.py",
                                   "merged when found and --no-delegate is not given"))


def collect(paths):
    """Expand files and directories into (md_files, svg_files)."""
    md, svg = [], []
    for p in paths:
        if os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
                for name in sorted(filenames):
                    full = os.path.join(dirpath, name)
                    if name.lower().endswith(".md"):
                        md.append(full)
                    elif name.lower().endswith(".svg"):
                        svg.append(full)
        elif p.lower().endswith(".svg"):
            svg.append(p)
        else:
            md.append(p)
    return md, svg


CLEAN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100" role="img">
  <title id="title">Two boxes</title>
  <desc id="desc">Box A sends a request to box B.</desc>
  <rect x="1" y="1" width="198" height="98" rx="8" fill="#FFFDF6" stroke="#E5E2D2"/>
  <text x="20" y="50">A</text>
</svg>
"""

CLEAN_DOC = """# Worker lifecycle

The worker claims one job at a time. This document names the states and the checks.

The worker runs these checks before it claims a job:

- the lease is free
- `ready_at` has passed
- attempts are left

| State | Owner |
|---|---|
| queued | `claim()` |
| running | `finish()` |

```python
def claim(job):
    return job.state == "queued"
```

The figure shows the two states and the one transition between them.

![Two boxes](figures/clean.svg)

*Box A sends a request to box B.*

## Steps

Do these steps to restart the worker:

1. Stop the worker.
2. Start the worker.
   - If the start fails, read the log.
"""


def selftest():
    cases = [
        # (text, rules that must appear, rules that must not appear)
        ("x\n" * 801, {"doc-length"}, set()),
        ("x\n" * 800, set(), {"doc-length"}),
        ("The fields are name, size, and owner.", {"inline-list"}, set()),
        ("The fields are name, size, owner.", {"inline-list"}, set()),
        ("The fields are name and size.", set(), {"inline-list"}),
        ("字段有名称、大小、所有者。", {"inline-list"}, set()),
        ("| a, b, and c | d |\n|---|---|\n| e, f, and g | h |", set(), {"inline-list"}),
        ("# Name, size, and owner", set(), {"inline-list"}),
        ("Some text here\n\n- one\n- two", {"list-lead-in"}, set()),
        ("The list has two items:\n\n- one\n- two", set(), {"list-lead-in"}),
        ("## Heading\n\n- one\n- two", set(), {"list-lead-in"}),
        ("Items:\n- one\n  - two\n    - three", {"list-depth"}, set()),
        ("Items:\n- one\n  - two\n- three\n  - four", set(), {"list-depth"}),
        ("Steps:\n1. one\n   - two\n     - three", {"list-depth"}, set()),
        ("The service is robust and handles errors.", {"vague-word"}, set()),
        ("Use the flag as appropriate, etc.", {"vague-word"}, set()),
        ("Simply ensure the cache is warm and/or empty.", {"vague-word"}, set()),
        ("Run `ensure.sh` and read [the guide](robust.md).", set(), {"vague-word"}),
        ("The file is small and the run is fast.", {"vague-size"}, {"vague-word"}),
        ("The worker may retry. It could fail. It should log.", set(), {"vague-word", "vague-size"}),
        ("配置一般放在根目录。", {"vague-word-zh"}, set()),
        ("支持 JSON、YAML、TOML 等。", {"vague-word-zh"}, set()),
        ("支持 JSON 和 YAML。", set(), {"vague-word-zh"}),
        ("The worker must stop. The manager shall log it.", {"obligation-mix"}, set()),
        ("The worker must stop. The manager must log it.", set(), {"obligation-mix"}),
        ("Use `shall` only in specs. The worker must stop.", set(), {"obligation-mix"}),
        ("```mermaid\ngraph TD\nA-->B\n```", {"mermaid"}, set()),
        ("```\n+-----+     +-----+\n|  A  | --> |  B  |\n+-----+     +-----+\n```", {"ascii-art"}, set()),
        ("```\n┌───┐\n│ A │\n└───┘\n```", {"ascii-art"}, set()),
        ("```python\nx = 1\n```\n\n```\n$ run --> out\n```", set(), {"ascii-art", "mermaid"}),
        ("Point first.\n\n![fig](a.svg)\n\n## Next", {"figure-caption"}, set()),
        ("Point first.\n\n![fig](a.svg)\n- item", {"figure-caption"}, set()),
        ("Point first.\n\n![fig](a.svg)\n\n*The caption.*", set(), {"figure-caption"}),
        ("<p align=\"center\">\n  <img src=\"a.svg\" width=\"900\" alt=\"x\"/>\n</p>\n"
         "<p align=\"center\"><sub>The caption.</sub></p>", set(), {"figure-caption"}),
        ("Code `etc.` and ``robust`` are fine.\n\n```\nrobust etc. and/or\n```",
         set(), {"vague-word"}),
        ("<!-- robust etc. -->\nClean line.", set(), {"vague-word"}),
    ]
    failed = 0
    for text, must, must_not in cases:
        got = {f.rule for f in lint(text)}
        miss, extra = must - got, must_not & got
        if miss or extra:
            failed += 1
            print("FAIL %r\n  missing=%s unexpected=%s got=%s" % (text[:60], sorted(miss), sorted(extra),
                                                                 sorted(got)))

    svg_cases = [
        (CLEAN_SVG, set()),
        (CLEAN_SVG.replace("<title id=\"title\">Two boxes</title>", ""), {"svg-meta"}),
        (CLEAN_SVG.replace("<desc id=\"desc\">Box A sends a request to box B.</desc>", ""), {"svg-meta"}),
        (CLEAN_SVG.replace("fill=\"#FFFDF6\"", "fill=\"none\""), {"svg-meta"}),
        (CLEAN_SVG.replace("width=\"198\" height=\"98\"", "width=\"50\" height=\"50\""), {"svg-meta"}),
        (CLEAN_SVG.replace("fill=\"#FFFDF6\"", "fill=\"none\"").replace(
            "role=\"img\"", "style=\"background:#fff\""), set()),
        (CLEAN_SVG.replace("width=\"198\" height=\"98\"", "width=\"100%\" height=\"100%\""), set()),
        ("<svg><title>x</title>", {"svg-parse"}),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for k, (svg, must) in enumerate(svg_cases):
            p = os.path.join(tmp, "case%d.svg" % k)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(svg)
            got = {f.rule for f in lint_svg(p)}
            if got != must:
                failed += 1
                print("FAIL svg case %d: expected=%s got=%s" % (k, sorted(must), sorted(got)))
        # a clean document with a referenced SVG yields zero findings
        os.makedirs(os.path.join(tmp, "figures"))
        with open(os.path.join(tmp, "figures", "clean.svg"), "w", encoding="utf-8") as fh:
            fh.write(CLEAN_SVG)
        got = lint(CLEAN_DOC, "clean.md", base_dir=tmp)
        if got:
            failed += 1
            print("FAIL clean document: %s" % [(f.rule, f.line, f.excerpt) for f in got])
        # a referenced SVG without a title is reported at the embed line
        with open(os.path.join(tmp, "figures", "clean.svg"), "w", encoding="utf-8") as fh:
            fh.write(CLEAN_SVG.replace("<title id=\"title\">Two boxes</title>", ""))
        got = {f.rule for f in lint(CLEAN_DOC, "clean.md", base_dir=tmp)}
        if got != {"svg-meta"}:
            failed += 1
            print("FAIL referenced svg: got=%s" % sorted(got))
    total = len(cases) + len(svg_cases) + 2
    print("selftest: %d/%d passed" % (total - failed, total))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mechanical checks for the doc-writing skill.")
    ap.add_argument("paths", nargs="*", help="Markdown or SVG files, or directories")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--baseline", type=int, default=0, help="tolerate N hard findings")
    ap.add_argument("--disable", default="", help="comma-separated rule ids to silence (ste:/nasa: ids allowed)")
    ap.add_argument("--no-delegate", action="store_true", help="do not run ste-lint and nasa-lint")
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
    unknown = {d for d in disabled if ":" not in d} - set(RULES)
    if unknown:
        ap.error("unknown rule id(s): %s" % ", ".join(sorted(unknown)))
    md_files, svg_files = collect(args.paths)
    findings = []
    for path in md_files:
        with open(path, encoding="utf-8") as fh:
            findings += lint(fh.read(), path, disabled, os.path.dirname(os.path.abspath(path)))
    for path in svg_files:
        findings += lint_svg(path, disabled)
    if not args.no_delegate:
        root = find_repo_root()
        if root is None:
            print("doc-lint: sibling linters not found above %s; delegation skipped" % Path(__file__).resolve(),
                  file=sys.stderr)
        else:
            findings += [f for f in delegate(md_files, root) if f.rule not in disabled]
    findings.sort(key=lambda f: (f.file, f.line, f.col, f.rule))
    return report(findings, args.json, args.baseline)


if __name__ == "__main__":
    sys.exit(main())
