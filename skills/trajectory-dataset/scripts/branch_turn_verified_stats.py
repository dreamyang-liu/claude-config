#!/usr/bin/env python3
"""Reproducible statistics behind the branch-turn report: the checks the verification pass found to hold,
recomputed from branches.jsonl / continuations.jsonl / classifications.json (read-only), plus the per-branch
listing tables. Pure python (Mann-Whitney U with normal approximation, Fisher exact via hypergeometric).

Run: python3 .claude/skills/trajectory-dataset/scripts/branch_turn_verified_stats.py \\
         ~/sprout-runs/qwen/analysis/fixed43-branch-turns-20261008
Writes verified-stats.md, verified-stats.json and branch-list-<model>.md / branch-list.csv.
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

MODELS = ["luna", "sonnet5", "kimi-k3"]


def mwu(a, b):
    """Two-sided Mann-Whitney U, normal approximation with tie correction. Returns (U, p, median a, median b)."""
    n1, n2 = len(a), len(b)
    if not n1 or not n2:
        return None
    allv = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    ranks, i = [0.0] * len(allv), 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = r
        i = j + 1
    r1 = sum(r for r, (v, g) in zip(ranks, allv) if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    ties = Counter(v for v, _ in allv)
    n = n1 + n2
    tie_term = sum(t ** 3 - t for t in ties.values()) / (n * (n - 1)) if n > 1 else 0
    sigma = math.sqrt(n1 * n2 / 12 * ((n + 1) - tie_term))
    if sigma == 0:
        return {"U": u1, "p": 1.0, "median_a": statistics.median(a), "median_b": statistics.median(b)}
    z = (u1 - mu) / sigma
    p = math.erfc(abs(z) / math.sqrt(2))
    return {"U": u1, "z": round(z, 3), "p": round(p, 4), "median_a": statistics.median(a), "median_b": statistics.median(b), "n_a": n1, "n_b": n2}


def fisher(a, b, c, d):
    """Two-sided Fisher exact p for [[a, b], [c, d]] (sum of probabilities <= observed)."""
    n = a + b + c + d
    r1, c1 = a + b, a + c

    def pmf(x):
        return math.comb(c1, x) * math.comb(n - c1, r1 - x) / math.comb(n, r1)
    p_obs = pmf(a)
    lo, hi = max(0, r1 - (n - c1)), min(r1, c1)
    return round(sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= p_obs + 1e-12), 4)


def spearman(x, y):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    return round(cov / math.sqrt(vx * vy), 3) if vx and vy else None


def rate(rs):
    return f"{sum(r['resolved'] for r in rs)}/{len(rs)} ({sum(r['resolved'] for r in rs) / len(rs):.2f})" if rs else "–"


def main() -> None:
    root = Path(sys.argv[1])
    rows = [json.loads(l) for l in (root / "branches.jsonl").open()]
    labels = {it["id"]: it for it in json.loads((root / "classifications.json").read_text())} if (root / "classifications.json").exists() else {}
    by_model = {m: [r for r in rows if r["model"] == m] for m in MODELS}
    out, md = {}, ["# Verified statistics (recomputed from the journals)", ""]

    # 1. fork position by outcome, round 1 only and all rounds
    md += ["## 1. Fork position, resolved vs unresolved (Mann-Whitney U, two-sided)", "",
           "| model | rounds | n res / unres | position median res / unres | p | steps-left median res / unres | p |", "|---|---|---|---|---|---|---|"]
    out["position_tests"] = {}
    for m in MODELS:
        for rnd_label, rs in (("round 1", [r for r in by_model[m] if r["round"] == 1]), ("all", by_model[m])):
            res, unr = [r for r in rs if r["resolved"]], [r for r in rs if not r["resolved"]]
            t1 = mwu([r["position"] for r in res], [r["position"] for r in unr])
            t2 = mwu([r["base_total_steps"] - r["fork_step_absolute"] for r in res], [r["base_total_steps"] - r["fork_step_absolute"] for r in unr])
            out["position_tests"][f"{m}/{rnd_label}"] = {"position": t1, "steps_left": t2}
            md.append(f"| {m} | {rnd_label} | {len(res)} / {len(unr)} | {t1['median_a']:.2f} / {t1['median_b']:.2f} | {t1['p']} | "
                      f"{t2['median_a']:.0f} / {t2['median_b']:.0f} | {t2['p']} |")
    # Luna 0.75-0.90 trough
    lu = by_model["luna"]
    trough = [r for r in lu if 0.75 <= r["position"] < 0.9]
    rest = [r for r in lu if r["position"] >= 0.9]
    p = fisher(sum(r["resolved"] for r in trough), len(trough) - sum(r["resolved"] for r in trough),
               sum(r["resolved"] for r in rest), len(rest) - sum(r["resolved"] for r in rest))
    md += ["", f"Luna 0.75–0.90 band: {rate(trough)} vs 0.90–1.00: {rate(rest)}, Fisher p = {p}."]
    out["luna_trough"] = {"band": rate(trough), "tail": rate(rest), "p": p}
    # Kimi: forking at the very last step vs 2-10 steps earlier
    ki = by_model["kimi-k3"]
    last = [r for r in ki if r["base_total_steps"] - r["fork_step_absolute"] <= 1]
    mid = [r for r in ki if 2 <= r["base_total_steps"] - r["fork_step_absolute"] <= 10]
    md.append(f"Kimi: fork with ≤1 step left: {rate(last)} vs 2–10 steps left: {rate(mid)}, Fisher p = "
              f"{fisher(sum(r['resolved'] for r in last), len(last) - sum(r['resolved'] for r in last), sum(r['resolved'] for r in mid), len(mid) - sum(r['resolved'] for r in mid))}.")
    so = by_model["sonnet5"]
    early = [r for r in so if r["position"] < 0.25]
    md.append(f"Sonnet 5: forks before 0.25: {rate(early)}; 0.90–1.00: {rate([r for r in so if r['position'] >= 0.9])}.")

    # 2. within-task discordant sibling pairs: does the later fork win?
    md += ["", "## 2. Within a task-round, when two siblings disagree in outcome, which forked later?", ""]
    out["discordant_pairs"] = {}
    for m in MODELS + ["all"]:
        later_wins = earlier_wins = same = 0
        groups = defaultdict(list)
        for r in (rows if m == "all" else by_model[m]):
            groups[(r["model"], r["task"], r["round"])].append(r)
        for rs in groups.values():
            for i in range(len(rs)):
                for j in range(i + 1, len(rs)):
                    a, b = rs[i], rs[j]
                    if a["resolved"] == b["resolved"] or a["base"] != b["base"]:
                        continue
                    win, lose = (a, b) if a["resolved"] else (b, a)
                    if win["fork_step_absolute"] > lose["fork_step_absolute"]:
                        later_wins += 1
                    elif win["fork_step_absolute"] < lose["fork_step_absolute"]:
                        earlier_wins += 1
                    else:
                        same += 1
        n = later_wins + earlier_wins
        pb = round(sum(math.comb(n, k) for k in range(max(later_wins, earlier_wins), n + 1)) / 2 ** n * 2, 4) if n else None
        out["discordant_pairs"][m] = {"later_wins": later_wins, "earlier_wins": earlier_wins, "same_step": same, "binomial_p": pb}
        md.append(f"- {m}: later fork wins {later_wins}, earlier fork wins {earlier_wins}, same step {same} (sign-test p = {pb})")

    # 3. continuation length vs steps left
    md += ["", "## 3. Continuation length (actor turns) vs steps left in the base at the fork", ""]
    out["continuation"] = {}
    for m in MODELS:
        rs = [r for r in by_model[m] if r["round"] == 1]
        left = [r["base_total_steps"] - r["fork_step_absolute"] for r in rs]
        calls = [r["continuation_model_calls"] for r in rs]
        rho = spearman(left, calls)
        ratio = [c / max(1, l) for c, l in zip(calls, left)]
        q = sorted(ratio)
        floor = [r["continuation_model_calls"] for r in rs if r["base_total_steps"] - r["fork_step_absolute"] <= 1]
        out["continuation"][m] = {"spearman_steps_left_vs_calls": rho, "ratio_p10": q[len(q) // 10], "ratio_median": statistics.median(ratio), "ratio_p90": q[9 * len(q) // 10],
                                  "calls_when_le1_step_left_median": statistics.median(floor) if floor else None, "n_le1": len(floor)}
        md.append(f"- {m} (round 1, n={len(rs)}): Spearman(steps left, actor turns) = {rho}; turns / steps-left ratio p10–median–p90 = "
                  f"{q[len(q) // 10]:.1f} / {statistics.median(ratio):.1f} / {q[9 * len(q) // 10]:.1f}; when ≤1 step was left the actor still ran a median of "
                  f"{statistics.median(floor) if floor else '–'} turns (n={len(floor)})")

    # 4. reviewer edits / commits / nonzero exits, within solvable task-rounds
    W = re.compile(r"cat\s*<<\s*['\"]?\w+['\"]?\s*>\s*\S+|cat\s*>\s*\S+\s*<<|\bsed\s+-i|perl -p?i|write_text\(|\.write\(|open\([^)]*['\"]w|\breplace\(|re\.sub\(|git apply|patch -p|>\s*[\w./-]+\.(py|ts|js|go|rs|tsx|jsx|toml|yaml|yml|json|md|cfg|ini|txt)\b")
    C = re.compile(r"git commit|COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT|MINI_SWE_AGENT_FINAL_OUTPUT")

    def cmds(r):
        return "\n".join(c["command"] or "" for c in r["turn"]["commands"])
    solvable = set()
    groups = defaultdict(list)
    for r in rows:
        groups[(r["model"], r["task"], r["round"])].append(r)
    for k, rs in groups.items():
        if any(r["resolved"] for r in rs):
            solvable.add(k)
    md += ["", "## 4. Reviewer-turn features vs outcome, all branches and within solvable task-rounds (≥1 sibling resolved)", "",
           "| model | feature | all: with / without | solvable rounds: with / without | Fisher p (solvable) |", "|---|---|---|---|---|"]
    out["features"] = {}
    for m in MODELS:
        for name, pred in (("writes a file", lambda r: bool(W.search(cmds(r)))), ("commits/submits in turn", lambda r: bool(C.search(cmds(r)))),
                           ("some command non-zero exit", lambda r: any((x.get("exit_code") or 0) != 0 for x in r["reviewer_results"]))):
            rs = by_model[m]
            w, wo = [r for r in rs if pred(r)], [r for r in rs if not pred(r)]
            sv = [r for r in rs if (m, r["task"], r["round"]) in solvable]
            sw, swo = [r for r in sv if pred(r)], [r for r in sv if not pred(r)]
            p = fisher(sum(r["resolved"] for r in sw), len(sw) - sum(r["resolved"] for r in sw), sum(r["resolved"] for r in swo), len(swo) - sum(r["resolved"] for r in swo)) if sw and swo else None
            out["features"][f"{m}/{name}"] = {"all_with": rate(w), "all_without": rate(wo), "solvable_with": rate(sw), "solvable_without": rate(swo), "p": p}
            md.append(f"| {m} | {name} | {rate(w)} / {rate(wo)} | {rate(sw)} / {rate(swo)} | {p} |")
    never = Counter()
    for m in MODELS:
        rs = by_model[m]
        noedit = [r for r in rs if not W.search(cmds(r))]
        never[m] = sum(1 for r in noedit if (m, r["task"], r["round"]) not in solvable)
    md += ["", "No-edit reviewer turns that sit in task-rounds nobody solved: " + ", ".join(f"{m} {never[m]}/{sum(1 for r in by_model[m] if not W.search(cmds(r)))}" for m in MODELS) + "."]

    # 5. actor reverts in the continuation (lexical) vs outcome
    R = re.compile(r"\bgit\s+(checkout|restore|revert|stash)\b")
    md += ["", "## 5. Continuation contains a git checkout/restore/revert/stash (lexical) vs outcome", "", "| model | with revert-type command | without |", "|---|---|---|"]
    out["actor_revert"] = {}
    for m in MODELS:
        w, wo = [], []
        for r in by_model[m]:
            c = json.loads((root / "continuations" / m / f"{r['task']}__{r['unit']}.json").read_text())
            has = any(R.search(cmd) for t in c["continuation"] for cmd in t["commands"])
            (w if has else wo).append(r)
        out["actor_revert"][m] = {"with": rate(w), "without": rate(wo)}
        md.append(f"| {m} | {rate(w)} | {rate(wo)} |")

    # 6. shared tasks
    md += ["", "## 6. Tasks all three models branched on (task mix control)", ""]
    shared = set.intersection(*(set(r["task"] for r in by_model[m]) for m in MODELS))
    out["shared_tasks"] = {"n": len(shared)}
    for m in MODELS:
        rs = [r for r in by_model[m] if r["task"] in shared]
        tasks_resolved = len({r["task"] for r in rs if r["resolved"]})
        out["shared_tasks"][m] = {"branches": rate(rs), "tasks_resolved": tasks_resolved}
        md.append(f"- {m}: branches {rate(rs)}; tasks resolved {tasks_resolved}/{len(shared)}")
    md.append(f"({len(shared)} shared tasks: {', '.join(sorted(shared))})")

    # 7. round 2 as a rescue pass
    md += ["", "## 7. Round 2 (only on tasks where all four round-1 branches failed)", ""]
    out["round2"] = {}
    for m in MODELS:
        t2 = {r["task"] for r in by_model[m] if r["round"] == 2}
        rescued = {r["task"] for r in by_model[m] if r["round"] == 2 and r["resolved"]}
        b_root = [r for r in by_model[m] if r["round"] == 2 and r["base"] == "root"]
        b_br = [r for r in by_model[m] if r["round"] == 2 and r["base"] != "root"]
        out["round2"][m] = {"tasks": len(t2), "rescued": len(rescued), "off_root": rate(b_root), "off_branch": rate(b_br)}
        md.append(f"- {m}: {len(t2)} tasks entered round 2, {len(rescued)} rescued ({len(rescued) / len(t2):.0%}); branches off root {rate(b_root)}, off a round-1 branch {rate(b_br)}")

    # 8. label-based tallies, with the agreement caveat
    if labels:
        md += ["", "## 8. Classifier labels (LLM-assigned, 90-branch re-rating agreement in parentheses) — resolve rate per label value", ""]
        agree = {"fork_intent": 0.91, "hypothesis_specificity": 0.90, "targets_analyst_failure_reason": 0.92, "actor_followthrough": 0.88, "outcome_explanation": 0.88, "observation_outcome": 0.79}
        for f, ag in agree.items():
            md.append(f"**{f}** (agreement {ag})")
            md.append("| value | " + " | ".join(MODELS) + " |")
            md.append("|---|---|---|---|")
            vals = sorted({labels[r["id"]][f] for r in rows if r["id"] in labels})
            for v in vals:
                cells = []
                for m in MODELS:
                    rs = [r for r in by_model[m] if r["id"] in labels and labels[r["id"]][f] == v]
                    cells.append(rate(rs))
                md.append(f"| {v} | " + " | ".join(cells) + " |")
            md.append("")

    (root / "verified-stats.json").write_text(json.dumps(out, indent=1) + "\n")
    (root / "verified-stats.md").write_text("\n".join(md) + "\n")

    # per-branch listing
    fields = ["id", "round", "base", "position", "steps_left", "continuation_turns", "resolved", "audit", "n_cmds", "fork_intent", "actions", "outcome_explanation", "turn_head"]
    with (root / "branch-list.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        for r in rows:
            lb = labels.get(r["id"], {})
            w.writerow([r["id"], r["round"], r["base"], r["position"], r["base_total_steps"] - r["fork_step_absolute"], r["continuation_model_calls"],
                        int(r["resolved"]), r["audit_verdict"], r["turn"]["n_commands"], lb.get("fork_intent"), ",".join(lb.get("actions", [])),
                        lb.get("outcome_explanation"), (r["turn"]["content"] or "").replace("\n", " ")[:300]])
    for m in MODELS:
        lines = [f"# {m}: every SPROUT branch turn (fixed 4+3)", "",
                 "| branch | rnd | base | pos | left | cont. turns | ✓ | cmds | intent | outcome (label) | reviewer text (head) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in by_model[m]:
            lb = labels.get(r["id"], {})
            head = (r["turn"]["content"] or "").replace("\n", " ").replace("|", "\\|")[:160]
            lines.append(f"| {r['task']}/{r['unit']} | {r['round']} | {r['base']} | {r['position']:.2f} | {r['base_total_steps'] - r['fork_step_absolute']} | "
                         f"{r['continuation_model_calls']} | {'✓' if r['resolved'] else '✗'} | {r['turn']['n_commands']} | {lb.get('fork_intent', '')} | "
                         f"{lb.get('outcome_explanation', '')} | {head} |")
        (root / f"branch-list-{m}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
