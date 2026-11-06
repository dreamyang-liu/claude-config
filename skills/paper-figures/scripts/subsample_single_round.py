#!/usr/bin/env python3
"""One seeded, nested sample of each task's accepted 32-branch population.

Figure renderers (--render) run under ~/sprout-runs/qwen/plots-env/bin/python (the repo .venv
has no matplotlib; override with SPROUT_PLOT_PYTHON). This script itself is standard library.
"""

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess


WIDTHS = (1, 2, 4, 8, 16, 32)
PLOT_PYTHON = os.environ.get("SPROUT_PLOT_PYTHON") or str(Path.home() / "sprout-runs/qwen/plots-env/bin/python")
ALLOWED_AUDITS = {"not_flagged", "holds_without_test_edits", "task_requested_test_update"}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def draw_nested(populations, seed, widths=WIDTHS):
    """Uniform subsets from one permutation per task, without replacement."""
    if not widths or any(type(width) is not int or width <= 0 for width in widths):
        raise ValueError("Widths must be positive integers")
    if len(set(widths)) != len(widths):
        raise ValueError("Widths must be distinct")
    generator = random.Random(seed)
    permutations = {}
    for task in sorted(populations):
        names = list(populations[task])
        if len(names) != len(set(names)) or len(names) != max(widths):
            raise ValueError("Population must contain exactly max(widths) unique branches")
        generator.shuffle(names)
        permutations[task] = names
    return {str(width): {task: names[:width] for task, names in permutations.items()}
            for width in widths}


def call_usage(calls):
    result = {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0,
              "calls": len(calls), "unknown_token_calls": 0}
    for call in calls:
        usage = call["usage"]
        for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
            result[key] += usage.get(key) or 0
        result["unknown_token_calls"] += (
            usage.get("input_tokens") is None or usage.get("output_tokens") is None)
    result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result


def sum_usage(parts):
    fields = ("input_tokens", "output_tokens", "cached_input_tokens", "calls", "unknown_token_calls")
    result = {field: sum(part[field] for part in parts) for field in fields}
    result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result


def build(root, base_source, output, seed):
    if not read(root / "completion-audit.json")["complete"]:
        raise ValueError("The 32-branch experiment has not passed final verification")
    base = read(base_source)
    for filename, expected in base["source_sha256"].items():
        if sha(filename) != expected:
            raise ValueError(f"Comparison source changed: {filename}")
    measured = read(root / "scaling.json")
    reference = next(row for row in measured["stages"] if row["stage"] == "sprout-b32")
    baseline_reference = next(row for row in measured["stages"] if row["stage"] == "baseline")
    audits = read(root / "test-edit-audit/audit.json")
    checked = {str(Path(item["trial"]).resolve()) for item in audits["checked"]}
    flagged = {str(Path(item["trial"]).resolve()) for item in audits["flagged"]}
    verdicts = {str(Path(item["trial"]).resolve()): item["verdict"]
                for item in read(root / "test-edit-audit/results.json")["cases"]}
    audited_reference = next(row for row in read(root / "audit-comparison.json")["stages"]
                             if row["stage"] == "sprout-b32")
    if audited_reference["audit_pending_tasks"] or audited_reference["completed_tasks"] != 113:
        raise ValueError("The population's audit is incomplete")
    metric_file = root / "accepted/sprout-b32/metrics-sprout.json"
    metrics = read(metric_file)["methods"]["sprout"]["tasks"]
    sources = read(root / "accepted-sources.json")["sprout-b32"]
    if len(metrics) != 113 or {row["task"] for row in metrics} != set(sources):
        raise ValueError("Incomplete population metrics")
    baselines, planners, pools, population_names = [], [], {}, {}
    baseline_resolved = 0
    for task_metric in sorted(metrics, key=lambda row: row["task"]):
        task = task_metric["task"]
        baselines.append(call_usage(task_metric["phases"]["initial"]["calls"]))
        state = read(root / "accepted/sprout-b32/tasks" / task / "sprout.task.json")
        if not state["complete"] or state["initial_resolved"] != task_metric["initial_resolved"]:
            raise ValueError("Canonical outcomes and provider metrics disagree")
        if state["initial_resolved"]:
            baseline_resolved += 1
            if state["methods"]["sprout"]["attempts"]:
                raise ValueError("Successful baseline generated extra branches")
            continue
        attempts = state["methods"]["sprout"]["attempts"]
        if len(attempts) != 32 or any(a["round"] != 1 for a in attempts):
            raise ValueError(f"Not a complete single-round 32-branch pool: {task}")
        population_names[task] = [attempt["name"] for attempt in attempts]
        actor_calls = defaultdict(list)
        planner_calls = []
        for call in task_metric["phases"]["additional"]["calls"]:
            if call["role"] in ("actor", "failed_request"):
                actor_calls[str(Path(call["source"]).resolve())].append(call)
            elif call["role"] in ("selector_or_critic", "failed_selector_request"):
                planner_calls.append(call)
            else:
                raise ValueError(f"Unknown token accounting role: {call['role']}")
        planners.append(call_usage(planner_calls))
        journals = {str(Path(a["journal"]).resolve()) for a in attempts}
        if set(actor_calls) - journals:
            raise ValueError("Actor token usage refers to a different rollout")
        pool = []
        for index, attempt in enumerate(attempts, 1):
            journal = str(Path(attempt["journal"]).resolve())
            trial = str(Path(journal).parent.parent)
            positive = attempt["resolved"]
            if type(positive) is not bool or attempt["status"] not in ("completed", "timeout"):
                raise ValueError("Invalid population outcome")
            verdict = "negative"
            audited_positive = False
            if positive:
                verdict = verdicts.get(
                    trial, "not_flagged" if trial in checked and trial not in flagged else "pending")
                if verdict not in ALLOWED_AUDITS | {"depends_on_test_edits"}:
                    raise ValueError(f"Unfinished branch-level audit: {trial}")
                audited_positive = verdict in ALLOWED_AUDITS
            pool.append({
                "name": attempt["name"], "original_index": index, "journal": journal,
                "official_positive": positive, "audited_positive": audited_positive,
                "audit_verdict": verdict, "actor_usage": call_usage(actor_calls[journal]),
            })
        pools[task] = pool
    if baseline_resolved != 52 or len(pools) != 61:
        raise ValueError("Baseline cohort changed")
    baseline_usage, planner_usage = sum_usage(baselines), sum_usage(planners)
    if baseline_usage["total_tokens"] != baseline_reference["accepted_total_tokens"]:
        raise ValueError("Baseline accounting does not match the original figure")
    output.mkdir(parents=True, exist_ok=True)
    selection_file = output / "selection.json"
    if selection_file.exists():
        selection = read(selection_file)
        if (selection["seed"] != seed or selection["populations"] != population_names
                or selection["source_root"] != str(root)):
            raise ValueError("Existing frozen sample has a different seed or population")
        selected = selection["selected_by_width"]
    else:
        # This function sees branch IDs only; neither rewards nor costs affect the draw.
        selected = draw_nested(population_names, seed)
        selection = {
            "seed": seed, "source_root": str(root), "source_stage": "sprout-b32",
            "method": "one permutation per task; nested prefixes without replacement",
            "task_order": sorted(population_names), "widths": list(WIDTHS),
            "populations": population_names, "selected_by_width": selected,
        }
        write(selection_file, selection)
    summaries = []
    for width in WIDTHS:
        official_recovered, audited_recovered = [], []
        official_positive = audited_positive = 0
        actor_parts = []
        for task, pool in pools.items():
            names = selected[str(width)][task]
            if len(names) != width or len(set(names)) != width:
                raise ValueError("Sample has an invalid cardinality")
            lookup = {branch["name"]: branch for branch in pool}
            branches = [lookup[name] for name in names]
            if any(branch["official_positive"] for branch in branches):
                official_recovered.append(task)
            if any(branch["audited_positive"] for branch in branches):
                audited_recovered.append(task)
            official_positive += sum(branch["official_positive"] for branch in branches)
            audited_positive += sum(branch["audited_positive"] for branch in branches)
            actor_parts.extend(branch["actor_usage"] for branch in branches)
        actors = sum_usage(actor_parts)
        total = sum_usage([baseline_usage, planner_usage, actors])
        summaries.append({
            "stage": f"sprout-b{width}", "label": f"1×{width}", "tasks": 113,
            "official_resolved": 52 + len(official_recovered),
            "official_resolve_rate": (52 + len(official_recovered)) / 113,
            "audited_resolved": 52 + len(audited_recovered),
            "audited_resolve_rate": (52 + len(audited_recovered)) / 113,
            "accepted_total_tokens": total["total_tokens"],
            "accepted_input_tokens": total["input_tokens"],
            "accepted_output_tokens": total["output_tokens"],
            "accepted_branch_tokens": planner_usage["total_tokens"] + actors["total_tokens"],
            "tokens_complete": total["unknown_token_calls"] == 0,
            "source_root": str(root), "source_stage": "sprout-b32",
            "sampling": {"seed": seed, "width": width, "selection_manifest": str(selection_file)},
            "series": ["single_round"], "actor_tokens": actors["total_tokens"],
            "planner_tokens": planner_usage["total_tokens"],
            "baseline_tokens": baseline_usage["total_tokens"],
            "selected_branches": len(pools) * width,
            "audited_positive_branches": audited_positive,
            "official_positive_branches": official_positive,
            "audited_recovered_tasks": audited_recovered,
            "official_recovered_tasks": official_recovered,
        })
    full = summaries[-1]
    if (full["audited_resolved"] != audited_reference["audited_resolved"]
            or full["official_resolved"] != reference["resolved"]
            or full["accepted_total_tokens"] != reference["accepted_total_tokens"]
            or full["tokens_complete"] != reference["tokens_complete"]):
        raise ValueError("The k=32 point does not reproduce the original experiment")
    if full["audited_positive_branches"] != 768:
        raise ValueError("The complete audited positive-branch population changed")
    for earlier, later in zip(summaries, summaries[1:]):
        if (earlier["audited_resolved"] > later["audited_resolved"]
                or earlier["accepted_total_tokens"] > later["accepted_total_tokens"]):
            raise ValueError("Nested sample violates monotonicity")
        for task in pools:
            if not set(selected[str(earlier["sampling"]["width"])][task]).issubset(
                    selected[str(later["sampling"]["width"])][task]):
                raise ValueError("Samples are not nested")
    metadata = {
        "seed": seed, "source_stage": "sprout-b32", "source_root": str(root),
        "nested": True, "without_replacement": True, "draws_per_task": 1,
        "widths": list(WIDTHS), "selection_manifest": str(selection_file),
        "cost_rule": "shared baseline once + all recorded original 32-branch planner usage once + selected actor usage",
        "independent_runs": False,
    }
    replace = {row["stage"]: row for row in summaries}
    combined = {**base, "stages": [replace.get(row["stage"], row) for row in base["stages"]],
                "single_round_sampling": metadata}
    for path in (metric_file, selection_file, root / "accepted-sources.json",
                 root / "test-edit-audit/audit.json", root / "test-edit-audit/results.json"):
        combined["source_sha256"][str(path)] = sha(path)
    write(output / "scaling-and-rounds.json", combined)
    write(output / "sampled-metrics.json", {
        "sampling": metadata, "baseline_usage": baseline_usage, "planner_usage": planner_usage,
        "source_metrics": str(metric_file), "pool": pools, "settings": summaries,
        "k32_reproduces_original": True, "sampler_program_sha256": sha(Path(__file__)),
    })
    table = [
        "# Single-round scaling from one 32-branch pool", "",
        f"One nested sample per initially failed task, seed {seed}. No model or verifier runs were launched.",
        "For each task, one shuffled ordering is reused and the first k branches are retained.", "",
        "| k | Audited resolved | Resolve rate | Failed-task recovery | Positive branches | Tokens (M) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        width = row["sampling"]["width"]
        table.append(
            f"| {width} | {row['audited_resolved']}/113 | {row['audited_resolve_rate']:.2%} | "
            f"{len(row['audited_recovered_tasks'])}/61 | "
            f"{row['audited_positive_branches']}/{row['selected_branches']} | "
            f"{row['accepted_total_tokens']/1e6:.1f} |")
    table += [
        "", "Token accounting includes the selected actors, the shared baseline once, and all recorded "
        "original 32-branch analyst/reviewer usage once. Tokens are attributed to the retained subset; "
        "this is not a measurement of a freshly planned 1×k run.",
        "Provider usage that was absent in the source remains unknown. Recorded totals are lower bounds.",
        "", "Multi-round points retain their original completed experimental results.", "",
    ]
    (output / "README.md").write_text("\n".join(table))
    with (output / "sampled-settings.csv").open("w", newline="") as stream:
        fields = ["stage", "audited_resolved", "audited_resolve_rate", "selected_branches",
                  "audited_positive_branches", "accepted_total_tokens", "actor_tokens", "planner_tokens",
                  "baseline_tokens", "tokens_complete"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summaries)
    return combined, summaries


def plot_single(data, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter, NullLocator
    rows = {row["stage"]: row for row in data["stages"]}
    order = data["series"]["single_round"]
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8.5, "axes.labelsize": 9.3,
        "text.color": "#344052", "axes.labelcolor": "#344052",
        "axes.edgecolor": "#A4ADB8", "xtick.color": "#657184", "ytick.color": "#657184",
        "pdf.fonttype": 42, "svg.fonttype": "none",
    })
    fig, axis = plt.subplots(figsize=(5.5, 2.95))
    fig.subplots_adjust(left=.115, right=.985, bottom=.19, top=.96)
    points = [(rows[stage]["accepted_total_tokens"]/1e9, 100*rows[stage]["audited_resolve_rate"])
              for stage in order]
    axis.plot(*zip(*points[:2]), color="#89939E", linewidth=.75,
              linestyle=(0, (1.5, 2.5)), alpha=.7)
    axis.plot(*zip(*points[1:]), color="#356A95", marker="o", markersize=4.7,
              markeredgecolor="white", markeredgewidth=.7, linewidth=1.6, solid_capstyle="round")
    axis.plot(*points[0], marker="o", markerfacecolor="white",
              markeredgecolor="#89939E", markeredgewidth=1, markersize=4.7)
    offsets = [(9, 0, "left", "center"), (5, -11, "left", "top"),
               (-8, 8, "right", "bottom"), (0, -11, "center", "top"),
               (0, 9, "center", "bottom"), (0, -11, "center", "top"),
               (0, 9, "center", "bottom")]
    for stage, point, (dx, dy, ha, va) in zip(order, points, offsets):
        axis.annotate(rows[stage]["label"], point, xytext=(dx, dy), textcoords="offset points",
                      ha=ha, va=va, fontsize=8.3, color="#89939E" if stage=="baseline" else "#356A95")
    axis.set_xscale("log")
    axis.set(xlim=(.36, 2.04), ylim=(42, 85),
             xlabel="Total tokens (B, log scale)", ylabel="Resolve rate (%)")
    axis.set_xticks([.4,.6,.8,1.2,1.6,2.0])
    axis.xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    axis.xaxis.set_minor_locator(NullLocator())
    axis.set_yticks([50,60,70,80])
    axis.grid(axis="y", color="#E3E8EE", linewidth=.45)
    axis.set_axisbelow(True)
    axis.spines[["top","right"]].set_visible(False)
    axis.spines[["left","bottom"]].set_linewidth(.6)
    axis.tick_params(length=2.8, width=.6, pad=3.5)
    axis.xaxis.labelpad = axis.yaxis.labelpad = 7
    for extension in ("svg","pdf","png"):
        target = output / f"single-turn-scaling.{extension}"
        fig.savefig(target, dpi=300)
        shutil.copy2(target, output / f"single-turn-subsampled.{extension}")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--base-data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    root, source, output = args.root.resolve(), args.base_data.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    original = output / "original-comparison.json"
    if not original.exists():
        shutil.copy2(source, original)
    data, summaries = build(root, original, output, args.seed)
    if args.render:
        paper = output / "paper"
        paper.mkdir(exist_ok=True)
        for name in ("plot_paper_combined.py", "plot_resolve_bars.py", "plot_initial_failure_yield.py"):
            result = subprocess.run(
                [PLOT_PYTHON, str(Path(__file__).with_name(name)), str(output / "scaling-and-rounds.json"),
                 "--output-dir", str(paper)], capture_output=True, text=True)
            (output / f"{name}.log").write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(f"{name} failed: {result.stderr[-1500:]}")
        plot_single(data, paper)
    print((output / "README.md").read_text())


if __name__ == "__main__":
    main()
