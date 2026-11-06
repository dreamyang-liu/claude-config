#!/usr/bin/env python3
"""test-lint: deterministic surface checks for pytest files against the testing skill.

Standard library only. Each rule traces to a sentence in SKILL.md (the section is
named in the RULES table). The linter finds patterns that the skill names
explicitly: control flow in a test body, sleep, unittest.mock, a test with no
assertion, a skip with no reason, a slow test with no skipif, private access,
host paths, partial assertions, and short test names. It cannot check whether a
case passes the deletion test, guards a real failure, checks one behavior, or
stays unchanged under a refactoring. A clean run means only that the configured
patterns did not match.

Usage:
    test-lint.py [--json] [--baseline N] [--disable rule1,rule2] PATH [PATH ...]
    test-lint.py --list-rules
    test-lint.py --selftest

A PATH is a file or a directory. In a directory the linter recurses and takes the
files named test_*.py, *_test.py and conftest.py.

Exit status: 1 when hard findings exceed --baseline, 0 otherwise.
Advisory findings never change the exit status. A file that does not parse is
reported on stderr and gives exit status 2.

The linter never flags hedges or modality words.

Suppress a line with the trailing comment:  # test-lint: ignore
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
import tokenize
from dataclasses import asdict, dataclass

HARD, ADV = "hard", "advisory"

WHAT = "SKILL.md: What to test"
ADMIT = "SKILL.md: Admitting a test"
SIZES = "SKILL.md: Test sizes"
DOUBLES = "SKILL.md: Test doubles"
WRITING = "SKILL.md: Writing a test"
REVIEW = "SKILL.md: Reviewing a test"

# rule id -> (severity, source, message)
RULES = {
    "test-name": (ADV, WRITING + " (name the test after the behavior)",
                  "Name the test after the behavior, as a sentence, e.g. "
                  "test_the_adapter_refuses_any_slot_but_mini."),
    "control-flow": (HARD, WRITING + " (put no logic in the test); " + REVIEW,
                     "No logic in a test. Use parametrize for cases, and "
                     "pytest.raises(..., match=...) for errors."),
    "sleep": (HARD, WRITING + " (make the test deterministic); " + SIZES + "; " + REVIEW,
              "Do not use sleep to wait for an event. Wait for the event, with a deadline. "
              "Only await asyncio.sleep(0) is allowed: it yields and does not wait."),
    "mock": (HARD, DOUBLES,
             "This skill uses fakes and spies, not mocks. Use monkeypatch at the point "
             "where the code receives the dependency."),
    "monkeypatch-private": (ADV, DOUBLES,
                            "Do not replace a private function of the unit. Replace the "
                            "dependency at the point where the code receives it."),
    "no-assert": (HARD, WRITING + " (assert exact values); " + ADMIT,
                  "The test checks nothing. Add an assert, pytest.raises, pytest.warns, "
                  "or a call to an assert_... helper."),
    "raises-no-match": (ADV, WRITING + " (put no logic in the test)",
                        "pytest.raises without match=. Pin the error message with match=."),
    "skip-no-reason": (HARD, SIZES + " (each skip must say what is missing)",
                       "Skip without a reason. Say what is missing and how to get it."),
    "slow-no-skip": (ADV, SIZES + " (Large)",
                     "A large test must skip, not fail, when its infrastructure is absent. "
                     "Add a skipif with a reason."),
    "private-access": (ADV, WHAT + " (test through the public API)",
                       "Test through the public API. Do not call private helpers, and do "
                       "not read private fields."),
    "host-path": (HARD, WRITING + " (name no host paths)",
                  "Host path. Use placeholders under /path/to/."),
    "partial-assert": (ADV, WRITING + " (assert exact values)",
                       "Assert exact values. Compare with the full expected value, not with "
                       "a part of it."),
}

IGNORE = re.compile(r"#\s*test-lint:\s*ignore\b")
TEST_FILE = re.compile(r"^(?:test_.*\.py|.*_test\.py|conftest\.py)$")
SKIP_DIRS = {"__pycache__", "node_modules"}
# "/path/to/home/x" is a placeholder; "/home/x" and "/Users/x" are host paths
HOST_PATH = re.compile(r"(?<![\w/.-])/(?:Users|home)/")
HOME = os.path.expanduser("~")
if HOME in ("~", "/", ""):
    HOME = None

SKIP_MARKS = ("pytest.mark.skip", "pytest.mark.skipif")
SLOW_MARK = "pytest.mark.slow"
SKIPIF_MARK = "pytest.mark.skipif"
RAISES = ("pytest.raises", "pytest.warns")
MOCK_BARE = ("patch", "Mock", "MagicMock")
MOCK_ATTRS = ("patch", "Mock", "MagicMock", "AsyncMock", "NonCallableMock", "PropertyMock",
              "create_autospec", "seal")
PRIVATE_RECEIVERS = ("monkeypatch", "request", "pytest")
SELF_NAMES = ("self", "cls")

CONTROL = (ast.For, ast.AsyncFor, ast.While, ast.If, ast.Try)
if hasattr(ast, "TryStar"):
    CONTROL = CONTROL + (ast.TryStar,)
COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


@dataclass
class Finding:
    file: str
    line: int
    col: int
    rule: str
    severity: str
    message: str
    excerpt: str


# --------------------------------------------------------------------------- ast helpers


def _ignored_lines(text):
    """Line numbers that carry a '# test-lint: ignore' comment."""
    out = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT and IGNORE.search(tok.string):
                out.add(tok.start[0])
    except (tokenize.TokenError, SyntaxError):
        pass
    return out


def _imports(tree):
    """Map each imported local name to its dotted origin.

    'import time as t' gives t -> time; 'from pytest import raises' gives
    raises -> pytest.raises; 'import unittest.mock' gives unittest -> unittest.
    """
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    names[a.asname] = a.name
                else:
                    head = a.name.split(".")[0]
                    names[head] = head
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                names[a.asname or a.name] = node.module + "." + a.name
    return names


def _dotted(node, names):
    """Dotted name of a Name, Attribute or Call, with import aliases resolved, else None."""
    if isinstance(node, ast.Call):
        return _dotted(node.func, names)
    if isinstance(node, ast.Name):
        return names.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value, names)
        return None if base is None else base + "." + node.attr
    return None


def _root_name(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _keyword(call, name):
    return any(k.arg == name for k in call.keywords)


def _functions(tree):
    """Yield (function, enclosing classes) for module-level functions and methods."""
    def visit(body, classes):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield node, classes
            elif isinstance(node, ast.ClassDef):
                for item in visit(node.body, classes + [node]):
                    yield item
    for item in visit(tree.body, []):
        yield item


def _shallow(node):
    """Descendants of NODE that are not inside a nested function, lambda or class."""
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, SCOPES):
            for sub in _shallow(child):
                yield sub


def _body(func, deep):
    """Nodes of the body of FUNC; DEEP also enters nested functions and lambdas."""
    for stmt in func.body:
        if deep:
            for node in ast.walk(stmt):
                yield node
        else:
            yield stmt
            if not isinstance(stmt, SCOPES):
                for node in _shallow(stmt):
                    yield node


def _module_marks(tree, names):
    """(assign node, dotted marks) of a module-level 'pytestmark = ...', or (None, [])."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            value = node.value
            items = value.elts if isinstance(value, (ast.List, ast.Tuple)) else [value]
            return node, [_dotted(v, names) or "" for v in items]
    return None, []


# --------------------------------------------------------------------------- rule predicates


def _is_mock(dotted):
    if not dotted:
        return False
    parts = dotted.split(".")
    if dotted.startswith("unittest.mock."):
        return True
    if parts[0] in MOCK_BARE:
        return True
    return parts[0] == "mock" and len(parts) > 1 and parts[1] in MOCK_ATTRS


def _is_mock_import(node):
    if isinstance(node, ast.Import):
        return any(a.name == "unittest.mock" or a.name.startswith("unittest.mock.")
                   for a in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        if node.module.startswith("unittest.mock"):
            return True
        return node.module == "unittest" and any(a.name == "mock" for a in node.names)
    return False


def _is_sleep(call, names):
    dotted = _dotted(call.func, names)
    if dotted == "time.sleep":
        return True
    if dotted == "asyncio.sleep":
        if call.args and isinstance(call.args[0], ast.Constant):
            v = call.args[0].value
            if type(v) in (int, float) and v == 0:
                return False
        return True
    return False


def _skip_without_reason(call, dotted):
    if dotted == "pytest.mark.skip" or dotted == "pytest.skip":
        return not (call.args or _keyword(call, "reason"))
    if dotted == "pytest.mark.skipif":
        return not _keyword(call, "reason")
    if dotted == "pytest.importorskip":
        return not (len(call.args) >= 3 or _keyword(call, "reason"))
    return False


def _monkeypatch_private_name(call):
    """The attribute name that monkeypatch.setattr replaces, when it is private."""
    def text(node):
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    args = call.args
    name = None
    if len(args) >= 2 and text(args[1]) is not None:
        name = text(args[1])                       # setattr(obj, "name", value)
    elif args and text(args[0]) and "." in text(args[0]):
        name = text(args[0]).rsplit(".", 1)[-1]    # setattr("pkg.mod.name", value)
    else:
        for k in call.keywords:
            if k.arg == "name" and text(k.value) is not None:
                name = text(k.value)
    if name and name.startswith("_") and not name.startswith("__"):
        return name
    return None


def _is_private_read(node):
    if not isinstance(node.ctx, ast.Load):
        return False
    if not node.attr.startswith("_") or node.attr.startswith("__"):
        return False
    if isinstance(node.value, ast.Name) and node.value.id in SELF_NAMES:
        return False
    return _root_name(node.value) not in PRIVATE_RECEIVERS


def _is_partial(test):
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.In):
        right = test.comparators[0]
        if isinstance(right, ast.Constant) and isinstance(right.value, str):
            return True
        if isinstance(right, ast.JoinedStr):
            return True
        if isinstance(right, ast.Call):
            f = right.func
            if isinstance(f, ast.Attribute) and f.attr in ("read_text", "read"):
                return True
            if isinstance(f, ast.Name) and f.id == "str":
                return True
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute) \
            and test.func.attr in ("startswith", "endswith") \
            and isinstance(test.func.value, ast.Call):
        return True
    return False


def _is_host_path(value):
    if HOST_PATH.search(value):
        return True
    return bool(HOME) and HOME in value


def _is_assertion_call(call, names):
    if _dotted(call.func, names) in RAISES:
        return True
    f = call.func
    fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
    return fname.startswith("assert")


def _is_fixture(decorators):
    return any(d and (d == "fixture" or d.endswith(".fixture")) for d in decorators)


# --------------------------------------------------------------------------- lint


def lint(text, filename="<stdin>", disabled=()):
    """Return the findings for one file. Raises SyntaxError when TEXT does not parse."""
    tree = ast.parse(text, filename)
    lines = text.splitlines()
    ignored = _ignored_lines(text)
    names = _imports(tree)
    findings = []

    def emit(rule, node, extra=""):
        if rule in disabled:
            return
        line = getattr(node, "lineno", 1)
        if line in ignored:
            return
        col = getattr(node, "col_offset", 0) + 1
        excerpt = lines[line - 1].strip() if 0 < line <= len(lines) else ""
        if len(excerpt) > 80:
            excerpt = excerpt[:77] + "..."
        sev, _, msg = RULES[rule]
        findings.append(Finding(filename, line, col, rule, sev,
                                " ".join(x for x in (msg, extra) if x), excerpt))

    # ---- file-wide rules
    call_funcs = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for node in ast.walk(tree):
        if _is_mock_import(node):
            emit("mock", node)
        elif isinstance(node, ast.Call):
            dotted = _dotted(node.func, names)
            if _is_mock(dotted):
                emit("mock", node)
            if dotted == "monkeypatch.setattr":
                name = _monkeypatch_private_name(node)
                if name:
                    emit("monkeypatch-private", node, "Replaced: %s." % name)
            if dotted == "pytest.raises" and not _keyword(node, "match"):
                emit("raises-no-match", node)
            if _skip_without_reason(node, dotted):
                emit("skip-no-reason", node)
        elif isinstance(node, ast.Attribute) and id(node) not in call_funcs:
            if _dotted(node, names) in SKIP_MARKS:
                emit("skip-no-reason", node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _is_host_path(node.value):
                emit("host-path", node)

    mark_node, module_marks = _module_marks(tree, names)
    file_marks = [_dotted(d, names) or "" for f, classes in _functions(tree)
                  for d in f.decorator_list + [d for c in classes for d in c.decorator_list]]
    if SLOW_MARK in module_marks and not any(m.startswith(SKIPIF_MARK)
                                              for m in module_marks + file_marks):
        emit("slow-no-skip", mark_node)

    # ---- per-function rules
    for func, classes in _functions(tree):
        decos = [_dotted(d, names) or "" for d in func.decorator_list]
        class_marks = [_dotted(d, names) or "" for c in classes for d in c.decorator_list]
        is_test = func.name.startswith("test")
        is_fixture = _is_fixture(decos)

        if is_test or is_fixture:
            for node in _body(func, deep=True):
                if isinstance(node, ast.Call) and _is_sleep(node, names):
                    emit("sleep", node)
        if not is_test:
            continue

        words = [w for w in func.name[4:].split("_") if w]
        if len(words) < 3:
            emit("test-name", func)

        for node in _body(func, deep=False):
            if isinstance(node, CONTROL):
                emit("control-flow", node)
            elif isinstance(node, COMPREHENSIONS) and any(g.ifs for g in node.generators):
                emit("control-flow", node)

        has_assert = False
        for node in _body(func, deep=True):
            if isinstance(node, ast.Assert):
                has_assert = True
                if _is_partial(node.test):
                    emit("partial-assert", node)
            elif isinstance(node, ast.Call):
                if _is_assertion_call(node, names):
                    has_assert = True
            elif isinstance(node, ast.Attribute) and _is_private_read(node):
                emit("private-access", node, "Read: .%s." % node.attr)
        if not has_assert:
            emit("no-assert", func)

        if SLOW_MARK in decos + class_marks:
            marks = decos + class_marks + module_marks
            if not any(m.startswith(SKIPIF_MARK) for m in marks):
                emit("slow-no-skip", func)

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
    print("%-22s %-9s %s" % ("rule", "severity", "source"))
    for rid, (sev, src, _) in RULES.items():
        print("%-22s %-9s %s" % (rid, sev, src))


def collect(paths):
    """Files to lint: each file path as given; each directory recursed for test files."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS)
                for f in sorted(files):
                    if TEST_FILE.match(f):
                        out.append(os.path.join(root, f))
        else:
            out.append(p)
    return out


# --------------------------------------------------------------------------- selftest

CLEAN_FILE = '''\
import asyncio

import pytest

from pkg import Store, run, EXPECTED_ROWS


def assert_rows(store, expected):
    assert list(store.rows()) == expected


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "db")
    yield s
    s.close()


@pytest.mark.parametrize("slot, message", [
    ("large", "slot must be mini"),
    ("medium", "slot must be mini"),
])
def test_the_adapter_refuses_any_slot_but_mini(store, slot, message):
    with pytest.raises(ValueError, match=message):
        store.open(slot)


async def test_a_concurrent_put_keeps_fifo_order(store):
    store.put("a")
    await asyncio.sleep(0)
    store.put("b")

    assert_rows(store, ["a", "b"])


def test_a_missing_input_uses_the_default_path(store):
    result = run(store, path=None)

    assert result.path == "/path/to/default"
    assert [r.id for r in result.rows] == EXPECTED_ROWS


@pytest.mark.slow
@pytest.mark.skipif(not Store.live_available(), reason="needs rootless podman: see tests/support/live.py")
def test_the_live_store_round_trips_a_snapshot(store):
    snapshot = store.snapshot()

    assert store.restore(snapshot) == store.state()
'''


def selftest():
    cases = [
        # (text, rules that must appear, rules that must not appear)
        # test-name
        ("def test_adapter():\n    assert run() == 1\n", {"test-name"}, set()),
        ("def test_the_adapter_refuses_any_slot_but_mini():\n    assert run() == 1\n",
         set(), {"test-name"}),
        # control-flow
        ("def test_a_b_c():\n    for x in xs:\n        assert x\n", {"control-flow"}, set()),
        ("def test_a_b_c():\n    while x:\n        x = step()\n    assert x == 0\n",
         {"control-flow"}, set()),
        ("def test_a_b_c():\n    if cond:\n        assert run() == 1\n", {"control-flow"}, set()),
        ("def test_a_b_c():\n    try:\n        run()\n    except ValueError:\n        pass\n"
         "    assert run() == 1\n", {"control-flow"}, set()),
        ("def test_a_b_c():\n    assert [x for x in xs if x] == []\n", {"control-flow"}, set()),
        ("def test_a_b_c():\n    assert [x for x in xs] == []\n", set(), {"control-flow"}),
        ("def test_a_b_c():\n    def helper():\n        for x in xs:\n            pass\n"
         "    assert helper() is None\n", set(), {"control-flow"}),
        ("def test_a_b_c():\n    f = lambda: [x for x in xs if x]\n    assert f() == []\n",
         set(), {"control-flow"}),
        ("import pytest\ndef test_a_b_c():\n    with pytest.raises(ValueError, match='x'):\n"
         "        run()\n", set(), {"control-flow", "no-assert", "raises-no-match"}),
        # sleep
        ("import time\ndef test_a_b_c():\n    time.sleep(1)\n    assert ok()\n", {"sleep"}, set()),
        ("import time as t\ndef test_a_b_c():\n    t.sleep(1)\n    assert ok()\n", {"sleep"}, set()),
        ("from time import sleep\ndef test_a_b_c():\n    sleep(0.1)\n    assert ok()\n",
         {"sleep"}, set()),
        ("import asyncio\nasync def test_a_b_c():\n    await asyncio.sleep(0.1)\n    assert ok()\n",
         {"sleep"}, set()),
        ("import asyncio\nasync def test_a_b_c():\n    await asyncio.sleep(0)\n    assert ok()\n",
         set(), {"sleep"}),
        ("import time\nimport pytest\n@pytest.fixture\ndef thing():\n    time.sleep(1)\n"
         "    return 1\n", {"sleep"}, set()),
        ("import time\ndef helper():\n    time.sleep(1)\ndef test_a_b_c():\n    assert helper()\n",
         set(), {"sleep"}),
        ("def test_a_b_c():\n    sleep(1)\n    assert ok()\n", set(), {"sleep"}),
        # mock
        ("from unittest import mock\ndef test_a_b_c():\n    assert ok()\n", {"mock"}, set()),
        ("from unittest.mock import patch\ndef test_a_b_c():\n    assert ok()\n", {"mock"}, set()),
        ("import unittest.mock\ndef test_a_b_c():\n    assert ok()\n", {"mock"}, set()),
        ("import mock\ndef test_a_b_c():\n    with mock.patch('x'):\n        assert ok()\n",
         {"mock"}, set()),
        ("def test_a_b_c():\n    with patch('x'):\n        assert ok()\n", {"mock"}, set()),
        ("def test_a_b_c():\n    m = MagicMock()\n    assert m\n", {"mock"}, set()),
        ("def test_a_b_c():\n    m = Mock()\n    assert m\n", {"mock"}, set()),
        ("import mock\n@mock.patch.object(A, 'b')\ndef test_a_b_c(m):\n    assert m\n",
         {"mock"}, set()),
        ("from mylib import Mock\ndef test_a_b_c():\n    assert Mock() == 1\n", set(), {"mock"}),
        ("def test_a_b_c(monkeypatch):\n    monkeypatch.setattr(mod, 'run', fake)\n    assert ok()\n",
         set(), {"mock", "monkeypatch-private"}),
        # monkeypatch-private
        ("def test_a_b_c(monkeypatch):\n    monkeypatch.setattr(mod, '_helper', fake)\n"
         "    assert ok()\n", {"monkeypatch-private"}, set()),
        ("def test_a_b_c(monkeypatch):\n    monkeypatch.setattr('pkg.mod._helper', fake)\n"
         "    assert ok()\n", {"monkeypatch-private"}, set()),
        ("def test_a_b_c(monkeypatch):\n    monkeypatch.setattr(mod, '__call__', fake)\n"
         "    assert ok()\n", set(), {"monkeypatch-private"}),
        ("def test_a_b_c(monkeypatch):\n    monkeypatch.setenv('HOME', '/path/to/home')\n"
         "    assert ok()\n", set(), {"monkeypatch-private", "host-path"}),
        # no-assert
        ("def test_a_b_c():\n    run()\n", {"no-assert"}, set()),
        ("def test_a_b_c():\n    assert_rows(store, [])\n", set(), {"no-assert"}),
        ("class TestStore:\n    def test_a_b_c(self):\n        self.assertEqual(run(), 1)\n",
         set(), {"no-assert"}),
        ("import pytest\ndef test_a_b_c():\n    with pytest.warns(UserWarning, match='x'):\n"
         "        run()\n", set(), {"no-assert"}),
        # raises-no-match
        ("import pytest\ndef test_a_b_c():\n    with pytest.raises(ValueError):\n        run()\n",
         {"raises-no-match"}, set()),
        ("from pytest import raises\ndef test_a_b_c():\n    with raises(ValueError):\n        run()\n",
         {"raises-no-match"}, {"no-assert"}),
        ("import pytest\ndef test_a_b_c():\n    with pytest.raises(ValueError, match='bad'):\n"
         "        run()\n", set(), {"raises-no-match"}),
        # skip-no-reason
        ("import pytest\n@pytest.mark.skip\ndef test_a_b_c():\n    assert ok()\n",
         {"skip-no-reason"}, set()),
        ("import pytest\n@pytest.mark.skip()\ndef test_a_b_c():\n    assert ok()\n",
         {"skip-no-reason"}, set()),
        ("import pytest\n@pytest.mark.skipif(cond)\ndef test_a_b_c():\n    assert ok()\n",
         {"skip-no-reason"}, set()),
        ("import pytest\ndef test_a_b_c():\n    pytest.skip()\n    assert ok()\n",
         {"skip-no-reason"}, set()),
        ("import pytest\ndef test_a_b_c():\n    pytest.importorskip('x')\n    assert ok()\n",
         {"skip-no-reason"}, set()),
        ("import pytest\n@pytest.mark.skipif(cond, reason='needs podman: install it')\n"
         "def test_a_b_c():\n    assert ok()\n", set(), {"skip-no-reason"}),
        ("import pytest\n@pytest.mark.skip(reason='removed in v2')\ndef test_a_b_c():\n"
         "    assert ok()\n", set(), {"skip-no-reason"}),
        ("import pytest\ndef test_a_b_c():\n    pytest.skip('no DSN: set SPROUT_RUNSTORE_TEST_DSN')\n"
         "    assert ok()\n", set(), {"skip-no-reason"}),
        ("import pytest\ndef test_a_b_c():\n    pytest.importorskip('x', reason='needs x')\n"
         "    assert ok()\n", set(), {"skip-no-reason"}),
        ("from pytest import mark\n@mark.skip\ndef test_a_b_c():\n    assert ok()\n",
         {"skip-no-reason"}, set()),
        # slow-no-skip
        ("import pytest\n@pytest.mark.slow\ndef test_a_b_c():\n    assert ok()\n",
         {"slow-no-skip"}, set()),
        ("import pytest\n@pytest.mark.slow\n@pytest.mark.skipif(cond, reason='needs podman')\n"
         "def test_a_b_c():\n    assert ok()\n", set(), {"slow-no-skip"}),
        ("import pytest\n@pytest.mark.skipif(cond, reason='needs podman')\nclass TestLive:\n"
         "    @pytest.mark.slow\n    def test_a_b_c(self):\n        assert ok()\n",
         set(), {"slow-no-skip"}),
        ("import pytest\npytestmark = pytest.mark.skipif(cond, reason='needs podman')\n"
         "@pytest.mark.slow\ndef test_a_b_c():\n    assert ok()\n", set(), {"slow-no-skip"}),
        ("import pytest\npytestmark = pytest.mark.slow\ndef test_a_b_c():\n    assert ok()\n",
         {"slow-no-skip"}, set()),
        ("import pytest\npytestmark = [pytest.mark.slow, pytest.mark.skipif(cond, reason='x')]\n"
         "def test_a_b_c():\n    assert ok()\n", set(), {"slow-no-skip"}),
        # private-access
        ("def test_a_b_c(store):\n    assert store._rows == []\n", {"private-access"}, set()),
        ("def test_a_b_c(obj):\n    assert obj._helper() == 1\n", {"private-access"}, set()),
        ("class TestX:\n    def test_a_b_c(self):\n        assert self._make() == 1\n",
         set(), {"private-access"}),
        ("def test_a_b_c(request):\n    assert request._pyfuncitem is not None\n",
         set(), {"private-access"}),
        ("def test_a_b_c(obj):\n    assert obj.__class__ is X\n", set(), {"private-access"}),
        ("def test_a_b_c(obj):\n    assert obj.rows == []\n", set(), {"private-access"}),
        ("def test_a_b_c(monkeypatch):\n    monkeypatch._setattr(x, 'y', 1)\n    assert ok()\n",
         set(), {"private-access"}),
        # host-path
        ("def test_a_b_c():\n    assert run('/Users/alice/data') == 1\n", {"host-path"}, set()),
        ("def test_a_b_c():\n    assert run('/home/alice') == 1\n", {"host-path"}, set()),
        ("def test_a_b_c(name):\n    assert run(f'/Users/{name}/data') == 1\n", {"host-path"}, set()),
        ("ROOT = '/home/ci/work'\ndef test_a_b_c():\n    assert run(ROOT) == 1\n",
         {"host-path"}, set()),
        ("def test_a_b_c():\n    assert run('/path/to/home/x') == 1\n", set(), {"host-path"}),
        ("def test_a_b_c():\n    assert run('/path/to/data') == 1\n", set(), {"host-path"}),
        ("def test_a_b_c():\n    p = '/Users/alice'  # test-lint: ignore\n    assert run(p) == 1\n",
         set(), {"host-path"}),
        # partial-assert
        ("def test_a_b_c(out):\n    assert 'ok' in out.read_text()\n", {"partial-assert"}, set()),
        ("def test_a_b_c(err):\n    assert 'ok' in str(err)\n", {"partial-assert"}, set()),
        ("def test_a_b_c():\n    assert 'ok' in 'the run was ok'\n", {"partial-assert"}, set()),
        ("def test_a_b_c():\n    assert run().startswith('ok')\n", {"partial-assert"}, set()),
        ("def test_a_b_c(fh):\n    assert fh.read().endswith('ok')\n", {"partial-assert"}, set()),
        ("def test_a_b_c(out):\n    assert out.read_text() == 'ok\\n'\n", set(), {"partial-assert"}),
        ("def test_a_b_c(items):\n    assert 'a' in items\n", set(), {"partial-assert"}),
        ("def test_a_b_c(name):\n    assert name.startswith('x')\n", set(), {"partial-assert"}),
    ]
    failed = 0
    for text, must, must_not in cases:
        got = {f.rule for f in lint(text)}
        miss, extra = must - got, must_not & got
        if miss or extra:
            failed += 1
            print("FAIL %r\n  missing=%s unexpected=%s got=%s" % (text, sorted(miss), sorted(extra),
                                                                 sorted(got)))
    total = len(cases)

    # --disable silences a rule
    total += 1
    got = {f.rule for f in lint("def test_adapter():\n    assert run() == 1\n",
                                disabled={"test-name"})}
    if got:
        failed += 1
        print("FAIL --disable: got=%s" % sorted(got))

    # the clean file produces zero findings
    total += 1
    clean = lint(CLEAN_FILE, "clean.py")
    if clean:
        failed += 1
        print("FAIL clean file:")
        for f in clean:
            print("  %d:%d %s %s" % (f.line, f.col, f.rule, f.excerpt))

    print("selftest: %d/%d passed" % (total - failed, total))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic checks for pytest files against the "
                                             "testing skill.")
    ap.add_argument("paths", nargs="*", help="files, or directories to recurse for "
                                             "test_*.py, *_test.py and conftest.py")
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
    findings = []
    parse_errors = 0
    for path in collect(args.paths):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        try:
            findings += lint(text, path, disabled)
        except SyntaxError as e:
            parse_errors += 1
            print("%s:%s: cannot parse: %s" % (path, e.lineno or 0, e.msg), file=sys.stderr)
    status = report(findings, args.json, args.baseline)
    return 2 if parse_errors else status


if __name__ == "__main__":
    sys.exit(main())
