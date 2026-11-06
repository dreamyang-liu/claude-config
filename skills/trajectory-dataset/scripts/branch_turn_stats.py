#!/usr/bin/env python3
"""Quantitative view of the SPROUT branch turns extracted by extract_branch_turns.py: where branches fork
(position in the base), how long the continuation runs, and how that differs between resolved and
unresolved branches, per model and round. Writes stats.json and stats.md next to branches.jsonl.

Run: python3 .claude/skills/trajectory-dataset/scripts/branch_turn_stats.py \\
         ~/sprout-runs/qwen/analysis/fixed43-branch-turns-20261008
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

BUCKETS = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 0.9), (0.9, 1.01)]


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summary(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "mean": round(statistics.mean(xs), 3), "median": q(xs, .5), "q1": q(xs, .25),
            "q3": q(xs, .75), "p90": q(xs, .9), "min": min(xs), "max": max(xs)}


def split(rows):
    return {"all": rows, "resolved": [r for r in rows if r["resolved"]],
            "unresolved": [r for r in rows if not r["resolved"]]}


def block(rows):
    out = {}
    for name, rs in split(rows).items():
        out[name] = {
            "n": len(rs),
            "position": summary([r["position"] for r in rs]),
            "branch_step": summary([r["branch_step"] for r in rs]),
            "base_total_steps": summary([r["base_total_steps"] for r in rs]),
            "fork_step_absolute": summary([r["fork_step_absolute"] for r in rs]),
            "steps_left_in_base": summary([r["base_total_steps"] - r["fork_step_absolute"] for r in rs]),
            "position_within_base_own": summary([r.get("position_within_base_own") for r in rs]),
            "continuation_actor_turns": summary([r["continuation_model_calls"] for r in rs]),
            "continuation_tool_steps": summary([r["continuation_steps"] for r in rs]),
            "continuation_over_base_remaining": summary([
                r["continuation_model_calls"] / max(1, r["base_total_steps"] - r["fork_step_absolute"]) for r in rs]),
            "reviewer_commands": summary([r["turn"]["n_commands"] for r in rs]),
            "reviewer_text_chars": summary([r["turn"]["content_chars"] for r in rs]),
            "reviewer_command_chars": summary([r["turn"]["command_chars"] for r in rs]),
            "reviewer_cmd_nonzero_exit_share": round(statistics.mean(
                [any((x.get("exit_code") or 0) != 0 for x in r["reviewer_results"]) for r in rs]), 3) if rs else None,
            "seconds": summary([r["seconds"] for r in rs]),
        }
    out["resolve_rate"] = round(out["resolved"]["n"] / len(rows), 3) if rows else None
    # resolve rate by position bucket
    buckets = {}
    for lo, hi in BUCKETS:
        rs = [r for r in rows if lo <= r["position"] < hi]
        buckets[f"{lo:.2f}-{min(hi, 1):.2f}"] = {"n": len(rs), "resolved": sum(r["resolved"] for r in rs),
                                                 "rate": round(sum(r["resolved"] for r in rs) / len(rs), 3) if rs else None}
    out["by_position_bucket"] = buckets
    # resolve rate by continuation length bucket
    cont = {}
    for lo, hi, label in [(0, 3, "1-2"), (3, 6, "3-5"), (6, 11, "6-10"), (11, 21, "11-20"), (21, 41, "21-40"), (41, 10 ** 6, "41+")]:
        rs = [r for r in rows if lo <= r["continuation_model_calls"] < hi]
        cont[label] = {"n": len(rs), "resolved": sum(r["resolved"] for r in rs),
                       "rate": round(sum(r["resolved"] for r in rs) / len(rs), 3) if rs else None}
    out["by_continuation_turns"] = cont
    # reviewer command failure vs outcome
    fail = [r for r in rows if any((x.get("exit_code") or 0) != 0 for x in r["reviewer_results"])]
    ok = [r for r in rows if r not in fail]
    out["reviewer_command_exit"] = {
        "nonzero": {"n": len(fail), "resolve_rate": round(sum(r["resolved"] for r in fail) / len(fail), 3) if fail else None},
        "all_zero": {"n": len(ok), "resolve_rate": round(sum(r["resolved"] for r in ok) / len(ok), 3) if ok else None}}
    return out


def per_task(rows):
    """Reviewer behaviour per task-round: distinct fork steps among the siblings, and whether siblings at the
    same step share an outcome."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["model"], r["task"], r["round"])].append(r)
    distinct = Counter()
    same_step_pairs = Counter()
    for (m, t, rnd), rs in groups.items():
        steps = Counter((r["base"], r["branch_step"]) for r in rs)
        distinct[(m, len(steps))] += 1
        for key, n in steps.items():
            if n > 1:
                sib = [r for r in rs if (r["base"], r["branch_step"]) == key]
                outcomes = {r["resolved"] for r in sib}
                same_step_pairs[(m, "mixed" if len(outcomes) > 1 else ("all_resolved" if sib[0]["resolved"] else "all_unresolved"))] += 1
    out = {}
    for m in sorted({k[0] for k in distinct}):
        out[m] = {"distinct_fork_points_per_round": {str(k[1]): v for k, v in sorted(distinct.items()) if k[0] == m},
                  "same_step_sibling_groups": {k[1]: v for k, v in same_step_pairs.items() if k[0] == m}}
    return out


def md_table(stats, models):
    lines = ["| model | split | n | position median (q1–q3) | steps left in base median | continuation turns median (q1–q3, p90) | "
             "reviewer cmds median | text chars median | cmd nonzero-exit share |", "|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        for sp in ("resolved", "unresolved"):
            b = stats[m]["rounds"]["all"][sp]
            if not b["n"]:
                continue
            pos, left, ct = b["position"], b["steps_left_in_base"], b["continuation_actor_turns"]
            lines.append(f"| {m} | {sp} | {b['n']} | {pos['median']:.2f} ({pos['q1']:.2f}–{pos['q3']:.2f}) | {left['median']:.0f} | "
                         f"{ct['median']:.0f} ({ct['q1']:.0f}–{ct['q3']:.0f}, {ct['p90']:.0f}) | {b['reviewer_commands']['median']:.0f} | "
                         f"{b['reviewer_text_chars']['median']:.0f} | {b['reviewer_cmd_nonzero_exit_share']:.2f} |")
    return "\n".join(lines)


def main() -> None:
    root = Path(sys.argv[1])
    rows = [json.loads(l) for l in (root / "branches.jsonl").open()]
    models = ["luna", "sonnet5", "kimi-k3"]
    stats = {}
    for m in models + ["all"]:
        rs = rows if m == "all" else [r for r in rows if r["model"] == m]
        stats[m] = {"rounds": {"all": block(rs), "round1": block([r for r in rs if r["round"] == 1]),
                               "round2": block([r for r in rs if r["round"] == 2])},
                    "round2_by_base": {"root": block([r for r in rs if r["round"] == 2 and r["base"] == "root"]),
                                       "branch": block([r for r in rs if r["round"] == 2 and r["base"] != "root"])}}
    stats["per_task"] = per_task(rows)
    # tasks: resolved in round 1 / round 2 / never, per model
    tasks = defaultdict(lambda: defaultdict(set))
    for r in rows:
        tasks[r["model"]][r["task"]].add((r["round"], r["resolved"]))
    outcome = {}
    for m in models:
        c = Counter()
        for t, s in tasks[m].items():
            if (1, True) in s:
                c["round1"] += 1
            elif (2, True) in s:
                c["round2"] += 1
            else:
                c["never"] += 1
        outcome[m] = dict(c)
    stats["task_outcome"] = outcome
    (root / "stats.json").write_text(json.dumps(stats, indent=1) + "\n")

    md = ["# Branch-turn statistics (fixed 4+3, official verdicts)", "",
          f"{len(rows)} branches: " + ", ".join(f"{m} {sum(1 for r in rows if r['model'] == m)}" for m in models), "",
          "Position = absolute fork step / total tool steps of the history it forks from (the root; for a round-2 branch off a "
          "round-1 branch, the root prefix + that branch's own steps). within-base-own = where in the round-1 branch's own steps "
          "a round-2 branch forks. "
          "Continuation turns = actor model calls after the reviewer-authored turn.", "",
          "## Resolved vs unresolved branches, all rounds", "", md_table(stats, models), "",
          "## Resolve rate by fork position", ""]
    md.append("| model | " + " | ".join(stats["all"]["rounds"]["all"]["by_position_bucket"]) + " |")
    md.append("|---|" + "---|" * len(BUCKETS))
    for m in models + ["all"]:
        b = stats[m]["rounds"]["all"]["by_position_bucket"]
        md.append(f"| {m} | " + " | ".join(f"{v['resolved']}/{v['n']} ({v['rate']:.2f})" if v["n"] else "–" for v in b.values()) + " |")
    md += ["", "## Resolve rate by continuation length (actor turns)", ""]
    keys = list(stats["all"]["rounds"]["all"]["by_continuation_turns"])
    md.append("| model | " + " | ".join(keys) + " |")
    md.append("|---|" + "---|" * len(keys))
    for m in models + ["all"]:
        b = stats[m]["rounds"]["all"]["by_continuation_turns"]
        md.append(f"| {m} | " + " | ".join(f"{v['resolved']}/{v['n']} ({v['rate']:.2f})" if v["n"] else "–" for v in b.values()) + " |")
    md += ["", "## Rounds", ""]
    md.append("| model | round | branches | resolved | rate | position median | within-base-own median | continuation turns median | round-2 bases: root / branch |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for m in models:
        for rnd in ("round1", "round2"):
            b = stats[m]["rounds"][rnd]
            if not b["all"]["n"]:
                continue
            r2 = stats[m]["round2_by_base"]
            bases = (f"{r2['root']['all']['n']} / {r2['branch']['all']['n']} "
                     f"(rates {r2['root']['resolve_rate']} / {r2['branch']['resolve_rate']})") if rnd == "round2" else ""
            own = b["all"]["position_within_base_own"]
            md.append(f"| {m} | {rnd[-1]} | {b['all']['n']} | {b['resolved']['n']} | {b['resolve_rate']:.2f} | "
                      f"{b['all']['position']['median']:.2f} | {own['median'] if own['n'] else '–'} | "
                      f"{b['all']['continuation_actor_turns']['median']:.0f} | {bases} |")
    md += ["", "## Reviewer command exit status vs outcome", ""]
    md.append("| model | all commands exit 0: n (rate) | some command non-zero: n (rate) |")
    md.append("|---|---|---|")
    for m in models + ["all"]:
        e = stats[m]["rounds"]["all"]["reviewer_command_exit"]
        md.append(f"| {m} | {e['all_zero']['n']} ({e['all_zero']['resolve_rate']}) | {e['nonzero']['n']} ({e['nonzero']['resolve_rate']}) |")
    md += ["", "## Reviewer fork-point diversity per task-round and task outcomes", "",
           "```", json.dumps(stats["per_task"], indent=1), json.dumps(stats["task_outcome"], indent=1), "```"]
    (root / "stats.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
