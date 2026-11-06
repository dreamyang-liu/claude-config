#!/usr/bin/env python3
"""adr-lint: deterministic checks for an ADR directory.

Standard library only. The linter checks the form that the architecture-decisions
skill (SKILL.md) prescribes: the file names and numbers, the title, the status,
date and revert-cost lines, the section headings and their order, the supersede
links between ADRs, and the index in README.md. It cannot apply the revert test,
judge whether a decision deserved an ADR, or tell whether the user accepted it.
A clean run means only that the configured patterns matched.

Usage:
    adr-lint.py [DIR] [--git] [--json] [--baseline N] [--disable rule1,rule2]
                (DIR defaults to docs/decisions)
    adr-lint.py --list-rules
    adr-lint.py --selftest

Exit status: 1 when hard findings exceed --baseline, 0 otherwise.
Advisory findings never change the exit status. Exit 2 when DIR does not exist.

With --git, the linter also compares each ADR with its HEAD version and reports
an edit to an accepted ADR outside its status line. It skips files that git
does not track, and does nothing when git is not available.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass

HARD, ADV = "hard", "advisory"

WHERE = "SKILL.md: Where the ADRs live"
WRITE = "SKILL.md: Write the ADR"
CHANGE = "SKILL.md: Change a decision"
CHECK = "SKILL.md: Checklist"

DEFAULT_DIR = "docs/decisions"
ONE_SCREEN_LINES = 120
REQUIRED_SECTIONS = ("Context", "Decision", "Alternatives", "Consequences", "Links")

# rule id -> (severity, source, message)
RULES = {
    "file-name": (HARD, WHERE,
                  "File name is not <NNNN>-<slug>.md with a four-digit number and a kebab-case slug."),
    "number-reuse": (HARD, WHERE, "Two ADR files share one number. Never reuse a number."),
    "number-gap": (ADV, WHERE,
                   "ADR numbers are not contiguous from 0001. Each number is the next after the highest."),
    "title": (HARD, WRITE, "First line is not '# ADR-<NNNN>: <the decision>' with the file's number."),
    "status-line": (HARD, WRITE + "; " + CHANGE,
                    "No '- **Status:** <value>' line right after the title, or the value is not "
                    "'Accepted', 'Superseded by ADR-<NNNN>', or 'Deprecated <YYYY-MM-DD> <reason>'."),
    "date-line": (HARD, WRITE, "No '- **Date:** YYYY-MM-DD' line, or the date is not valid."),
    "revert-cost-line": (HARD, WRITE, "No '- **Revert cost:** <text>' line."),
    "sections": (HARD, WRITE + "; " + CHECK,
                 "Missing or misordered sections. Use '## Context', '## Decision', '## Alternatives', "
                 "'## Consequences', '## Links' in that order."),
    "decision-actor": (ADV, WRITE, "The first sentence of '## Decision' does not start with 'We'."),
    "alternatives-format": (ADV, WRITE,
                            "'## Alternatives' has no list item of the form '- **<alternative>:** <why not>'."),
    "one-screen": (ADV, WRITE, "Keep it to about one screen (%d lines). Put the details in docs/*.md and "
                               "link that file." % ONE_SCREEN_LINES),
    "supersedes-link": (HARD, CHANGE,
                        "A 'Superseded by ADR-<NNNN>' status and a 'Supersedes ADR-<MMMM>' context must "
                        "point at each other, and both files must exist."),
    "index-missing": (HARD, WHERE + "; " + WRITE,
                      "README.md in the directory is missing, or has no table row that links this ADR."),
    "index-stale": (HARD, CHANGE + "; " + CHECK,
                    "The index row's Status does not match the ADR file, or the row links a missing file."),
    "index-order": (ADV, WHERE, "Index rows are not in ascending number order. List the oldest first."),
    "accepted-edited": (HARD, CHANGE + "; " + CHECK,
                        "Do not edit an accepted ADR; write a new ADR that supersedes it. Only the "
                        "status line, a typo or a link may change."),
}

FILE_NAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
FILE_NUMBER = re.compile(r"^(\d{4})\b")
TITLE = re.compile(r"^# ADR-(\d{4}): (\S.*)$")
STATUS_LINE = re.compile(r"^- \*\*Status:\*\* (.+?)\s*$")
STATUS_ACCEPTED = re.compile(r"^Accepted$")
STATUS_SUPERSEDED = re.compile(r"^Superseded by ADR-(\d{4})$")
STATUS_DEPRECATED = re.compile(r"^Deprecated\b.*\b(\d{4}-\d{2}-\d{2})\b.*\S")
DATE_LINE = re.compile(r"^- \*\*Date:\*\* (.*?)\s*$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REVERT_COST_LINE = re.compile(r"^- \*\*Revert cost:\*\* \S")
SECTION = re.compile(r"^## (.+?)\s*$")
SUPERSEDES = re.compile(r"\bSupersedes ADR-(\d{4})\b")
ALTERNATIVE_ITEM = re.compile(r"^\s*- \*\*[^*]+?(?::\*\*|\*\*:) +\S")
WE = re.compile(r"^We\b")
TABLE_ROW = re.compile(r"^\s*\|")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
ROW_LINK = re.compile(r"\]\(([^)\s]+\.md)\)")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class Finding:
    file: str
    line: int
    col: int
    rule: str
    severity: str
    message: str
    excerpt: str


class Adr:
    """One parsed ADR file."""

    def __init__(self, name, text):
        self.name = name
        self.text = text
        self.lines = text.splitlines()
        m = FILE_NUMBER.match(name)
        self.number = m.group(1) if m else None
        self.title_number = None
        self.status = None  # (line_no, value)
        self.sections = {}  # heading -> (line_no, body lines)
        self.section_order = []
        self._parse()

    def _parse(self):
        if self.lines:
            m = TITLE.match(self.lines[0])
            if m:
                self.title_number = m.group(1)
        # the first non-blank line after the title is the status line
        for i in range(1, len(self.lines)):
            if not self.lines[i].strip():
                continue
            m = STATUS_LINE.match(self.lines[i])
            if m:
                self.status = (i + 1, m.group(1))
            break
        current = None
        for i, raw in enumerate(self.lines):
            m = SECTION.match(raw)
            if m:
                current = m.group(1)
                self.section_order.append(current)
                self.sections[current] = (i + 1, [])
            elif current is not None:
                self.sections[current][1].append(raw)

    @property
    def status_value(self):
        return self.status[1] if self.status else None

    @property
    def status_word(self):
        return self.status_value.split()[0] if self.status_value else None

    def find_line(self, regex):
        for i, raw in enumerate(self.lines):
            if regex.match(raw):
                return i + 1, raw
        return None, None

    def supersedes(self):
        """Numbers named by 'Supersedes ADR-MMMM' in the Context section (or the whole file)."""
        if "Context" in self.sections:
            body = self.sections["Context"][1]
        else:
            body = [l for i, l in enumerate(self.lines) if not (self.status and i + 1 == self.status[0])]
        found = []
        for raw in body:
            for m in SUPERSEDES.finditer(raw):
                found.append(m.group(1))
        return found


def _excerpt(s):
    s = (s or "").strip()
    return s if len(s) <= 80 else s[:77] + "..."


def _status_ok(value):
    return bool(STATUS_ACCEPTED.match(value) or STATUS_SUPERSEDED.match(value)
                or STATUS_DEPRECATED.match(value))


def _parse_index(text):
    """Return (rows, status_col) for the README table. rows: (line_no, raw, link, cells)."""
    rows, status_col, header_seen = [], None, False
    for i, raw in enumerate(text.splitlines()):
        if not TABLE_ROW.match(raw) or TABLE_SEP.match(raw):
            continue
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if not header_seen:
            header_seen = True
            lowered = [c.lower() for c in cells]
            status_col = lowered.index("status") if "status" in lowered else None
            if status_col is not None or not ROW_LINK.search(raw):
                continue
        m = ROW_LINK.search(raw)
        rows.append((i + 1, raw, m.group(1) if m else None, cells))
    if status_col is None:
        status_col = 2
    return rows, status_col


def _git(args, cwd):
    try:
        return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    except (OSError, FileNotFoundError):
        return None


def _accepted_edited(directory, adr, emit):
    head = _git(["show", "HEAD:./" + adr.name], directory)
    if head is None or head.returncode != 0:
        return  # no git, no HEAD, or untracked file
    head_adr = Adr(adr.name, head.stdout)
    if head_adr.status_word != "Accepted":
        return
    diff = _git(["diff", "-U0", "HEAD", "--", adr.name], directory)
    if diff is None or diff.returncode != 0:
        return
    new_line = 0
    for raw in diff.stdout.splitlines():
        m = HUNK.match(raw)
        if m:
            new_line = int(m.group(1))
            continue
        if raw.startswith(("+++", "---")):
            continue
        if raw.startswith("+"):
            if "**Status:**" not in raw:
                emit("accepted-edited", adr.name, new_line, raw[1:])
                return
            new_line += 1
        elif raw.startswith("-") and "**Status:**" not in raw:
            emit("accepted-edited", adr.name, max(new_line, 1), raw[1:])
            return


def lint(directory, disabled=(), use_git=False):
    findings = []

    def emit(rule_id, file, line, excerpt="", extra=""):
        if rule_id in disabled:
            return
        sev, _, msg = RULES[rule_id]
        if extra:
            msg = msg + " " + extra
        findings.append(Finding(file, line, 1, rule_id, sev, msg, _excerpt(excerpt)))

    names = sorted(n for n in os.listdir(directory)
                   if n.endswith(".md") and n != "README.md" and os.path.isfile(os.path.join(directory, n)))
    adrs = []
    for name in names:
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            adrs.append(Adr(name, fh.read()))

    # file names and numbers
    by_number = {}
    for adr in adrs:
        if not FILE_NAME.match(adr.name):
            emit("file-name", adr.name, 1, adr.name)
        if adr.number:
            by_number.setdefault(adr.number, []).append(adr)
    for number, group in sorted(by_number.items()):
        if len(group) > 1:
            for adr in group:
                emit("number-reuse", adr.name, 1, adr.name,
                     "Also used by %s." % ", ".join(a.name for a in group if a is not adr))
    numbers = sorted(int(n) for n in by_number)
    if numbers:
        expected = list(range(1, numbers[-1] + 1))
        missing = sorted(set(expected) - set(numbers))
        if missing or numbers[0] != 1:
            emit("number-gap", "", 1, "", "Missing: %s." % ", ".join("%04d" % n for n in missing))

    # each file
    for adr in adrs:
        first = adr.lines[0] if adr.lines else ""
        if adr.title_number is None or adr.title_number != adr.number:
            emit("title", adr.name, 1, first)
        if adr.status is None:
            line = 2 if len(adr.lines) > 1 else 1
            emit("status-line", adr.name, line, adr.lines[line - 1] if adr.lines else "")
        elif not _status_ok(adr.status_value):
            emit("status-line", adr.name, adr.status[0], adr.lines[adr.status[0] - 1])
        line_no, raw = adr.find_line(DATE_LINE)
        if line_no is None:
            emit("date-line", adr.name, 1, first)
        else:
            value = DATE_LINE.match(raw).group(1)
            valid = bool(ISO_DATE.match(value))
            if valid:
                try:
                    datetime.date.fromisoformat(value)
                except ValueError:
                    valid = False
            if not valid:
                emit("date-line", adr.name, line_no, raw)
        line_no, raw = adr.find_line(REVERT_COST_LINE)
        if line_no is None:
            emit("revert-cost-line", adr.name, 1, first)
        present = [s for s in adr.section_order if s in REQUIRED_SECTIONS]
        missing = [s for s in REQUIRED_SECTIONS if s not in adr.sections]
        in_order = present == [s for s in REQUIRED_SECTIONS if s in present]
        if missing or not in_order:
            extra = ("Missing: %s." % ", ".join(missing)) if missing else "Order found: %s." % ", ".join(present)
            emit("sections", adr.name, 1, first, extra)
        if "Decision" in adr.sections:
            line_no, body = adr.sections["Decision"]
            text_lines = [(line_no + 1 + i, l) for i, l in enumerate(body) if l.strip()]
            if text_lines:
                n, raw = text_lines[0]
                stripped = re.sub(r"^[\s>*_\-]+", "", raw)
                if not WE.match(stripped):
                    emit("decision-actor", adr.name, n, raw)
            else:
                emit("decision-actor", adr.name, line_no, adr.lines[line_no - 1], "The section is empty.")
        if "Alternatives" in adr.sections:
            line_no, body = adr.sections["Alternatives"]
            if not any(ALTERNATIVE_ITEM.match(l) for l in body):
                emit("alternatives-format", adr.name, line_no, adr.lines[line_no - 1])
        if len(adr.lines) > ONE_SCREEN_LINES:
            emit("one-screen", adr.name, ONE_SCREEN_LINES + 1, adr.lines[ONE_SCREEN_LINES],
                 "%d lines." % len(adr.lines))

    # supersede links in both directions
    first_by_number = {n: g[0] for n, g in by_number.items()}
    for adr in adrs:
        m = STATUS_SUPERSEDED.match(adr.status_value or "")
        if m:
            target = first_by_number.get(m.group(1))
            if target is None:
                emit("supersedes-link", adr.name, adr.status[0], adr.lines[adr.status[0] - 1],
                     "ADR-%s does not exist in the directory." % m.group(1))
            elif adr.number not in target.supersedes():
                emit("supersedes-link", adr.name, adr.status[0], adr.lines[adr.status[0] - 1],
                     "%s does not say 'Supersedes ADR-%s'." % (target.name, adr.number))
        for old_number in adr.supersedes():
            old = first_by_number.get(old_number)
            line_no, raw = adr.find_line(re.compile(r".*\bSupersedes ADR-%s\b" % old_number))
            if old is None:
                emit("supersedes-link", adr.name, line_no or 1, raw,
                     "ADR-%s does not exist in the directory." % old_number)
            elif old.status_value != "Superseded by ADR-%s" % adr.number:
                emit("supersedes-link", adr.name, line_no or 1, raw,
                     "%s has status '%s', not 'Superseded by ADR-%s'." % (old.name, old.status_value,
                                                                            adr.number))

    # the index
    index_path = os.path.join(directory, "README.md")
    if not os.path.isfile(index_path):
        if adrs:
            emit("index-missing", "README.md", 1, "", "The file does not exist.")
    else:
        with open(index_path, encoding="utf-8") as fh:
            index_text = fh.read()
        rows, status_col = _parse_index(index_text)
        linked = {}
        for line_no, raw, link, cells in rows:
            if link is None:
                continue
            linked.setdefault(os.path.basename(link), (line_no, raw, cells))
        for adr in adrs:
            if adr.name not in linked:
                emit("index-missing", "README.md", 1, "", "No row links %s." % adr.name)
                continue
            line_no, raw, cells = linked[adr.name]
            index_status = cells[status_col].split()[0] if len(cells) > status_col and cells[status_col] else ""
            if adr.status_word and index_status != adr.status_word:
                emit("index-stale", "README.md", line_no, raw,
                     "Row says '%s'; %s says '%s'." % (index_status or "(empty)", adr.name, adr.status_word))
        existing = {a.name for a in adrs}
        for line_no, raw, link, cells in rows:
            if link and os.path.basename(link) not in existing:
                emit("index-stale", "README.md", line_no, raw, "%s does not exist." % link)
        row_numbers = []
        for line_no, raw, link, cells in rows:
            m = FILE_NUMBER.match(os.path.basename(link or ""))
            if m:
                row_numbers.append((int(m.group(1)), line_no, raw))
        for prev, cur in zip(row_numbers, row_numbers[1:]):
            if cur[0] <= prev[0]:
                emit("index-order", "README.md", cur[1], cur[2])
                break

    if use_git:
        for adr in adrs:
            _accepted_edited(directory, adr, emit)

    findings.sort(key=lambda f: (f.file, f.line, f.col, f.rule))
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
    print("%-22s %-9s %-44s %s" % ("rule", "severity", "source", "message"))
    for rid, (sev, src, msg) in RULES.items():
        print("%-22s %-9s %-44s %s" % (rid, sev, src, msg))


# --------------------------------------------------------------------------- selftest

def _adr(number, slug_title, status="Accepted", date="2026-01-15", context="The problem.",
         decision="We do the thing.", alternatives="- **Other way:** too slow.", revert="- **Revert cost:** "
         "one revert does not restore the written data.", sections=None, extra_lines=0):
    body = sections or [
        ("Context", context),
        ("Decision", decision),
        ("Alternatives", alternatives),
        ("Consequences", "- Easier: one thing. Harder: another."),
        ("Links", "- PR #1"),
    ]
    out = ["# ADR-%s: %s" % (number, slug_title), "", "- **Status:** %s" % status,
           "- **Date:** %s" % date]
    if revert:
        out.append(revert)
    for heading, text in body:
        out += ["", "## " + heading, "", text]
    out += ["filler"] * extra_lines
    return "\n".join(out) + "\n"


def _index(rows):
    lines = ["# Decisions", "", "| ADR | Decision | Status | Date |", "|---|---|---|---|"]
    for number, slug, status in rows:
        lines.append("| [%s](%s-%s.md) | %s | %s | 2026-01-15 |" % (number, number, slug, slug, status))
    return "\n".join(lines) + "\n"


def _valid_set():
    return {
        "0001-first.md": _adr("0001", "First decision"),
        "0002-second.md": _adr("0002", "Second decision", status="Superseded by ADR-0003"),
        "0003-third.md": _adr("0003", "Third decision", context="Supersedes ADR-0002 because it failed."),
        "README.md": _index([("0001", "first", "Accepted"), ("0002", "second", "Superseded by ADR-0003"),
                             ("0003", "third", "Accepted")]),
    }


def _run_case(files, use_git=False, git_setup=None):
    tmp = tempfile.mkdtemp(prefix="adr-lint-")
    try:
        for name, text in files.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        if git_setup:
            git_setup(tmp)
        return {f.rule for f in lint(tmp, use_git=use_git)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _git_edit_accepted(tmp):
    """Commit the valid set, then edit the decision of the accepted ADR 0001."""
    def g(*args):
        subprocess.run(["git"] + list(args), cwd=tmp, capture_output=True, text=True, check=True)
    g("init", "-q")
    g("config", "user.email", "selftest@example.com")
    g("config", "user.name", "selftest")
    g("add", "-A")
    g("commit", "-q", "-m", "Add ADRs")
    path = os.path.join(tmp, "0001-first.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace("We do the thing.", "We do another thing."))


def _git_status_only(tmp):
    """Commit the valid set, then change only the status line of 0001."""
    _git_edit_accepted(tmp)
    path = os.path.join(tmp, "0001-first.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace("We do another thing.", "We do the thing.")
    text = text.replace("- **Status:** Accepted", "- **Status:** Deprecated 2026-02-01 no longer needed")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def selftest():
    valid = _valid_set()

    def variant(**changes):
        files = dict(valid)
        for k, v in changes.items():
            if v is None:
                files.pop(k, None)
            else:
                files[k] = v
        return files

    def rename(files, old, new):
        files = dict(files)
        files[new] = files.pop(old)
        return files

    cases = [
        # (label, files, rules that must appear, rules that must not appear, use_git, git_setup)
        ("valid set", valid, set(), set(RULES), False, None),
        ("bad file name", rename(valid, "0001-first.md", "0001_First.md"), {"file-name"}, set(), False, None),
        ("number reuse", variant(**{"0001-other.md": _adr("0001", "Other")}), {"number-reuse"}, set(), False, None),
        ("number gap", variant(**{"0003-third.md": None, "0005-fifth.md": _adr("0005", "Fifth",
                                  context="Supersedes ADR-0002 because it failed."),
                                  "0002-second.md": _adr("0002", "Second", status="Superseded by ADR-0005"),
                                  "README.md": _index([("0001", "first", "Accepted"),
                                                       ("0002", "second", "Superseded by ADR-0005"),
                                                       ("0005", "fifth", "Accepted")])}),
         {"number-gap"}, {"supersedes-link", "index-missing", "index-stale"}, False, None),
        ("title number", variant(**{"0001-first.md": _adr("0009", "First decision")}), {"title"}, set(), False, None),
        ("title shape", variant(**{"0001-first.md": "# First decision\n" + _adr("0001", "x").split("\n", 1)[1]}),
         {"title"}, set(), False, None),
        ("status missing", variant(**{"0001-first.md": _adr("0001", "First").replace("- **Status:** Accepted\n", "")}),
         {"status-line"}, set(), False, None),
        ("status value", variant(**{"0001-first.md": _adr("0001", "First", status="Proposed")}),
         {"status-line"}, set(), False, None),
        ("deprecated no date", variant(**{"0001-first.md": _adr("0001", "First", status="Deprecated, replaced")}),
         {"status-line"}, set(), False, None),
        ("deprecated ok", variant(**{"0001-first.md": _adr("0001", "First", status="Deprecated 2026-03-01 obsolete"),
                                     "README.md": _index([("0001", "first", "Deprecated 2026-03-01"),
                                                          ("0002", "second", "Superseded by ADR-0003"),
                                                          ("0003", "third", "Accepted")])}),
         set(), {"status-line", "index-stale"}, False, None),
        ("date missing", variant(**{"0001-first.md": _adr("0001", "First").replace("- **Date:** 2026-01-15\n", "")}),
         {"date-line"}, set(), False, None),
        ("date invalid", variant(**{"0001-first.md": _adr("0001", "First", date="2026-13-40")}),
         {"date-line"}, set(), False, None),
        ("date not iso", variant(**{"0001-first.md": _adr("0001", "First", date="15 Jan 2026")}),
         {"date-line"}, set(), False, None),
        ("revert cost missing", variant(**{"0001-first.md": _adr("0001", "First", revert="")}),
         {"revert-cost-line"}, set(), False, None),
        ("section missing", variant(**{"0001-first.md": _adr("0001", "First", sections=[
            ("Context", "x"), ("Decision", "We do."), ("Consequences", "- y"), ("Links", "- z")])}),
         {"sections"}, set(), False, None),
        ("section order", variant(**{"0001-first.md": _adr("0001", "First", sections=[
            ("Decision", "We do."), ("Context", "x"), ("Alternatives", "- **A:** no"),
            ("Consequences", "- y"), ("Links", "- z")])}),
         {"sections"}, set(), False, None),
        ("decision actor", variant(**{"0001-first.md": _adr("0001", "First", decision="The team does the thing.")}),
         {"decision-actor"}, set(), False, None),
        ("alternatives format", variant(**{"0001-first.md": _adr("0001", "First", alternatives="Other way: too slow.")}),
         {"alternatives-format"}, set(), False, None),
        ("one screen", variant(**{"0001-first.md": _adr("0001", "First", extra_lines=110)}),
         {"one-screen"}, set(), False, None),
        ("superseded target missing", variant(**{"0002-second.md": _adr("0002", "Second",
                                                                        status="Superseded by ADR-0007")}),
         {"supersedes-link"}, set(), False, None),
        ("superseded no back link", variant(**{"0003-third.md": _adr("0003", "Third")}),
         {"supersedes-link"}, set(), False, None),
        ("supersedes but old still accepted", variant(**{"0002-second.md": _adr("0002", "Second"),
                                                         "README.md": _index([("0001", "first", "Accepted"),
                                                                              ("0002", "second", "Accepted"),
                                                                              ("0003", "third", "Accepted")])}),
         {"supersedes-link"}, {"index-stale"}, False, None),
        ("index missing file", variant(**{"README.md": None}), {"index-missing"}, set(), False, None),
        ("index missing row", variant(**{"README.md": _index([("0001", "first", "Accepted"),
                                                              ("0002", "second", "Superseded by ADR-0003")])}),
         {"index-missing"}, set(), False, None),
        ("index stale status", variant(**{"README.md": _index([("0001", "first", "Accepted"),
                                                               ("0002", "second", "Accepted"),
                                                               ("0003", "third", "Accepted")])}),
         {"index-stale"}, set(), False, None),
        ("index dangling link", variant(**{"README.md": valid["README.md"] +
                                           "| [0004](0004-ghost.md) | ghost | Accepted | 2026-01-15 |\n"}),
         {"index-stale"}, set(), False, None),
        ("index order", variant(**{"README.md": _index([("0003", "third", "Accepted"), ("0001", "first", "Accepted"),
                                                        ("0002", "second", "Superseded by ADR-0003")])}),
         {"index-order"}, set(), False, None),
        ("accepted edited (git)", valid, {"accepted-edited"}, set(), True, _git_edit_accepted),
        ("accepted edited without --git", valid, set(), {"accepted-edited"}, False, _git_edit_accepted),
        ("status-only edit (git)", valid, set(), {"accepted-edited"}, True, _git_status_only),
    ]
    failed = 0
    for label, files, must, must_not, use_git, git_setup in cases:
        if git_setup and shutil.which("git") is None:
            continue
        got = _run_case(files, use_git=use_git, git_setup=git_setup)
        miss, extra = must - got, must_not & got
        if miss or extra:
            failed += 1
            print("FAIL [%s]\n  missing=%s unexpected=%s got=%s" % (label, sorted(miss), sorted(extra),
                                                                   sorted(got)))
    print("selftest: %d/%d passed" % (len(cases) - failed, len(cases)))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic checks for an ADR directory.")
    ap.add_argument("dir", nargs="?", default=DEFAULT_DIR, help="ADR directory (default: %s)" % DEFAULT_DIR)
    ap.add_argument("--git", action="store_true", help="also report an edit to an accepted ADR (vs. HEAD)")
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
    disabled = {d.strip() for d in args.disable.split(",") if d.strip()}
    unknown = disabled - set(RULES)
    if unknown:
        ap.error("unknown rule id(s): %s" % ", ".join(sorted(unknown)))
    if not os.path.isdir(args.dir):
        print("adr-lint: directory not found: %s" % args.dir, file=sys.stderr)
        return 2
    findings = lint(args.dir, disabled, args.git)
    return report(findings, args.json, args.baseline)


if __name__ == "__main__":
    sys.exit(main())
