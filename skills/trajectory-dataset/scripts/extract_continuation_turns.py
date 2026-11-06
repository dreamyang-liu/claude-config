#!/usr/bin/env python3
"""What the actor does after the reviewer-authored turn: every continuation turn of every SPROUT branch,
labelled lexically from its bash commands (read-only on the packaged trajectories).

Per turn (multi-label, from the commands' text):
  edit_source / edit_tests / edit_unknown  a command that writes a file (heredoc > path, sed -i, python
                                           open(..., 'w') / write_text, printf >> path, git apply, patch),
                                           split by whether the path looks like a test file
  run_tests        pytest, go test, cargo test, vitest/jest/mocha, npm/pnpm/yarn/bun test, unittest, tox, ...
  lint_build       eslint, black, ruff, mypy, tsc, go vet/build, cargo build/check/clippy, golangci-lint, ...
  probe_script     a python/node heredoc or -c that does not write files (ad-hoc check)
  git              git add/commit/stash/checkout/reset/restore
  inspect          grep/rg/cat/sed -n/head/tail/ls/find/nl/wc/git diff|status|log
  submit           the mini-swe-agent submission marker
Primary label = highest-precedence label of the turn (submit > edit_* > run_tests > lint_build > probe_script
> git > inspect > other).

Outputs under <out>/continuations/: <model>/<task>__<unit>.json (turn list with message heads, commands and
observation heads: the input for a qualitative pass), continuations.jsonl (one row per branch: label sequence
and counts), continuation-stats.md / .json.

Run: python3 .claude/skills/trajectory-dataset/scripts/extract_continuation_turns.py --package ~/sprout-runs/qwen/hf-stage/deepswe-fixed43-20261008/deepswe-fixed43-trajectories \\
         --out ~/sprout-runs/qwen/analysis/fixed43-branch-turns-20261008
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path

MODELS = ("luna", "sonnet5", "kimi-k3")
TEST_PATH = re.compile(r"(^|/)(tests?|t|spec|specs|__tests__|testdata|__snapshots__|e2e|fixtures)(/|$)|(^|/)(test_[^/]*|[^/]*_test\.[a-z]+|[^/]*\.(test|spec)\.[a-z]+|conftest\.py)$")
WRITE_PATH_PATTERNS = [
    re.compile(r"cat\s*>\s*(['\"]?)([^\s'\"<>|;&]+)\1\s*<<"),               # cat > path <<EOF
    re.compile(r"cat\s*<<\s*-?\s*['\"]?\w+['\"]?\s*>\s*(['\"]?)([^\s'\"<>|;&]+)\1"),  # cat <<EOF > path
    re.compile(r"\btee\s+(-a\s+)?(['\"]?)([^\s'\"<>|;&]+)\2"),
    re.compile(r"\b(?:sed|perl)\s+-[a-zA-Z]*i[a-zA-Z]*\b[^\n|;&]*?\s(['\"]?)([^\s'\"<>|;&]+\.[a-zA-Z]+)\1\s*(?:$|\n|;|&&)"),
    re.compile(r"(?:printf|echo)\s[^\n]*?>>?\s*(['\"]?)([^\s'\"<>|;&]+)\1"),
    re.compile(r"open\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"][wa]"),
    re.compile(r"Path\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\.write_(?:text|bytes)\("),
    re.compile(r"writeFileSync\(\s*['\"]([^'\"]+)['\"]"),
    # python heredoc patches assign the path to a variable, then open(path, "w") / Path(path).write_text
    re.compile(r"(?m)^\s*(?:path|p|fn|fname|filename|file|target|src_path|dst|out_path|PATH|FILE)\s*=\s*(?:pathlib\.)?(?:Path\()?\s*['\"]([^'\"]+)['\"](?=[\s\S]*(?:open\([^)]*['\"][wa]|\.write_(?:text|bytes)\(|\.write\())"),
    re.compile(r"(?:pathlib\.)?Path\(\s*['\"]([^'\"]+)['\"]\s*\)(?=[\s\S]{0,400}\.write_(?:text|bytes)\()"),
    re.compile(r"\bmv\s+(?:-f\s+)?\S+\s+(['\"]?)([^\s'\"<>|;&]+)\1"),
    re.compile(r"\bcp\s+(?:-[a-z]+\s+)?\S+\s+(['\"]?)([^\s'\"<>|;&]+)\1"),
]
WRITE_ANY = re.compile(r"\.write_(?:text|bytes)\(|\.write\(|open\([^)]*['\"][wa]|writeFileSync|git apply|\bpatch\s+-p|\bsed\s+-[a-zA-Z]*i|perl\s+-[a-zA-Z]*i|cat\s*>|cat\s*<<[^\n]*>\s*\S|\btee\s|>>\s*\S|\bmv\s|\bcp\s|\brm\s|\bmkdir\s|\btouch\s|\bgit\s+(checkout|restore|stash)\b")
RUN_TESTS = re.compile(r"\b(pytest|py\.test|python3?\s+-m\s+(pytest|unittest)|go\s+test|cargo\s+test|cargo\s+nextest|npm\s+(run\s+)?test|pnpm\s+(run\s+)?test|yarn\s+(run\s+)?test|bun\s+test|npx\s+(vitest|jest|mocha|ava|tsx\s+[^\n]*test)|vitest(\s+run)?|\bjest\b|mix\s+test|\btox\b|make\s+test|ctest|rspec|gradlew\s+test|deno\s+test|/tmp/\S*test\S*\.sh|rtest)\b")
LINT_BUILD = re.compile(r"\b(eslint|black|ruff|flake8|isort|mypy|pyright|tsc|go\s+(vet|build|fmt)|gofmt|golangci-lint|cargo\s+(build|check|clippy|fmt)|npm\s+run\s+(build|lint|typecheck|check)|pnpm\s+(run\s+)?(build|lint|typecheck|check)|oxlint|prettier|biome|pip\s+install|npm\s+(install|ci)|pnpm\s+install|go\s+mod|make\b(?!\s+test))")
GIT = re.compile(r"\bgit\s+(add|commit|stash|checkout|reset|restore|revert|rm|mv|clean)\b")
INSPECT = re.compile(r"\b(grep|rg|ag|cat|sed\s+-n|head|tail|less|ls|find|fd|nl|wc|tree|stat|file|which|git\s+(diff|status|log|show|blame|branch))\b")
SUBMIT = re.compile(r"COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT|MINI_SWE_AGENT_FINAL_OUTPUT")
SCRIPT = re.compile(r"\b(python3?|node|deno|ruby|perl|go\s+run|cargo\s+run)\b\s*(-\s*<<|<<|-c\b|-e\b|/tmp/\S+)")
PRECEDENCE = ["submit", "edit_source", "edit_tests", "edit_unknown", "run_tests", "lint_build", "probe_script", "git", "inspect", "other"]
SHORT = {"submit": "S", "edit_source": "E", "edit_tests": "e", "edit_unknown": "w", "run_tests": "T", "lint_build": "L",
         "probe_script": "P", "git": "G", "inspect": "I", "other": "O"}
WRAPPER = re.compile(r"^env\s[^\n]*?\bbash -c '(.*)'$", re.S)


def inner_command(cmd: str) -> str:
    m = WRAPPER.match(cmd or "")
    s = m.group(1) if m else (cmd or "")
    return s.replace("'\"'\"'", "'")


def written_paths(cmd: str) -> list:
    out = []
    for pat in WRITE_PATH_PATTERNS:
        for m in pat.finditer(cmd):
            path = m.group(m.lastindex) if m.lastindex else m.group(0)
            if path and not path.startswith(("/dev/", "/tmp/", "$")) and "." in Path(path).name:
                out.append(path)
    return out


def labels_of(cmd: str) -> set:
    labels = set()
    paths = written_paths(cmd)
    if paths:
        for p in paths:
            labels.add("edit_tests" if TEST_PATH.search(p) else "edit_source")
    elif re.search(r"\.write_(?:text|bytes)\(|\.write\(|open\([^)]*['\"][wa]|writeFileSync|git apply|\bpatch\s+-p|\bsed\s+-[a-zA-Z]*i|perl\s+-[a-zA-Z]*i", cmd):
        labels.add("edit_unknown")
    if RUN_TESTS.search(cmd):
        labels.add("run_tests")
    if LINT_BUILD.search(cmd):
        labels.add("lint_build")
    if SUBMIT.search(cmd):
        labels.add("submit")
    if GIT.search(cmd):
        labels.add("git")
    if SCRIPT.search(cmd) and not (labels & {"edit_source", "edit_tests", "edit_unknown", "run_tests"}):
        labels.add("probe_script")
    if INSPECT.search(cmd) and not labels:
        labels.add("inspect")
    if not labels:
        labels.add("other")
    return labels


def primary(labels: set) -> str:
    return next(l for l in PRECEDENCE if l in labels)


def turns_of(journal: Path) -> list:
    """Actor turns after the reviewer turn: message head, commands, labels, observation heads."""
    turns, cur = [], None
    with open(journal, errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            t = r.get("type")
            if t == "turn.started":
                cur = {"turn": r.get("turn"), "source": r.get("source"), "message": "", "commands": [], "commands_full": [],
                       "results": [], "rejected": False}
            elif cur is None:
                continue
            elif t == "agent.message":
                cur["message"] = (r.get("text") or "")[:700]
            elif t == "tool.started":
                cmd = inner_command((r.get("args") or {}).get("command", ""))
                cur["commands_full"].append(cmd)
                cur["commands"].append(cmd if len(cmd) <= 1600 else cmd[:1200] + f"\n... [{len(cmd) - 1500} chars omitted] ...\n" + cmd[-300:])
            elif t == "tool.finished":
                oc = r.get("outcome") or {}
                cur["results"].append({"status": r.get("status"), "exit_code": oc.get("exit_code") if isinstance(oc, dict) else None,
                                       "head": (r.get("output") or "")[:300]})
            elif t == "turn.completed":
                cur["rejected"] = bool(r.get("rejected"))
                if cur["source"] != "reviewer":
                    labels = set()
                    for c in cur["commands_full"]:
                        labels |= labels_of(c)
                    if not cur["commands_full"]:
                        labels = {"other"}
                    del cur["commands_full"]
                    cur["labels"] = sorted(labels)
                    cur["primary"] = primary(labels)
                    cur["nonzero_exit"] = any((x.get("exit_code") or 0) != 0 for x in cur["results"])
                    turns.append(cur)
                cur = None
    return turns


def compress(seq: list) -> str:
    """Run-length collapse of the primary-label letters: T T E T S -> T+ E T S."""
    out = []
    for s in seq:
        if out and out[-1][0] == s:
            out[-1] = (s, out[-1][1] + 1)
        else:
            out.append((s, 1))
    return " ".join(f"{s}+" if n > 1 else s for s, n in out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out / "continuations"
    rows = []
    branch_rows = {json.loads(l)["id"]: json.loads(l) for l in (args.out / "branches.jsonl").open()}
    for model in MODELS:
        (out / model).mkdir(parents=True, exist_ok=True)
        for task_dir in sorted((args.package / model).iterdir()):
            if task_dir.name == "experiment" or not (task_dir / "sprout").is_dir():
                continue
            for unit_dir in sorted(task_dir.glob("branch*"), key=lambda p: int(p.name[6:])):
                bid = f"{model}/{task_dir.name}/{unit_dir.name}"
                b = branch_rows[bid]
                turns = turns_of(unit_dir / "journal.jsonl")
                seq = [SHORT[t["primary"]] for t in turns]
                counts = Counter(t["primary"] for t in turns)
                any_edit = [i for i, t in enumerate(turns) if set(t["labels"]) & {"edit_source", "edit_tests", "edit_unknown"}]
                src_edit = [i for i, t in enumerate(turns) if "edit_source" in t["labels"]]
                row = {"id": bid, "model": model, "task": task_dir.name, "unit": unit_dir.name, "resolved": b["resolved"],
                       "round": b["round"], "position": b["position"], "n_turns": len(turns),
                       "sequence": "".join(seq), "pattern": compress(seq),
                       "counts": dict(counts), "edit_turns": len(any_edit), "source_edit_turns": len(src_edit),
                       "test_edit_turns": sum(1 for t in turns if "edit_tests" in t["labels"]),
                       "test_run_turns": sum(1 for t in turns if "run_tests" in t["labels"]),
                       "first_edit_turn": (any_edit[0] + 1) if any_edit else None,
                       "ends_with_submit": bool(seq) and seq[-1] == "S",
                       "rejected_turns": sum(1 for t in turns if t["rejected"]),
                       "nonzero_exit_turns": sum(1 for t in turns if t["nonzero_exit"]),
                       "reviewer_turn": {"content": b["turn"]["content"], "commands": [c["command"] for c in b["turn"]["commands"]],
                                         "results": b["reviewer_results"]},
                       "continuation": turns}
                (out / model / f"{task_dir.name}__{unit_dir.name}.json").write_text(json.dumps(row, indent=1, ensure_ascii=False) + "\n")
                rows.append({k: v for k, v in row.items() if k not in ("continuation", "reviewer_turn")})
        print(model, "done", flush=True)
    with (out / "continuations.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- aggregate
    def share(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    stats, md = {}, ["# Continuation turns: what the actor does after the reviewer turn", "",
                     "Labels are lexical (see extract_continuation_turns.py); E = edit source, e = edit tests, w = write (path unknown), "
                     "T = run tests, L = lint/build/install, P = ad-hoc script, G = git add/commit/checkout, I = inspect, S = submit, O = other.", ""]
    md += ["## Turn-level: primary label of every continuation turn (share of turns)", ""]
    labels = PRECEDENCE
    md.append("| model | split | turns | " + " | ".join(labels) + " |")
    md.append("|---|---|---|" + "---|" * len(labels))
    for m in MODELS + ("all",):
        for res in (True, False):
            rs = [r for r in rows if (m == "all" or r["model"] == m) and r["resolved"] == res]
            c = Counter()
            for r in rs:
                c.update(r["counts"])
            n = sum(c.values())
            stats[f"{m}/{'resolved' if res else 'unresolved'}/turn_labels"] = {k: c.get(k, 0) for k in labels}
            md.append(f"| {m} | {'resolved' if res else 'unresolved'} | {n} | " + " | ".join(f"{100 * c.get(k, 0) / n:.0f}%" if n else "–" for k in labels) + " |")
    md += ["", "## Branch-level: did the actor itself edit code during the continuation?", ""]
    md.append("| model | split | branches | any edit | source edit | test-file edit | median edit turns (of those) | median share of edit turns | verification-only (no edit) | verification-only & ≤3 turns | ends with submit |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for m in MODELS + ("all",):
        for res in (True, False):
            rs = [r for r in rows if (m == "all" or r["model"] == m) and r["resolved"] == res]
            if not rs:
                continue
            ed = [r for r in rs if r["edit_turns"]]
            st = {"n": len(rs), "any_edit": share([bool(r["edit_turns"]) for r in rs]),
                  "source_edit": share([bool(r["source_edit_turns"]) for r in rs]),
                  "test_edit": share([bool(r["test_edit_turns"]) for r in rs]),
                  "median_edit_turns_given_edit": statistics.median([r["edit_turns"] for r in ed]) if ed else None,
                  "median_edit_share": round(statistics.median([r["edit_turns"] / r["n_turns"] for r in rs if r["n_turns"]]), 3),
                  "verification_only": share([not r["edit_turns"] for r in rs]),
                  "verification_only_le3": share([(not r["edit_turns"]) and r["n_turns"] <= 3 for r in rs]),
                  "ends_with_submit": share([r["ends_with_submit"] for r in rs])}
            stats[f"{m}/{'resolved' if res else 'unresolved'}/branch"] = st
            md.append(f"| {m} | {'resolved' if res else 'unresolved'} | {st['n']} | {st['any_edit']:.0%} | {st['source_edit']:.0%} | {st['test_edit']:.0%} | "
                      f"{st['median_edit_turns_given_edit']} | {st['median_edit_share']:.2f} | {st['verification_only']:.0%} | {st['verification_only_le3']:.0%} | {st['ends_with_submit']:.0%} |")
    md += ["", "## Edit turns vs continuation length (resolved branches): does a longer continuation mean more repair, or more verification?", ""]
    md.append("| model | continuation turns | branches | median edit turns | median test-run turns | median inspect turns | median edit share |")
    md.append("|---|---|---|---|---|---|---|")
    for m in MODELS:
        for lo, hi, label in [(1, 2, "1-2"), (3, 5, "3-5"), (6, 10, "6-10"), (11, 20, "11-20"), (21, 40, "21-40"), (41, 10 ** 6, "41+")]:
            rs = [r for r in rows if r["model"] == m and r["resolved"] and lo <= r["n_turns"] <= hi]
            if not rs:
                continue
            md.append(f"| {m} | {label} | {len(rs)} | {statistics.median([r['edit_turns'] for r in rs])} | "
                      f"{statistics.median([r['test_run_turns'] for r in rs])} | {statistics.median([r['counts'].get('inspect', 0) for r in rs])} | "
                      f"{statistics.median([r['edit_turns'] / r['n_turns'] for r in rs]):.2f} |")
    md += ["", "## Most common continuation patterns (run-length collapsed primary labels), per model and outcome", ""]
    for m in MODELS:
        for res in (True, False):
            rs = [r for r in rows if r["model"] == m and r["resolved"] == res]
            c = Counter(r["pattern"] for r in rs)
            md.append(f"**{m}, {'resolved' if res else 'unresolved'}** ({len(rs)}): " + "; ".join(f"`{p}` ×{n}" for p, n in c.most_common(8)))
            md.append("")
    md += ["## First actor edit: at which continuation turn (resolved branches with an edit)", ""]
    for m in MODELS:
        rs = [r for r in rows if r["model"] == m and r["resolved"] and r["first_edit_turn"]]
        c = Counter("1" if r["first_edit_turn"] == 1 else "2" if r["first_edit_turn"] == 2 else "3-5" if r["first_edit_turn"] <= 5 else "6+" for r in rs)
        md.append(f"- {m}: n={len(rs)}; first edit at turn 1: {c['1']}, 2: {c['2']}, 3-5: {c['3-5']}, 6+: {c['6+']}")
    (out / "continuation-stats.json").write_text(json.dumps(stats, indent=1) + "\n")
    (out / "continuation-stats.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
