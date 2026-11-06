#!/usr/bin/env python3
"""Cost of the reviewer-authored turn versus an ordinary actor turn (read-only on the packaged fixed 4+3
trajectories): tokens of the analyst and reviewer calls that produce it, amortised per branch, next to the
per-turn tokens of the actor in the same branches and in the root rollouts, plus 'work' per turn (bash
commands and their length).

Run: python3 .claude/skills/trajectory-dataset/scripts/branch_turn_token_cost.py --package ~/sprout-runs/qwen/hf-stage/deepswe-fixed43-20261008/deepswe-fixed43-trajectories \\
        --analysis ~/sprout-runs/qwen/analysis/fixed43-branch-turns-20261008
Writes <analysis>/turn-token-cost.md and .json.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

MODELS = ("luna", "sonnet5", "kimi-k3")
OMITTED = re.compile(r"\n\.\.\. \[(\d+) chars omitted\] \.\.\.\n")


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1)))] if xs else None


def summ(xs):
    xs = [x for x in xs if x is not None]
    return {"n": len(xs), "median": statistics.median(xs), "mean": round(statistics.mean(xs), 1), "p90": q(xs, .9)} if xs else {"n": 0}


def usage_of(resp: dict) -> dict:
    u = (resp or {}).get("usage") or {}
    det = u.get("completion_tokens_details") or {}
    return {"prompt": u.get("prompt_tokens"), "completion": u.get("completion_tokens"),
            "reasoning": det.get("reasoning_tokens"), "visible": (u.get("completion_tokens") or 0) - (det.get("reasoning_tokens") or 0)}


def actor_turns(journal: Path) -> list:
    """Per actor turn: output / reasoning / prompt tokens (usage.updated) and the turn's commands."""
    turns, cur = [], None
    with open(journal, errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            t = r.get("type")
            if t == "turn.started":
                cur = {"source": r.get("source"), "usage": None, "commands": 0, "command_chars": 0}
            elif cur is None:
                continue
            elif t == "usage.updated":
                u = r.get("usage") or {}
                cur["usage"] = {"prompt": u.get("input_tokens"), "completion": u.get("output_tokens"),
                                "reasoning": u.get("reasoning_output_tokens") or 0,
                                "visible": (u.get("output_tokens") or 0) - (u.get("reasoning_output_tokens") or 0)}
            elif t == "tool.started":
                cmd = (r.get("args") or {}).get("command", "")
                m = re.match(r"^env\s[^\n]*?\bbash -c '(.*)'$", cmd, re.S)
                inner = (m.group(1) if m else cmd).replace("'\"'\"'", "'")
                cur["commands"] += 1
                cur["command_chars"] += len(inner)
            elif t == "turn.completed":
                if cur["source"] != "reviewer" and cur["usage"]:
                    turns.append(cur)
                cur = None
    return turns


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    args = parser.parse_args()
    branches = [json.loads(l) for l in (args.analysis / "branches.jsonl").open()]
    by_task = defaultdict(list)
    for b in branches:
        by_task[(b["model"], b["task"])].append(b)
    out, md = {}, ["# Token cost of the reviewer turn versus ordinary actor turns (fixed 4+3)", "",
                   "Analyst = one call per failed base (report); reviewer = one call per round (the plan with all 4 or 3 branches' assistant turns); "
                   "both are the same model as the actor, same reasoning effort. Actor turn tokens are per model call (usage.updated). "
                   "Prompt tokens for actor turns are mostly cache hits (94–98% cached).", ""]
    for m in MODELS:
        analyst, reviewer, per_branch_reviewer, per_branch_all = [], [], [], []
        branch_turns, root_turns = [], []
        reviewer_cmd = [(b["turn"]["n_commands"], b["turn"]["command_chars"], b["turn"]["content_chars"]) for b in branches if b["model"] == m]
        for task_dir in sorted((args.package / m).iterdir()):
            if task_dir.name == "experiment" or not (task_dir / "sprout").is_dir():
                continue
            n_br = len(by_task[(m, task_dir.name)])
            a_tot = r_tot = 0
            for rv in sorted((task_dir / "sprout/reviews").glob("review-*.json")):
                d = json.loads(rv.read_text())
                u = usage_of(d.get("response") if isinstance(d.get("response"), dict) else {})
                if u["completion"] is None:
                    continue
                text = (d.get("text") or "").lstrip()
                is_reviewer = text.startswith("```branch-plan") or '"branches"' in text[:4000] or '"synthesis"' in text[:2000]
                (reviewer if is_reviewer else analyst).append(u)
                if is_reviewer:
                    r_tot += u["completion"]
                else:
                    a_tot += u["completion"]
            per_branch_reviewer.append(r_tot / n_br)
            per_branch_all.append((r_tot + a_tot) / n_br)
            for unit in task_dir.glob("branch*"):
                branch_turns += actor_turns(unit / "journal.jsonl")
            root_turns += actor_turns(task_dir / "root" / "journal.jsonl")
        out[m] = {
            "analyst_call": {k: summ([u[k] for u in analyst]) for k in ("completion", "reasoning", "visible", "prompt")},
            "reviewer_call": {k: summ([u[k] for u in reviewer]) for k in ("completion", "reasoning", "visible", "prompt")},
            "reviewer_output_per_branch": summ(per_branch_reviewer),
            "analyst_plus_reviewer_output_per_branch": summ(per_branch_all),
            "actor_turn_in_branch": {k: summ([t["usage"][k] for t in branch_turns]) for k in ("completion", "reasoning", "visible", "prompt")},
            "actor_turn_in_root": {k: summ([t["usage"][k] for t in root_turns]) for k in ("completion", "reasoning", "visible", "prompt")},
            "work": {"reviewer_turn_commands": summ([c for c, _, _ in reviewer_cmd]),
                     "reviewer_turn_command_chars": summ([cc for _, cc, _ in reviewer_cmd]),
                     "reviewer_turn_text_chars": summ([tc for _, _, tc in reviewer_cmd]),
                     "actor_turn_commands": summ([t["commands"] for t in branch_turns]),
                     "actor_turn_command_chars": summ([t["command_chars"] for t in branch_turns if t["commands"]]),
                     "root_actor_turn_command_chars": summ([t["command_chars"] for t in root_turns if t["commands"]])},
            "n": {"analyst_calls": len(analyst), "reviewer_calls": len(reviewer), "branch_actor_turns": len(branch_turns), "root_actor_turns": len(root_turns)},
        }
        o = out[m]
        md += [f"## {m}", "",
               f"analyst calls {len(analyst)}, reviewer calls {len(reviewer)}, actor turns in branches {len(branch_turns)}, in roots {len(root_turns)}", "",
               "| per call / turn | output tokens median (mean, p90) | of which reasoning median | visible text median | prompt tokens median |", "|---|---|---|---|---|"]
        for label, key in (("analyst call (one report)", "analyst_call"), ("reviewer call (one plan = 4 or 3 turns)", "reviewer_call"),
                           ("actor turn, inside a branch", "actor_turn_in_branch"), ("actor turn, root rollout", "actor_turn_in_root")):
            c, r, v, p = o[key]["completion"], o[key]["reasoning"], o[key]["visible"], o[key]["prompt"]
            md.append(f"| {label} | {c['median']:.0f} ({c['mean']:.0f}, {c['p90']:.0f}) | {r['median']:.0f} | {v['median']:.0f} | {p['median']:.0f} |")
        md += ["", f"Reviewer output amortised per branch: median {o['reviewer_output_per_branch']['median']:.0f} tokens; analyst + reviewer per branch: "
               f"median {o['analyst_plus_reviewer_output_per_branch']['median']:.0f} tokens. A branch's own actor continuation: "
               f"median {statistics.median([b['continuation_model_calls'] for b in branches if b['model'] == m]):.0f} turns × "
               f"{o['actor_turn_in_branch']['completion']['median']:.0f} output tokens/turn.", "",
               "| work per turn | reviewer turn | actor turn (branch) | actor turn (root) |", "|---|---|---|---|",
               f"| bash commands, median (p90) | {o['work']['reviewer_turn_commands']['median']:.0f} ({o['work']['reviewer_turn_commands']['p90']:.0f}) | "
               f"{o['work']['actor_turn_commands']['median']:.0f} ({o['work']['actor_turn_commands']['p90']:.0f}) | – |",
               f"| command chars, median (p90) | {o['work']['reviewer_turn_command_chars']['median']:.0f} ({o['work']['reviewer_turn_command_chars']['p90']:.0f}) | "
               f"{o['work']['actor_turn_command_chars']['median']:.0f} ({o['work']['actor_turn_command_chars']['p90']:.0f}) | "
               f"{o['work']['root_actor_turn_command_chars']['median']:.0f} ({o['work']['root_actor_turn_command_chars']['p90']:.0f}) |",
               f"| assistant text chars, median | {o['work']['reviewer_turn_text_chars']['median']:.0f} | – | – |", ""]
        print(m, "done", flush=True)
    (args.analysis / "turn-token-cost.json").write_text(json.dumps(out, indent=1) + "\n")
    (args.analysis / "turn-token-cost.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
