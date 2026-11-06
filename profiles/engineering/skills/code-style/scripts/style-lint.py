#!/usr/bin/env python3
"""style-lint: deterministic surface checks for the code-style skill.

Standard library only. The linter checks the measurable rules in SKILL.md.
These are sizes, mixins, defensive getattr and hasattr, frozen dataclasses,
positional calls, whole-Namespace parameters, and inline blocks in __init__.
It cannot check pseudocode readability, dead code or protected names. A clean
run means only that the configured patterns did not match.

Usage:
    style-lint.py [--json] [--baseline N] [--disable rule1,rule2] PATH ...
    style-lint.py --list-rules
    style-lint.py --selftest

Exit status: 1 when hard findings exceed --baseline, 0 otherwise.
Advisory findings never change the exit status.

Suppress a line with a trailing comment `# style-lint: ignore`.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import io
import json
import os
import re
import sys
import tempfile
import tokenize
from dataclasses import asdict, dataclass

HARD, ADV = "hard", "advisory"
DATA = "SKILL.md: Data and state"
SIZE = "SKILL.md: Size and structure"
IFACE = "SKILL.md: Interfaces"
LARGE = "SKILL.md: Large classes, __init__"
ATTR = "SKILL.md: Attribute access"

# rule id -> (severity, source, message)
RULES = {
    "file-length": (HARD, SIZE,
                    "File is over 1000 lines. Split the module along the boundaries of its "
                    "responsibilities."),
    "function-length": (HARD, SIZE,
                        "Function is over 100 lines. Split it into helpers with clear names."),
    "package-size": (HARD, SIZE,
                     "Package holds more than 10 .py files. Split the package."),
    "mutable-dataclass": (ADV, DATA,
                          "Dataclass is not frozen. Define a data container as @dataclass(frozen=True). "
                          "Make a container mutable only when code must change it in place."),
    "mixin": (HARD, SIZE,
              "Mixin class. Use composition: hold a collaborator and call it, or call a plain "
              "function."),
    "defensive-getattr": (HARD, ATTR,
                          "Defensive attribute read with a fixed name. Do one of these instead: "
                          "(1) 'Narrow the type with isinstance', then read the attribute directly. "
                          "(2) 'Always set the attribute', to None if there is no value, then test "
                          "'is not None'. (3) 'Declare an optional operation in the protocol or the "
                          "base class', with a default that reports no support."),
    "positional-args": (ADV, IFACE,
                        "Call passes 3 or more arguments by position. The skill says to pass two or "
                        "more by keyword. The linter uses 3 as the threshold to limit noise."),
    "whole-namespace-param": (ADV, IFACE,
                              "Parameter takes a whole argparse.Namespace. Pass the specific values "
                              "by keyword."),
    "init-inline-block": (ADV, LARGE,
                          "Inline block in the __init__ of a large class. Write __init__ as a "
                          "sequence of self._init_<thing>(...) calls and one-line glue such as "
                          "self._root = root."),
}

MAX_FILE_LINES = 1000
MAX_FUNCTION_LINES = 100
MAX_PACKAGE_FILES = 10
LARGE_CLASS_LINES = 150
POSITIONAL_LIMIT = 3
BUILTINS = frozenset(dir(builtins))
IGNORE = re.compile(r"#\s*style-lint:\s*ignore\s*$")
INIT_PREFIXES = ("_init_", "_maybe_init_")
GLUE_VALUES = (ast.Name, ast.Attribute, ast.Constant)


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    col: int
    rule: str
    severity: str
    message: str
    excerpt: str


# --------------------------------------------------------------------------- ast helpers


def _dotted_tail(node):
    """The last name of a Name or Attribute node, or '' for any other node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_str(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_self_attr(node):
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"


def _parameters(args):
    params = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
    params += [a for a in (args.vararg, args.kwarg) if a is not None]
    return params


def _is_namespace(annotation):
    """True when the annotation names Namespace, also inside Optional[...] or a string."""
    for sub in ast.walk(annotation):
        if _dotted_tail(sub) == "Namespace":
            return True
        if _is_str(sub) and sub.value.split(".")[-1] == "Namespace":
            return True
    return False


def _dataclass_state(decorator):
    """(is_dataclass, is_frozen) for one decorator node."""
    call = decorator if isinstance(decorator, ast.Call) else None
    if _dotted_tail(call.func if call else decorator) != "dataclass":
        return False, False
    if call is None:
        return True, False
    frozen = any(kw.arg == "frozen" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                 for kw in call.keywords)
    return True, frozen


def _is_init_call(value):
    """True for self._init_<thing>(...) or self._maybe_init_<thing>(...)."""
    return (isinstance(value, ast.Call) and _is_self_attr(value.func)
            and value.func.attr.startswith(INIT_PREFIXES))


def _is_super_init(value):
    return (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
            and value.func.attr == "__init__" and isinstance(value.func.value, ast.Call)
            and _dotted_tail(value.func.value.func) == "super")


def _is_init_glue(stmt, first):
    """True when STMT is allowed in the __init__ of a large class."""
    if isinstance(stmt, ast.Expr):
        value = stmt.value
        if first and _is_str(value):
            return True
        return _is_init_call(value) or _is_super_init(value)
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        target, value = stmt.targets[0], stmt.value
    elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        target, value = stmt.target, stmt.value
    else:
        return False
    return _is_self_attr(target) and (isinstance(value, GLUE_VALUES) or _is_init_call(value))


# --------------------------------------------------------------------------- checks


def _check_function(node, emit):
    length = node.end_lineno - node.lineno + 1
    if length > MAX_FUNCTION_LINES:
        emit("function-length", node.lineno, col=node.col_offset + 1, extra="%d lines." % length)
    for arg in _parameters(node.args):
        if arg.annotation is not None and _is_namespace(arg.annotation):
            emit("whole-namespace-param", arg.lineno, col=arg.col_offset + 1)


def _check_init(cls, emit):
    for item in cls.body:
        if not (isinstance(item, ast.FunctionDef) and item.name == "__init__"):
            continue
        for index, stmt in enumerate(item.body):
            if not _is_init_glue(stmt, first=index == 0):
                emit("init-inline-block", stmt.lineno, col=stmt.col_offset + 1)


def _check_class(node, emit):
    if node.name.endswith("Mixin") or any(_dotted_tail(b).endswith("Mixin") for b in node.bases):
        emit("mixin", node.lineno, col=node.col_offset + 1)
    for decorator in node.decorator_list:
        is_dataclass, frozen = _dataclass_state(decorator)
        if is_dataclass and not frozen:
            emit("mutable-dataclass", decorator.lineno, col=decorator.col_offset + 1)
    if node.end_lineno - node.lineno + 1 > LARGE_CLASS_LINES:
        _check_init(node, emit)


def _check_call(node, emit):
    name = node.func.id if isinstance(node.func, ast.Name) else ""
    args = node.args
    literal = len(args) >= 2 and _is_str(args[1])
    if literal and ((name == "getattr" and len(args) >= 3) or (name == "hasattr" and len(args) == 2)):
        emit("defensive-getattr", node.lineno, col=node.col_offset + 1)
    splat = any(isinstance(a, ast.Starred) for a in args)
    if len(args) >= POSITIONAL_LIMIT and not splat and name not in BUILTINS:
        emit("positional-args", node.lineno, col=node.col_offset + 1,
             extra="%d positional arguments." % len(args))


def _ignored_lines(text):
    ignored = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT and IGNORE.match(tok.string):
                ignored.add(tok.start[0])
    except (tokenize.TokenError, SyntaxError):
        pass
    return ignored


def lint(text, filename="<stdin>", disabled=()):
    """Findings for one Python source text. A file with a syntax error yields none."""
    try:
        tree = ast.parse(text, filename=filename)
    except SyntaxError as exc:
        print("%s:%s: syntax error, file skipped: %s" % (filename, exc.lineno, exc.msg), file=sys.stderr)
        return []
    lines = text.splitlines()
    ignored = _ignored_lines(text)
    findings = []

    def emit(rule, lineno, col=1, extra=""):
        if rule in disabled or lineno in ignored:
            return
        excerpt = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
        if len(excerpt) > 80:
            excerpt = excerpt[:77] + "..."
        message = " ".join(x for x in (RULES[rule][2], extra) if x)
        findings.append(Finding(file=filename, line=lineno, col=col, rule=rule,
                                severity=RULES[rule][0], message=message, excerpt=excerpt))

    if len(lines) > MAX_FILE_LINES:
        emit("file-length", 1, extra="%d lines." % len(lines))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _check_function(node, emit)
        elif isinstance(node, ast.ClassDef):
            _check_class(node, emit)
        elif isinstance(node, ast.Call):
            _check_call(node, emit)
    findings.sort(key=lambda f: (f.file, f.line, f.col, f.rule))
    return findings


# --------------------------------------------------------------------------- paths


def _lint_file(path, disabled):
    with open(path, encoding="utf-8") as fh:
        return lint(fh.read(), filename=path, disabled=disabled)


def _package_finding(dirpath, count, disabled):
    init = os.path.join(dirpath, "__init__.py")
    if "package-size" in disabled:
        return []
    with open(init, encoding="utf-8") as fh:
        if IGNORE.search(fh.readline()):
            return []
    message = "%s Found %d, __init__.py included." % (RULES["package-size"][2], count)
    return [Finding(file=init, line=1, col=1, rule="package-size", severity=HARD,
                    message=message, excerpt=dirpath)]


def _lint_directory(root, disabled):
    findings = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d != "__pycache__")
        py_files = sorted(f for f in filenames if f.endswith(".py"))
        if "__init__.py" in py_files and len(py_files) > MAX_PACKAGE_FILES:
            findings += _package_finding(dirpath=dirpath, count=len(py_files), disabled=disabled)
        for name in py_files:
            findings += _lint_file(os.path.join(dirpath, name), disabled)
    return findings


def lint_paths(paths, disabled=()):
    """Findings for files and directories. A directory is walked for .py files and packages."""
    findings = []
    for path in paths:
        if os.path.isdir(path):
            findings += _lint_directory(path, disabled)
        else:
            findings += _lint_file(path, disabled)
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
    print("%-24s %-9s %s" % ("rule", "severity", "source"))
    for rid, (severity, source, _) in RULES.items():
        print("%-24s %-9s %s" % (rid, severity, source))


# --------------------------------------------------------------------------- selftest

CLEAN_SAMPLE = '''\
"""Clean sample."""
from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    root: str
    timeout_s: int


class Runner:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._store = self._init_store(root=config.root)

    def _init_store(self, *, root: str) -> dict:
        return {"root": root}

    def run(self, *, name: str, retries: int) -> int:
        if isinstance(self._config, Config):
            return self._config.timeout_s + retries + len(name)
        return 0


def build(argv: list[str]) -> Config:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    print(args.root, "ready", 3)
    return Config(root=args.root, timeout_s=60)
'''

_PAD_METHODS = "".join("    def m%d(self):\n        return %d\n\n" % (i, i) for i in range(60))
_INIT_GLUE = ('class Big:\n    def __init__(self, root, config):\n        """Doc."""\n'
              "        super().__init__()\n        self._root = root\n"
              "        self._store = self._init_store(root=root)\n        self._maybe_init_cache()\n")
INIT_BAD = _INIT_GLUE + "        self._timeout_s = config.timeout_s * 2\n\n" + _PAD_METHODS
INIT_OK = _INIT_GLUE + "\n" + _PAD_METHODS
INIT_SMALL = "class Small:\n    def __init__(self, config):\n        self._timeout_s = config.timeout_s * 2\n"

# (source text, rules that must appear, rules that must not appear)
SELFTEST_CASES = [
    (CLEAN_SAMPLE, set(), set(RULES)),
    ("x = 1\n" * 1001, {"file-length"}, set()),
    ("x = 1\n" * 1000, set(), {"file-length"}),
    ("def f():\n" + "    x = 1\n" * 100, {"function-length"}, set()),
    ("def f():\n" + "    x = 1\n" * 99, set(), {"function-length"}),
    ("async def f():\n" + "    x = 1\n" * 100, {"function-length"}, set()),
    ("from dataclasses import dataclass\n@dataclass\nclass A:\n    x: int\n", {"mutable-dataclass"}, set()),
    ("from dataclasses import dataclass\n@dataclass(frozen=False)\nclass A:\n    x: int\n",
     {"mutable-dataclass"}, set()),
    ("import dataclasses\n@dataclasses.dataclass\nclass A:\n    x: int\n", {"mutable-dataclass"}, set()),
    ("from dataclasses import dataclass\n@dataclass(frozen=True)\nclass A:\n    x: int\n",
     set(), {"mutable-dataclass"}),
    ("import dataclasses\n@dataclasses.dataclass(frozen=True, slots=True)\nclass A:\n    x: int\n",
     set(), {"mutable-dataclass"}),
    ("class LogMixin:\n    pass\n", {"mixin"}, set()),
    ("class Worker(Base, LogMixin):\n    pass\n", {"mixin"}, set()),
    ("class Worker(util.LogMixin):\n    pass\n", {"mixin"}, set()),
    ("class Store(Base):\n    pass\n", set(), {"mixin"}),
    ('x = getattr(cfg, "timeout_s", 60)\n', {"defensive-getattr"}, set()),
    ('if hasattr(cfg, "timeout_s"):\n    pass\n', {"defensive-getattr"}, set()),
    ('x = getattr(cfg, "timeout_s")\n', set(), {"defensive-getattr"}),
    ("x = getattr(cfg, name, 60)\n", set(), {"defensive-getattr"}),
    ("x = hasattr(cfg, name)\n", set(), {"defensive-getattr"}),
    ("x = cfg.timeout_s\n", set(), {"defensive-getattr"}),
    ("run(a, b, c)\n", {"positional-args"}, set()),
    ("store.claim(a, b, c)\n", {"positional-args"}, set()),
    ("run(a, b)\n", set(), {"positional-args"}),
    ("run(a=1, b=2, c=3)\n", set(), {"positional-args"}),
    ("run(a, b, *rest)\n", set(), {"positional-args"}),
    ("print(a, b, c)\nisinstance(a, b, c)\n", set(), {"positional-args"}),
    ("import argparse\ndef f(args: argparse.Namespace):\n    pass\n", {"whole-namespace-param"}, set()),
    ("def f(*, args: Namespace):\n    pass\n", {"whole-namespace-param"}, set()),
    ("def f(args: 'argparse.Namespace'):\n    pass\n", {"whole-namespace-param"}, set()),
    ("def f(*, root: str, args):\n    pass\n", set(), {"whole-namespace-param"}),
    (INIT_BAD, {"init-inline-block"}, set()),
    (INIT_OK, set(), {"init-inline-block"}),
    (INIT_SMALL, set(), {"init-inline-block"}),
    ("class LogMixin:  # style-lint: ignore\n    pass\n", set(), {"mixin"}),
]


def _package_dirs(tmp):
    """Two packages under TMP: 'big' with 11 .py files and 'small' with 10."""
    made = []
    for name, count in (("big", 11), ("small", 10)):
        pkg = os.path.join(tmp, name)
        os.mkdir(pkg)
        for i in range(count):
            fname = "__init__.py" if i == 0 else "mod%d.py" % i
            with open(os.path.join(pkg, fname), "w", encoding="utf-8") as fh:
                fh.write("x = 1\n")
        made.append(pkg)
    return made


def _rules_for(sample):
    if os.path.isdir(sample):
        return {f.rule for f in lint_paths([sample])}
    return {f.rule for f in lint(sample)}


def selftest():
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        big, small = _package_dirs(tmp)
        cases = SELFTEST_CASES + [(big, {"package-size"}, set()), (small, set(), {"package-size"})]
        for sample, must, must_not in cases:
            got = _rules_for(sample)
            miss, extra = must - got, must_not & got
            if miss or extra:
                failed += 1
                label = sample if os.path.isdir(sample) else sample[:60]
                print("FAIL %r\n  missing=%s unexpected=%s got=%s" % (label, sorted(miss), sorted(extra),
                                                                     sorted(got)))
    print("selftest: %d/%d passed" % (len(cases) - failed, len(cases)))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic checks for the code-style skill.")
    ap.add_argument("paths", nargs="*", help="files or directories (directories are walked for .py)")
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
