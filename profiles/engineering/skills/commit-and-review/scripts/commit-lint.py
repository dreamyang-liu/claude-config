#!/usr/bin/env python3
"""commit-lint: deterministic checks for commit messages, the staged state, and PR bodies.

Standard library only. The linter checks the form that the commit-and-review skill
(SKILL.md) prescribes: one subject line with no body and no trailer, a staged diff
that is on a topic branch and holds only the files of the change, and a PR
description with What, Why, Tests and Deviations and no attribution line. It
cannot judge whether the subject describes the change, whether the tests are the
right ones, or whether the user approved anything. A clean run means only that
the configured patterns did not match.

Usage:
    commit-lint.py MSGFILE                 check a commit message file (git commit-msg hook)
    commit-lint.py --message "text"        check a commit message given inline
    commit-lint.py --commits RANGE         check each commit in a git range (HEAD~3..HEAD)
    commit-lint.py --staged                check the staged state of the current repository
    commit-lint.py --pr-body FILE          check a PR description in a file
    commit-lint.py --pr NUMBER             check the body of a PR via gh
    commit-lint.py --list-rules
    commit-lint.py --selftest

    Common options: [--json] [--baseline N] [--disable rule1,rule2]

Exit status: 1 when hard findings exceed --baseline, 0 otherwise. Advisory findings
never change the exit status. Exit 2 when git or gh is missing or fails for
--commits, --staged, --pr.

As a commit-msg hook: ln -s <path-to>/commit-lint.py .git/hooks/commit-msg
(or call it from the hook that core.hooksPath names).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass

HARD, ADV = "hard", "advisory"
MESSAGE, STAGED, PR = "message", "staged", "pr"

BEFORE = "SKILL.md: Before a commit"
COMMIT = "SKILL.md: The commit"
PULL = "SKILL.md: The pull request"
SCOPE = "SKILL.md: Reviewing a diff, step 1"
CHECK = "SKILL.md: Checklist"

SUBJECT_MAX = 72
MAX_FILES = 10
LARGE_FILE = 1024 * 1024

# rule id -> (severity, mode, source, message)
RULES = {
    "subject-empty": (HARD, MESSAGE, COMMIT, "No subject line."),
    "subject-length": (HARD, MESSAGE, COMMIT, "Subject is over %d characters." % SUBJECT_MAX),
    "body": (HARD, MESSAGE, COMMIT + "; " + CHECK, "The message has a body. Write one subject line only."),
    "trailer": (HARD, MESSAGE, COMMIT + "; " + CHECK,
                "The message has a trailer or an attribution line. Do not add a Co-Authored-By line "
                "or another trailer."),
    "subject-period": (ADV, MESSAGE, COMMIT, "Subject ends with a period. Subjects in git log --oneline do not."),
    "subject-imperative": (ADV, MESSAGE, COMMIT,
                           "Write the subject in the imperative, like `git log --oneline`."),
    "on-main": (HARD, STAGED, BEFORE + " step 2; " + CHECK, "The current branch is main. Make a topic branch first."),
    "too-many-files": (HARD, STAGED, BEFORE + " step 4; " + CHECK,
                       "More than %d files are staged. Split the change into smaller commits." % MAX_FILES),
    "scratch-file": (HARD, STAGED, SCOPE, "A staged file is under scratch/. It is not part of the change."),
    "large-file": (HARD, STAGED, SCOPE, "A staged file is over 1 MiB. Do not commit a large binary."),
    "host-path": (HARD, STAGED, SCOPE, "An added line contains a host path."),
    "debug-output": (ADV, STAGED, SCOPE, "An added line looks like debug output."),
    "nothing-staged": (ADV, STAGED, BEFORE + " step 3", "No file is staged."),
    "pr-sections": (HARD, PR, PULL + " step 3; " + CHECK,
                    "The description lacks a section. Use What, Why, Tests and Deviations."),
    "pr-attribution": (HARD, PR, PULL + " step 3; " + CHECK,
                       "The description has an attribution line or a trailer. Remove it."),
    "pr-section-empty": (ADV, PR, PULL + " step 3", "The section has no text."),
}

TRAILER = re.compile(r"^[A-Za-z-]+: ")
GENERATED = re.compile(r"Generated with", re.I)
NON_IMPERATIVE = {"adds", "fixes", "updates", "removes", "changes", "refactors", "improves", "moves",
                  "renames", "deletes", "implements", "introduces"}
# imperative verbs that end in -ed or -ing
IMPERATIVE_OK = {"embed", "feed", "speed", "shed", "shred", "seed", "need", "exceed", "proceed", "succeed",
                 "bring", "string", "ring", "sing", "swing", "spring", "cling", "fling", "wring", "bed",
                 "breed", "bleed", "heed", "wed", "sled", "sting", "sling", "ping"}
SCRATCH = re.compile(r"(?:^|/)scratch/")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
DIFF_FILE = re.compile(r"^\+\+\+ b/(.*)$")
DEBUG = re.compile(r"^\s*(?:print\(|console\.log\(|breakpoint\(\)|pdb\.set_trace\(\)|fmt\.Println\()")
DEBUG_EXT = (".py", ".js", ".ts", ".go")
PR_LABELS = ("What", "Why", "Tests", "Deviations")
PR_LABEL = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*(%s):?\*\*:?|#{1,6}\s+(%s)\b|(%s):)" % (
    ("|".join(PR_LABELS),) * 3), re.I)
ATTRIBUTION = re.compile(r"Generated with|Co-Authored-By|\U0001F916", re.I)


@dataclass
class Finding:
    file: str
    line: int
    col: int
    rule: str
    severity: str
    message: str
    excerpt: str


def _excerpt(s):
    s = (s or "").strip()
    return s if len(s) <= 80 else s[:77] + "..."


class Emitter:
    def __init__(self, disabled):
        self.disabled = set(disabled)
        self.findings = []

    def __call__(self, rule_id, file, line, excerpt="", extra="", col=1):
        if rule_id in self.disabled:
            return
        sev, _, _, msg = RULES[rule_id]
        if extra:
            msg = msg + " " + extra
        self.findings.append(Finding(file, line, col, rule_id, sev, msg, _excerpt(excerpt)))

    def sorted(self):
        return sorted(self.findings, key=lambda f: (f.file, f.line, f.col, f.rule))


# --------------------------------------------------------------------------- commit message

def lint_message(text, filename="<message>", disabled=()):
    emit = Emitter(disabled)
    lines = text.splitlines()
    numbered = [(i + 1, l) for i, l in enumerate(lines) if not l.startswith("#")]
    while numbered and not numbered[0][1].strip():
        numbered.pop(0)
    if not numbered:
        emit("subject-empty", filename, 1, "")
        return emit.sorted()
    subj_no, subject = numbered[0]
    subject = subject.rstrip()
    if len(subject) > SUBJECT_MAX:
        emit("subject-length", filename, subj_no, subject, "%d characters." % len(subject), col=SUBJECT_MAX + 1)
    if subject.endswith("."):
        emit("subject-period", filename, subj_no, subject, col=len(subject))
    first = re.sub(r"^[^A-Za-z]+", "", subject.split()[0] if subject.split() else "")
    word = first.lower()
    if word and (word in NON_IMPERATIVE or (word not in IMPERATIVE_OK and len(word) > 3
                                             and (word.endswith("ed") or word.endswith("ing")))):
        emit("subject-imperative", filename, subj_no, subject, "First word: '%s'." % first)
    body_lines = []
    for n, raw in numbered[1:]:
        if not raw.strip():
            continue
        if TRAILER.match(raw) or GENERATED.search(raw):
            emit("trailer", filename, n, raw)
        else:
            body_lines.append((n, raw))
    if body_lines:
        n, raw = body_lines[0]
        emit("body", filename, n, raw, "%d body line(s)." % len(body_lines))
    return emit.sorted()


def _run(cmd, cwd=None):
    """Run CMD. Return CompletedProcess, or None when the executable is missing."""
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    except (OSError, FileNotFoundError):
        return None


class ToolError(Exception):
    pass


def _git(args, cwd=None):
    r = _run(["git"] + args, cwd)
    if r is None:
        raise ToolError("git is not available")
    if r.returncode != 0:
        raise ToolError("git %s failed: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def lint_commits(range_spec, disabled=(), cwd=None):
    out = _git(["log", "--format=%H%n%B%x00", range_spec], cwd)
    findings = []
    for chunk in out.split("\x00"):
        chunk = chunk.lstrip("\n")
        if not chunk.strip():
            continue
        sha, _, body = chunk.partition("\n")
        findings += lint_message(body, sha[:7], disabled)
    return findings


# --------------------------------------------------------------------------- staged state

def lint_staged(disabled=(), cwd=None):
    emit = Emitter(disabled)
    where = "<staged>"
    _git(["rev-parse", "--is-inside-work-tree"], cwd)
    r = _run(["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd)
    branch = r.stdout.strip() if r is not None and r.returncode == 0 else ""
    if branch in ("main", "master"):
        emit("on-main", where, 1, branch)
    files = [p for p in _git(["diff", "--staged", "--name-only", "-z"], cwd).split("\0") if p]
    if not files:
        emit("nothing-staged", where, 1, "")
    if len(files) > MAX_FILES:
        emit("too-many-files", where, 1, "", "%d files." % len(files))
    for path in files:
        if SCRATCH.search(path):
            emit("scratch-file", path, 1, path)
        r = _run(["git", "cat-file", "-s", ":" + path], cwd)
        if r is not None and r.returncode == 0 and r.stdout.strip().isdigit():
            size = int(r.stdout.strip())
            if size > LARGE_FILE:
                emit("large-file", path, 1, path, "%d bytes." % size)
    home = os.path.expanduser("~")
    host_paths = ["/Users/", "/home/"] + ([home] if home and home != "~" else [])
    current, new_line = None, 0
    for raw in _git(["diff", "--staged", "-U0"], cwd).splitlines():
        m = DIFF_FILE.match(raw)
        if m:
            current = m.group(1)
            continue
        m = HUNK.match(raw)
        if m:
            new_line = int(m.group(1))
            continue
        if raw.startswith("---") or not raw.startswith("+") or current is None:
            continue
        added = raw[1:]
        if any(h in added for h in host_paths):
            emit("host-path", current, new_line, added)
        if current.endswith(DEBUG_EXT) and DEBUG.match(added):
            emit("debug-output", current, new_line, added)
        new_line += 1
    return emit.sorted()


# --------------------------------------------------------------------------- pull request

def lint_pr_body(text, filename="<pr>", disabled=()):
    emit = Emitter(disabled)
    lines = text.splitlines()
    labels = []  # (line_no, label, rest_of_line)
    for i, raw in enumerate(lines):
        m = PR_LABEL.match(raw)
        if m:
            label = next(g for g in m.groups() if g)
            labels.append((i + 1, label.capitalize(), raw[m.end():]))
        if ATTRIBUTION.search(raw):
            emit("pr-attribution", filename, i + 1, raw)
    found = {label for _, label, _ in labels}
    missing = [l for l in PR_LABELS if l not in found]
    if missing:
        emit("pr-sections", filename, 1, lines[0] if lines else "", "Missing: %s." % ", ".join(missing))
    for idx, (line_no, label, rest) in enumerate(labels):
        end = labels[idx + 1][0] - 1 if idx + 1 < len(labels) else len(lines)
        body = [rest] + lines[line_no:end]
        if not any(l.strip() for l in body):
            emit("pr-section-empty", filename, line_no, lines[line_no - 1], "Section: %s." % label)
    return emit.sorted()


def _gh_pr_body(number):
    r = _run(["gh", "pr", "view", str(number), "--json", "body,title", "-q", ".body"])
    if r is None:
        raise ToolError("gh is not available")
    if r.returncode != 0:
        raise ToolError("gh pr view %s failed: %s" % (number, r.stderr.strip()))
    return r.stdout


# --------------------------------------------------------------------------- output

def report(findings, as_json, baseline, mode=None):
    hard = sum(1 for f in findings if f.severity == HARD)
    adv = len(findings) - hard
    if as_json:
        print(json.dumps({"mode": mode, "hard": hard, "advisory": adv, "baseline": baseline,
                          "findings": [asdict(f) for f in findings]}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print('%s:%d:%d: %s %s: %s  "%s"' % (f.file, f.line, f.col, f.severity, f.rule,
                                                f.message, f.excerpt))
        print("mode=%s: %d hard, %d advisory (baseline %d)" % (mode, hard, adv, baseline))
    return 1 if hard > baseline else 0


def list_rules():
    print("%-20s %-9s %-8s %-46s %s" % ("rule", "severity", "mode", "source", "message"))
    for rid, (sev, mode, src, msg) in RULES.items():
        print("%-20s %-9s %-8s %-46s %s" % (rid, sev, mode, src, msg))


# --------------------------------------------------------------------------- selftest

def _staged_repo(branch, paths):
    """Make a git repo on BRANCH with PATHS staged. Return its directory."""
    tmp = tempfile.mkdtemp(prefix="commit-lint-")

    def g(*args):
        subprocess.run(["git"] + list(args), cwd=tmp, capture_output=True, text=True, check=True)
    g("init", "-q")
    g("symbolic-ref", "HEAD", "refs/heads/" + branch)
    g("config", "user.email", "selftest@example.com")
    g("config", "user.name", "selftest")
    for path, content in paths.items():
        full = os.path.join(tmp, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
    g("add", "--", *paths)
    return tmp


def selftest():
    msg_cases = [
        # (text, rules that must appear, rules that must not appear)
        ("Add the ADR linter", set(), set(RULES)),
        ("Add the ADR linter\n", set(), set(RULES)),
        ("Add the ADR linter\n# Please enter the commit message\n# On branch topic\n", set(), set(RULES)),
        ("", {"subject-empty"}, set()),
        ("\n\n# only comments\n", {"subject-empty"}, set()),
        ("A" * 73, {"subject-length"}, set()),
        ("A" * 72, set(), {"subject-length"}),
        ("Add the linter\n\nThis explains why.\n", {"body"}, {"trailer"}),
        ("Add the linter\n\nCo-Authored-By: Someone <x@example.com>\n", {"trailer"}, {"body"}),
        ("Add the linter\n\nSigned-off-by: Someone <x@example.com>\n", {"trailer"}, {"body"}),
        ("Add the linter\n\nGenerated with Claude Code\n", {"trailer"}, {"body"}),
        ("Add the linter\n\nSome body.\n\nCo-Authored-By: X <x@y>\n", {"body", "trailer"}, set()),
        ("Add the linter.", {"subject-period"}, set()),
        ("Added the linter", {"subject-imperative"}, set()),
        ("Adding the linter", {"subject-imperative"}, set()),
        ("Fixes the linter", {"subject-imperative"}, set()),
        ("Embed the version string", set(), {"subject-imperative"}),
        ("Bring the docs up to date", set(), {"subject-imperative"}),
        ("Red is the new default", set(), {"subject-imperative"}),
    ]
    pr_cases = [
        ("**What:** the change.\n**Why:** the reason.\n**Tests:** 3 passed.\n**Deviations:** none.\n",
         set(), set(RULES)),
        ("## What\n\nthe change\n\n## Why\n\nreason\n\n## Tests\n\n3 passed\n\n## Deviations\n\nnone\n",
         set(), set(RULES)),
        ("- **What:** the change.\n- **Why:** the reason.\n- **Tests:** 3 passed.\n- **Deviations:** none.\n",
         set(), set(RULES)),
        ("What: the change.\nWhy: reason.\nTests: 3 passed.\n", {"pr-sections"}, set()),
        ("**What:** x\n**Why:** y\n**Tests:** z\n**Deviations:** none\n\nGenerated with Claude Code\n",
         {"pr-attribution"}, set()),
        ("**What:** x\n**Why:** y\n**Tests:** z\n**Deviations:** none\n\n\U0001F916 made this\n",
         {"pr-attribution"}, set()),
        ("**What:** x\n**Why:** y\n**Tests:** z\n**Deviations:** none\nCo-Authored-By: A <a@b>\n",
         {"pr-attribution"}, set()),
        ("## What\n\n## Why\n\nreason\n\n## Tests\n\n3 passed\n\n## Deviations\n\nnone\n",
         {"pr-section-empty"}, {"pr-sections"}),
        ("**What:**\n**Why:** y\n**Tests:** z\n**Deviations:** none\n", {"pr-section-empty"}, set()),
    ]
    failed = total = 0
    for text, must, must_not in msg_cases:
        total += 1
        got = {f.rule for f in lint_message(text)}
        miss, extra = must - got, must_not & got
        if miss or extra:
            failed += 1
            print("FAIL [message] %r\n  missing=%s unexpected=%s got=%s" % (text, sorted(miss), sorted(extra),
                                                                           sorted(got)))
    for text, must, must_not in pr_cases:
        total += 1
        got = {f.rule for f in lint_pr_body(text)}
        miss, extra = must - got, must_not & got
        if miss or extra:
            failed += 1
            print("FAIL [pr] %r\n  missing=%s unexpected=%s got=%s" % (text, sorted(miss), sorted(extra),
                                                                      sorted(got)))
    if shutil.which("git"):
        staged_cases = [
            ("topic", {"src/a.py": "x = 1\n", "docs/b.md": "# B\n"}, set(),
             {"on-main", "scratch-file", "too-many-files", "large-file", "host-path", "nothing-staged",
              "debug-output"}),
            ("main", {"scratch/notes.md": "temp\n", "src/a.py": "x = 1\n"}, {"on-main", "scratch-file"}, set()),
            ("topic", {"src/a.py": "def f():\n    print(x)\n    return x\n",
                       "notes.md": "see /Users/someone/file\n"}, {"debug-output", "host-path"}, set()),
            ("topic", {"blob.bin": "0" * (LARGE_FILE + 1)}, {"large-file"}, set()),
            ("topic", {"f%d.txt" % i: "x\n" for i in range(11)}, {"too-many-files"}, set()),
            ("topic", {}, {"nothing-staged"}, set()),
        ]
        for branch, paths, must, must_not in staged_cases:
            total += 1
            tmp = _staged_repo(branch, paths) if paths else None
            if tmp is None:
                tmp = tempfile.mkdtemp(prefix="commit-lint-")
                subprocess.run(["git", "init", "-q"], cwd=tmp, check=True, capture_output=True)
                subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/" + branch], cwd=tmp, check=True)
            try:
                got = {f.rule for f in lint_staged(cwd=tmp)}
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            miss, extra = must - got, must_not & got
            if miss or extra:
                failed += 1
                print("FAIL [staged %s %s]\n  missing=%s unexpected=%s got=%s" % (
                    branch, sorted(paths), sorted(miss), sorted(extra), sorted(got)))
    else:
        print("selftest: git not found, staged cases skipped")
    print("selftest: %d/%d passed" % (total - failed, total))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic checks for commit messages, staged state, "
                                             "and PR bodies.")
    ap.add_argument("msgfile", nargs="?", help="commit message file (as a commit-msg hook)")
    ap.add_argument("--message", help="commit message text")
    ap.add_argument("--commits", metavar="RANGE", help="check each commit in a git range")
    ap.add_argument("--staged", action="store_true", help="check the staged state")
    ap.add_argument("--pr-body", metavar="FILE", help="check a PR description file")
    ap.add_argument("--pr", metavar="NUMBER", help="check the body of a PR via gh")
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
    chosen = [n for n, v in (("msgfile", args.msgfile), ("--message", args.message is not None),
                             ("--commits", args.commits), ("--staged", args.staged),
                             ("--pr-body", args.pr_body), ("--pr", args.pr)) if v]
    if len(chosen) != 1:
        ap.error("give exactly one of MSGFILE, --message, --commits, --staged, --pr-body, --pr")
    try:
        if args.msgfile:
            with open(args.msgfile, encoding="utf-8") as fh:
                findings, mode = lint_message(fh.read(), args.msgfile, disabled), MESSAGE
        elif args.message is not None:
            findings, mode = lint_message(args.message, "<message>", disabled), MESSAGE
        elif args.commits:
            findings, mode = lint_commits(args.commits, disabled), MESSAGE
        elif args.staged:
            findings, mode = lint_staged(disabled), STAGED
        elif args.pr_body:
            with open(args.pr_body, encoding="utf-8") as fh:
                findings, mode = lint_pr_body(fh.read(), args.pr_body, disabled), PR
        else:
            findings, mode = lint_pr_body(_gh_pr_body(args.pr), "PR #%s" % args.pr, disabled), PR
    except ToolError as e:
        print("commit-lint: %s" % e, file=sys.stderr)
        return 2
    return report(findings, args.json, args.baseline, mode)


if __name__ == "__main__":
    sys.exit(main())
