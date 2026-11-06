#!/usr/bin/env python3
"""Extract every SPROUT branch's reviewer-authored assistant turn, with its context and outcome, from the
packaged fixed 4+3 trajectories (read-only), for the branch-turn analysis.

One JSON per branch under <out>/<model>/<task>__<unit>.json and all of them in <out>/branches.jsonl:

  position      branch_step (tool-call index in the base) / base_total_steps, base = root or a round-1 branch
  continuation  the branch's own actor turns (model_calls) and tool calls (steps) after the reviewer turn
  turn          the reviewer's assistant text, its bash commands and their real observations
  context       the analyst report of the base (failure_reason, lesson, salvage), the reviewer's why + synthesis,
                the task prompt head, the actor's first reply and last message, the verdict

Run: python3 .claude/skills/trajectory-dataset/scripts/extract_branch_turns.py --package ~/sprout-runs/qwen/hf-stage/deepswe-fixed43-20261008/deepswe-fixed43-trajectories \\
         --out ~/sprout-runs/qwen/analysis/fixed43-branch-turns-20261008
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MODELS = ("luna", "sonnet5", "kimi-k3")


def read(p: Path):
    return json.loads(p.read_text())


def clip(text, head=1500, tail=500):
    if text is None:
        return None
    text = str(text)
    if len(text) <= head + tail + 20:
        return text
    return text[:head] + f"\n... [{len(text) - head - tail} chars omitted] ...\n" + text[-tail:]


def commands_of(turn: dict) -> list:
    out = []
    for call in turn.get("tool_calls") or []:
        args = call.get("function", {}).get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {"command": args}
        out.append({"id": call.get("id"), "command": (args or {}).get("command")})
    return out


def journal_facts(journal: Path) -> dict:
    """Reviewer-command observations, the actor's first and last messages, run result, and the task prompt."""
    reviewer_results, actor_messages, result, task_prompt = [], [], None, None
    with open(journal, errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            t = r.get("type")
            if t == "tool.finished" and str(r.get("call_id", "")).startswith("reviewer-"):
                oc = r.get("outcome") or {}
                reviewer_results.append({"call_id": r["call_id"], "status": r.get("status"),
                                         "exit_code": oc.get("exit_code") if isinstance(oc, dict) else None,
                                         "timed_out": oc.get("timed_out") if isinstance(oc, dict) else None,
                                         "output": clip(r.get("output"), 1200, 400)})
            elif t == "agent.message":
                actor_messages.append(r.get("text") or "")
            elif t == "run.result":
                result = {k: v for k, v in r.items() if k not in ("v", "seq", "agent_id", "sandbox_id", "ts")}
            elif t == "run.started" and r.get("task_prompt"):
                task_prompt = r["task_prompt"]
    # actor_messages[0] is the reviewer's own text (journaled as agent.message); the actor's first reply follows
    return {"reviewer_results": reviewer_results,
            "actor_first_message": clip(actor_messages[1], 1200, 300) if len(actor_messages) > 1 else None,
            "actor_last_message": clip(actor_messages[-1], 800, 300) if len(actor_messages) > 1 else None,
            "actor_messages": max(0, len(actor_messages) - 1), "run_result": result, "task_prompt": task_prompt}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for model in MODELS:
        (args.out / model).mkdir(exist_ok=True)
        for task_dir in sorted((args.package / model).iterdir()):
            if task_dir.name == "experiment" or not (task_dir / "sprout").is_dir():
                continue
            task = task_dir.name
            task_meta = read(task_dir / "meta.json")
            root_meta = read(task_dir / "root" / "meta.json")
            root_facts = journal_facts(task_dir / "root" / "journal.jsonl")
            plans = {int(re.search(r"round(\d+)", p.name).group(1)): read(p)
                     for p in task_dir.glob("sprout/plan-round*.json")}
            units = {p.parent.name: read(p) for p in task_dir.glob("branch*/meta.json")}
            # A branch journal numbers its tool steps from 1 at the reviewer turn, so a round-2 branch's
            # branch_step is in its base branch's own numbering. Absolute = base's fork step + own step;
            # total tool steps of a base: the root's, or (fork step + own steps) for a round-1 branch.
            base_total = {"root": root_meta["steps"]}
            base_fork_abs = {"root": 0}
            for unit, m in units.items():
                base_total[unit] = m["branch_step"] + m["steps"]
                base_fork_abs[unit] = m["branch_step"]
            for unit in sorted(units, key=lambda u: int(u[6:])):
                m = units[unit]
                plan = plans.get(m["round"]) or {}
                chosen = plan.get("selected_branches", [])
                idx = next((i for i, b in enumerate(chosen) if b["run_name"] == m["original_name"]), None)
                selected = chosen[idx] if idx is not None else None
                # selected_branches and review.branches are the same plan in the same order (run names are
                # truncated, so match by position rather than by name)
                reviewed = (plan.get("review") or {}).get("branches", [])
                review_branch = reviewed[idx] if idx is not None and len(reviewed) == len(chosen) else None
                turn = (selected or {}).get("assistant_turn") or {}
                report = (plan.get("reports") or {}).get(m["base_original_name"]) or {}
                facts = journal_facts(task_dir / unit / "journal.jsonl")
                base_len = base_total.get(m["base"])
                fork_abs = base_fork_abs.get(m["base"], 0) + m["branch_step"]
                base_own = units[m["base"]]["steps"] if m["base"] in units else None
                row = {
                    "id": f"{model}/{task}/{unit}", "model": model, "task": task, "unit": unit,
                    "original_name": m["original_name"], "round": m["round"], "index_in_round": m.get("index_in_round"),
                    "base": m["base"], "base_original_name": m["base_original_name"],
                    "branch_step": m["branch_step"], "fork_step_absolute": fork_abs, "base_total_steps": base_len,
                    "position": round(fork_abs / base_len, 4) if base_len else None,
                    "position_within_base_own": round(m["branch_step"] / base_own, 4) if base_own else None,
                    "base_own_steps": base_own,
                    "root_total_steps": root_meta["steps"], "root_model_calls": root_meta["model_calls"],
                    "continuation_steps": m["steps"], "continuation_model_calls": m["model_calls"],
                    "continuation_actor_messages": facts["actor_messages"],
                    "resolved": m["resolved"], "reward": m["reward"], "status": m["status"],
                    "audit_verdict": m["audit"]["verdict"], "seconds": m.get("seconds"),
                    "task_resolved_by": task_meta["sprout"]["resolved_by"],
                    "siblings_resolved_same_round": sum(1 for u, x in units.items()
                                                        if x["round"] == m["round"] and x["resolved"] and u != unit),
                    "turn": {"content": turn.get("content"), "commands": commands_of(turn),
                             "n_commands": len(turn.get("tool_calls") or []),
                             "content_chars": len(turn.get("content") or ""),
                             "command_chars": sum(len(c["command"] or "") for c in commands_of(turn))},
                    "reviewer_results": facts["reviewer_results"],
                    "reviewer_why": (review_branch or {}).get("why"),
                    "review_synthesis": (plan.get("review") or {}).get("synthesis"),
                    "base_report": {k: report.get(k) for k in ("failure_reason", "lesson", "salvage", "steps")},
                    "base_candidates": report.get("branch_candidates"),
                    "task_prompt_head": clip(root_facts["task_prompt"], 1500, 0),
                    "actor_first_message": facts["actor_first_message"],
                    "actor_last_message": facts["actor_last_message"],
                    "run_result": facts["run_result"],
                    "package_dir": str(task_dir / unit),
                }
                if turn.get("content") is None:
                    row["missing_turn"] = True
                rows.append(row)
                (args.out / model / f"{task}__{unit}.json").write_text(json.dumps(row, indent=1, ensure_ascii=False) + "\n")
        print(model, sum(1 for r in rows if r["model"] == model), flush=True)
    with (args.out / "branches.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(rows), "branches;", sum(1 for r in rows if r.get("missing_turn")), "without a recorded turn")


if __name__ == "__main__":
    main()
