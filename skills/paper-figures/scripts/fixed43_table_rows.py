#!/usr/bin/env python3
"""Main-table SPROUT rows for the fixed 4+3 podman experiments (Luna, Kimi K3, Sonnet 5): resolve
rate, recovery, steps and tokens, with the same definitions as the ash table
(deepswe-branch-best-20260925T1755Z/table_steps.py + table_accounting.py):

  steps    = tool.finished events (one bash call each) in the accepted root journal of every task
             plus every accepted branch journal (a branch journal holds only its new turns)
  tokens   = the stage's accepted total tokens (root once + branches + analyst/reviewer calls)
  recovery = (resolved - Pass@1 resolved) / (tasks - Pass@1 resolved), against the table's Pass@1
             column (mean of four independent attempts), as in the ash table; the run's own root
             is reported beside it

Read-only. Run: ~/sprout-runs/qwen/plots-env/bin/python .claude/skills/paper-figures/scripts/fixed43_table_rows.py
[--grade official] (writes <repo>/figures/fixed43-table-rows.json unless --output says otherwise)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixed43 import FIXED43_ROOTS, FIXED43_STAGE, load_fixed43  # noqa: E402
from plot_tokens_vs_resolve import DATA, FIGURES  # noqa: E402

TASKS = 113


def count(path: Path) -> tuple[int, int]:
    tools = calls = 0
    with open(path, errors="replace") as fh:
        for line in fh:
            if '"tool.finished"' in line:
                tools += 1
            elif '"raw.mini-swe-agent"' in line:
                calls += 1
    return tools, calls


def steps(root: Path) -> dict:
    accepted = json.loads((root / "accepted-sources.json").read_text())
    root_steps = root_calls = 0
    for task, src in accepted["baseline"].items():
        # a retry's task_root restarts at attempt-1 whatever the accepted attempt number; trial names are truncated
        journals = list((Path(src["task_root"]) / "baseline").glob("attempt-*/trials/*-parent/agent/trajectory.jsonl"))
        if len(journals) != 1:
            raise SystemExit(f"{root.name}: {task} accepted baseline {src['task_root']} has {len(journals)} journals")
        t, c = count(journals[0])
        root_steps += t
        root_calls += c
    branch_steps = branch_calls = branches = 0
    tasks_with_branches = root_resolved_tasks = 0
    for task, src in accepted[FIXED43_STAGE].items():
        summary_path = Path(src["task_root"]) / "sprout" / "summary.json"
        if not summary_path.exists():
            root_resolved_tasks += 1  # the root resolved it: the stage never ran branching for this task
            continue
        summary = json.loads(summary_path.read_text())
        parent = next(a for a in summary["attempts"] if a["name"] == "parent")
        # an accepted task_root's "baseline" may be a symlink into the shared baseline experiment
        want = (Path(accepted["baseline"][task]["task_root"]) / "baseline").resolve()
        if not Path(parent["journal"]).resolve().is_relative_to(want):
            raise SystemExit(f"{root.name}: {task} sprout parent {parent['journal']} is not the accepted baseline {want}")
        rows = [a for a in summary["attempts"] if a["round"] > 0]
        if rows:
            tasks_with_branches += 1
        for a in rows:
            t, c = count(Path(a["journal"]))
            branch_steps += t
            branch_calls += c
            branches += 1
    if len(accepted["baseline"]) != TASKS or len(accepted[FIXED43_STAGE]) != TASKS:
        raise SystemExit(f"{root.name}: accepted sources cover {len(accepted['baseline'])}/{len(accepted[FIXED43_STAGE])} tasks")
    stage = {r["stage"]: r for r in json.loads((root / "scaling.json").read_text())["stages"]}
    if root_resolved_tasks != stage["baseline"]["resolved"]:
        raise SystemExit(f"{root.name}: {root_resolved_tasks} tasks without a sprout summary, "
                         f"but the root resolved {stage['baseline']['resolved']}")
    return {"root_steps": root_steps, "root_model_calls": root_calls, "branches": branches,
            "tasks_with_branches": tasks_with_branches, "branch_steps": branch_steps,
            "branch_model_calls": branch_calls,
            "steps_per_branch_mean": round(branch_steps / branches, 1) if branches else None,
            "sprout_total_steps": root_steps + branch_steps}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grade", choices=("official", "audited"), default="official")
    parser.add_argument("--output", type=Path, default=FIGURES / "fixed43-table-rows.json")
    args = parser.parse_args()
    points = load_fixed43(args.grade)
    out = {}
    for model, p in points.items():
        root = FIXED43_ROOTS[model]
        s = steps(root)
        pass1_rate = DATA[model]["Pass@1"][0]
        pass1_resolved = pass1_rate / 100 * TASKS
        resolved = p["resolved"]
        out[model] = {
            **p, **s,
            "recovery_vs_table_pass1": round(100 * (resolved - pass1_resolved) / (TASKS - pass1_resolved), 1),
            "recovery_vs_own_root": round(100 * (resolved - p["root_resolved"]) / (TASKS - p["root_resolved"]), 1),
            "table_pass1_rate": pass1_rate, "tokens_M_rounded": round(p["tokens_M"]),
        }
        r = out[model]
        print(f"== {model}  ({root.name}, {args.grade})")
        print(f"   resolve {resolved}/{TASKS} = {r['rate']}%   (official {r['official_resolved']}, audited {r['audited_resolved']}; root {r['root_resolved']})")
        print(f"   recovery vs table Pass@1 {pass1_rate}%: {r['recovery_vs_table_pass1']}%   vs own root: {r['recovery_vs_own_root']}%")
        print(f"   steps: root {s['root_steps']} + branches {s['branch_steps']} ({s['branches']} branches over "
              f"{s['tasks_with_branches']} tasks, {s['steps_per_branch_mean']}/branch) = {s['sprout_total_steps']}")
        print(f"   tokens: {r['tokens_M_rounded']} M")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=1) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
