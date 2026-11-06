#!/usr/bin/env python3
"""Positive-task coverage and positive-trajectory yield on failed baselines."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


ORDER = [
    "sprout-b1", "sprout-b2", "sprout-b4", "sprout-b8", "sprout-b16", "sprout-b32",
    "sprout-r2-b1", "sprout-r2-b2", "sprout-r4-b1",
    "sprout-r2-b4", "sprout-r4-b2", "sprout-r8-b1",
]
BLUE, ORANGE = "#356A95", "#D47C4C"
ACCEPTED_VERDICTS = {"not_flagged", "holds_without_test_edits", "task_requested_test_update"}


def read(path):
    return json.loads(Path(path).read_text())


def root_context(root):
    sources = read(root / "accepted-sources.json")
    baseline = {
        task: read(root / "accepted/baseline/tasks" / task / "baseline.task.json")
        for task in sources["baseline"]
    }
    if len(baseline) != 113 or any(type(row["initial_resolved"]) is not bool for row in baseline.values()):
        raise ValueError("Incomplete baseline cohort")
    failed = {task for task, row in baseline.items() if not row["initial_resolved"]}
    if len(failed) != 61:
        raise ValueError("Expected the shared 61 initially failed tasks")
    audit = read(root / "test-edit-audit/audit.json")
    checked = {str(Path(row["trial"]).resolve()) for row in audit["checked"]}
    flagged = {str(Path(row["trial"]).resolve()) for row in audit["flagged"]}
    verdicts = {str(Path(row["trial"]).resolve()): row["verdict"]
                for row in read(root / "test-edit-audit/results.json")["cases"]}
    return {"sources": sources, "baseline": baseline, "failed": failed,
            "checked": checked, "flagged": flagged, "verdicts": verdicts}


def measure(stage, summary, context):
    root = Path(summary["source_root"])
    cohort, failed = set(context["baseline"]), context["failed"]
    source_stage = summary.get("source_stage", stage)
    sampling = summary.get("sampling")
    selections = None
    if sampling:
        manifest = read(sampling["selection_manifest"])
        selections = manifest["selected_by_width"][str(sampling["width"])]
        if set(selections) != failed:
            raise ValueError("Sampling manifest covers a different failed-task cohort")
    if set(context["sources"][source_stage]) != cohort:
        raise ValueError(f"Incomplete setting: {stage}")
    tasks, trials = [], set()
    for task in sorted(cohort):
        state = read(root / "accepted" / source_stage / "tasks" / task / "sprout.task.json")
        if not state["complete"] or state["initial_resolved"] is not (task not in failed):
            raise ValueError(f"Baseline cohort membership changed: {stage}/{task}")
        method = state["methods"]["sprout"]
        attempts = method["attempts"]
        if task not in failed:
            if attempts or method["status"] != "skipped_initial_success":
                raise ValueError("An initially successful task generated new branches")
            continue
        if not attempts or method["status"] != "complete":
            raise ValueError(f"Incomplete failed-parent evaluation: {stage}/{task}")
        if selections is not None:
            selected = selections[task]
            if len(selected) != sampling["width"] or len(set(selected)) != len(selected):
                raise ValueError("Invalid sampled branch count")
            selected_names = set(selected)
            attempts = [attempt for attempt in attempts if attempt["name"] in selected_names]
            if {attempt["name"] for attempt in attempts} != selected_names:
                raise ValueError("Sample names a branch outside the accepted population")
        official_positive, audited_positive, rejected = [], [], []
        for row in attempts:
            if row["round"] < 1 or row["status"] not in ("completed", "timeout") or type(row["resolved"]) is not bool:
                raise ValueError("Incomplete branch outcome")
            trial = str(Path(row["journal"]).resolve().parent.parent)
            if trial in trials:
                raise ValueError("Duplicate branch trial within a setting")
            trials.add(trial)
            if not row["resolved"]:
                continue
            official_positive.append(trial)
            verdict = context["verdicts"].get(
                trial, "not_flagged" if trial in context["checked"] and trial not in context["flagged"]
                else "not_audited")
            if verdict in ACCEPTED_VERDICTS:
                audited_positive.append(trial)
            elif verdict == "depends_on_test_edits":
                rejected.append(trial)
            else:
                raise ValueError(f"Unfinished positive-trial audit: {stage}/{task}/{verdict}")
        tasks.append({
            "task": task, "new_branches": len(attempts),
            "official_positive_branches": len(official_positive),
            "audited_positive_branches": len(audited_positive),
            "official_has_positive": bool(official_positive),
            "audited_has_positive": bool(audited_positive),
            "audited_positive_trials": audited_positive, "test_edit_dependent_trials": rejected,
        })
    rescued = sum(row["audited_has_positive"] for row in tasks)
    official_rescued = sum(row["official_has_positive"] for row in tasks)
    positives = sum(row["audited_positive_branches"] for row in tasks)
    official_positives = sum(row["official_positive_branches"] for row in tasks)
    total = sum(row["new_branches"] for row in tasks)
    baseline_successes = len(cohort) - len(failed)
    if rescued + baseline_successes != summary["audited_resolved"]:
        raise ValueError(f"Per-task audit does not reconcile with the final report: {stage}")
    if official_rescued + baseline_successes != summary["official_resolved"]:
        raise ValueError(f"Official per-task outcomes do not reconcile: {stage}")
    return {
        "stage": stage, "label": summary["label"], "initial_failed_tasks": len(failed),
        "official_rescued_tasks": official_rescued, "audited_rescued_tasks": rescued,
        "official_task_recovery_rate": official_rescued / len(failed),
        "audited_task_recovery_rate": rescued / len(failed),
        "new_branches": total, "official_positive_branches": official_positives,
        "audited_positive_branches": positives,
        "official_branch_positive_rate": official_positives / total,
        "audited_branch_positive_rate": positives / total,
        "source_root": str(root), "source_stage": source_stage,
        "sampling": sampling, "tasks": tasks,
    }


def plot(rows, field, ylabel, output):
    positions, colors = [], []
    position, previous = 0, None
    for row in rows:
        group = "multi" if row["stage"].startswith("sprout-r") else "single"
        if previous is not None:
            position += 1 + (.65 if group != previous else 0)
        positions.append(position)
        colors.append(ORANGE if group == "multi" else BLUE)
        previous = group
    fig, axis = plt.subplots(figsize=(5.5, 3.1))
    fig.subplots_adjust(left=.12, right=.99, bottom=.19, top=.86)
    values = [100 * row[field] for row in rows]
    bars = axis.bar(positions, values, width=.7, color=colors, linewidth=0, zorder=3)
    labels = axis.bar_label(bars, labels=[f"{value:.1f}" for value in values],
                           fontsize=7.5 if len(rows) > 9 else 8, padding=3, color="#30343B")
    axis.set(xlim=(-.65, positions[-1] + .65), ylim=(0, 100),
             xlabel="Rounds × branches per round", ylabel=ylabel)
    axis.set_xticks(positions, [row["label"] for row in rows])
    axis.set_yticks([0, 20, 40, 60, 80, 100])
    axis.grid(axis="y", color="#E6E8EC", linewidth=.55)
    axis.set_axisbelow(True)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_linewidth(.65)
    axis.tick_params(axis="x", length=0, pad=6)
    axis.tick_params(axis="y", length=2.5, width=.65, pad=3)
    axis.xaxis.labelpad = axis.yaxis.labelpad = 7
    legend = axis.legend(
        handles=[Patch(facecolor=BLUE, label="Single round"),
                 Patch(facecolor=ORANGE, label="Multiple rounds")],
        loc="lower center", bbox_to_anchor=(.5, 1.015), ncol=2, frameon=False,
        fontsize=8.5, handlelength=1.2, handleheight=.8, columnspacing=2.2, borderaxespad=0,
    )
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for item in [axis.xaxis.label, axis.yaxis.label, *axis.get_xticklabels(),
                 *axis.get_yticklabels(), *labels, *legend.get_texts()]:
        box = item.get_window_extent(renderer)
        if (box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width + 1
                or box.y1 > fig.bbox.height + 1):
            raise ValueError(f"Label outside canvas: {item.get_text()}")
    for ext in ("pdf", "svg", "png"):
        fig.savefig(output.with_suffix(f".{ext}"), dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    source = args.data.resolve()
    data = read(source)
    source_hashes = dict(data["source_sha256"])
    for name, expected in source_hashes.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source experiment result changed: {name}")
    summaries = {row["stage"]: row for row in data["stages"]}
    order = [stage for stage in ORDER if stage in summaries]
    if set(summaries) - {"baseline"} != set(order):
        raise ValueError("Unexpected branching settings")
    contexts = {}
    for name in {summaries[stage]["source_root"] for stage in order}:
        root = Path(name)
        contexts[name] = root_context(root)
        for filename in ("accepted-sources.json", "test-edit-audit/audit.json",
                         "test-edit-audit/results.json"):
            path = root / filename
            source_hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    failed = next(iter(contexts.values()))["failed"]
    if any(context["failed"] != failed for context in contexts.values()):
        raise ValueError("Experiments have different initially failed cohorts")
    rows = [measure(stage, summaries[stage], contexts[summaries[stage]["source_root"]]) for stage in order]
    output = (args.output_dir or source.parent / "paper").resolve()
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "font.size": 8.5, "axes.labelsize": 9.5, "xtick.labelsize": 8, "ytick.labelsize": 8.5,
        "text.color": "#30343B", "axes.labelcolor": "#30343B", "axes.edgecolor": "#7B8188",
        "xtick.color": "#535A63", "ytick.color": "#535A63",
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none", "savefig.facecolor": "white",
    })
    plot(rows, "audited_task_recovery_rate", "Initial-failure recovery (%)",
         output / "initial-failed-task-recovery")
    plot(rows, "audited_branch_positive_rate", "Positive branch samples (%)",
         output / "initial-failed-branch-yield")
    result = {
        "model": data["model"], "total_tasks": 113, "baseline_resolved": 52,
        "initial_failed_tasks": sorted(failed),
        "task_metric": "initially failed tasks with at least one audited positive branch / 61",
        "branch_metric": "audited positive new branch trajectories / actual new branch trajectories",
        "scope": "Accepted complete evaluations only; initially successful tasks and infrastructure retries excluded.",
        "note": "Multiple positive branches for one task count once for task recovery and separately for branch yield. "
                "Multi-round evaluations stop after a successful round; branch yields reflect this stopping policy.",
        "source_sha256": source_hashes,
        "single_round_sampling": data.get("single_round_sampling"),
        "plot_program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "stages": rows,
    }
    (output / "initial-failure-yield.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    compact = [{key: value for key, value in row.items() if key != "tasks"} for row in rows]
    with (output / "initial-failure-yield.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(compact[0]))
        writer.writeheader()
        writer.writerows(compact)
    lines = [
        "# Positive yield from initially failed tasks", "",
        "61 initially failed tasks; the 52 successful baseline tasks are excluded. "
        "Both metrics use test-edit-audited positives.", "",
        "| Setting | Tasks with ≥1 positive | Task recovery | Positive branches | Branch yield |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['audited_rescued_tasks']}/61 | "
            f"{row['audited_task_recovery_rate']:.2%} | "
            f"{row['audited_positive_branches']}/{row['new_branches']} | "
            f"{row['audited_branch_positive_rate']:.2%} |")
    lines += ["", result["scope"], result["note"], ""]
    if data.get("single_round_sampling"):
        lines += ["Single-round settings are one nested subsample per task from the accepted 1×32 pool "
                  f"(seed {data['single_round_sampling']['seed']}); they are not new independently planned runs.", ""]
    (output / "initial-failure-yield.md").write_text("\n".join(lines))
    print(json.dumps({"initial_failed_tasks": len(failed), "stages": compact}, indent=2))


if __name__ == "__main__":
    main()
