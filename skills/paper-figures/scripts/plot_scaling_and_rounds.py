#!/usr/bin/env python3
"""Combine single-round width scaling and multi-round allocation on one axis.

Bootstrap only: builds the first (10-stage) scaling-and-rounds.{json,csv,svg,png} for a brand-new
pair of roots. The published file under deepswe-luna-rounds-20261005/plots has 13 stages
(update_completed_figures.py and subsample_single_round.py added them), so --output-dir is
required and must be a fresh directory, never a root's published plots/.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MultipleLocator


def read(path):
    return json.loads(path.read_text())


def load(root):
    if not read(root / "completion-audit.json")["complete"]:
        raise ValueError(f"Experiment verification is incomplete: {root}")
    data = read(root / "scaling.json")
    audits = {row["stage"]: row for row in read(root / "audit-comparison.json")["stages"]}
    rows = {}
    for row in data["stages"]:
        audit = audits[row["stage"]]
        if (row["completed"] != row["tasks"] or audit["completed_tasks"] != row["tasks"]
                or audit["audit_pending_tasks"] or audit["audited_resolve_rate"] is None
                or audit["official_resolved"] != row["resolved"]):
            raise ValueError(f"Incomplete or inconsistent result: {root}/{row['stage']}")
        rows[row["stage"]] = {
            "stage": row["stage"], "tasks": row["tasks"],
            "official_resolved": row["resolved"], "official_resolve_rate": row["resolve_rate"],
            "audited_resolved": audit["audited_resolved"],
            "audited_resolve_rate": audit["audited_resolve_rate"],
            "accepted_total_tokens": row["accepted_total_tokens"],
            "tokens_complete": row["tokens_complete"], "source_root": str(root),
        }
    return data, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--single-round-root", required=True, type=Path)
    parser.add_argument("--multi-round-root", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="a fresh directory (never a root's published plots/)")
    args = parser.parse_args()
    single_root, multi_root = args.single_round_root.resolve(), args.multi_round_root.resolve()
    single_data, single = load(single_root)
    multi_data, multi = load(multi_root)
    if single_data["model"] != multi_data["model"] or single_data["tasks"] != multi_data["tasks"]:
        raise ValueError("Experiments use different models or cohorts")
    for field in ("accepted_total_tokens", "official_resolved", "audited_resolved"):
        if single["baseline"][field] != multi["baseline"][field]:
            raise ValueError(f"Shared baseline differs in {field}")
    manifests = [read(root / "accepted/baseline/manifest-baseline.json")
                 for root in (single_root, multi_root)]
    for field in ("tasks", "dataset_digest", "model", "reasoning_effort", "max_turns",
                  "max_output_tokens", "command_timeout", "prompt_budget_chars",
                  "review_timeout", "backend", "store", "branch_count_mode"):
        if manifests[0][field] != manifests[1][field]:
            raise ValueError(f"Experiment configurations differ in {field}")
    baseline_root = Path(read(multi_root / "launch-config.json")["baseline_root"]).resolve()
    if baseline_root != (single_root / "accepted/baseline").resolve():
        raise ValueError("Multi-round experiment did not reuse this baseline")

    widths = (1, 2, 4, 8, 16, 32)
    single_order = ["baseline", *(f"sprout-b{width}" for width in widths)]
    round_order = ["sprout-r8-b1", "sprout-r4-b2", "sprout-r2-b4", "sprout-b8"]
    rows = {**single, **{stage: row for stage, row in multi.items() if stage != "baseline"}}
    if set(rows) != set(single_order + round_order):
        raise ValueError("Unexpected experiment stages")
    labels = {"baseline": "Baseline", **{f"sprout-b{width}": f"1×{width}" for width in widths},
              "sprout-r8-b1": "8×1", "sprout-r4-b2": "4×2", "sprout-r2-b4": "2×4"}
    for stage, row in rows.items():
        row["label"] = labels[stage]
        row["accepted_branch_tokens"] = row["accepted_total_tokens"] - single["baseline"]["accepted_total_tokens"]
        row["series"] = (["single_round", "round_allocation"] if stage == "sprout-b8"
                         else ["round_allocation"] if stage in round_order
                         else ["baseline"] if stage == "baseline" else ["single_round"])

    blue, orange, grey = "#167b9c", "#d45d2b", "#64748b"
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11, "svg.fonttype": "none",
        "axes.labelcolor": "#334155", "xtick.color": "#475569", "ytick.color": "#475569",
    })
    fig = plt.figure(figsize=(13.2, 7.6), facecolor="white")
    axis = fig.add_axes([.08, .27, .88, .53])
    axis.set_axisbelow(True)
    axis.grid(color="#e2e8f0", linewidth=.7)
    axis.spines[["top", "right"]].set_visible(False)
    for side in ("bottom", "left"):
        axis.spines[side].set_color("#94a3b8")

    def points(order):
        return ([rows[stage]["accepted_total_tokens"] / 1e6 for stage in order],
                [100 * rows[stage]["audited_resolve_rate"] for stage in order])

    axis.plot(*points(single_order), color=blue, linewidth=2, marker="o", markersize=7,
              markeredgecolor="white", markeredgewidth=1, zorder=2)
    axis.plot(*points(round_order), color=orange, linewidth=2, linestyle=(0, (4, 2)),
              marker="D", markersize=7, markeredgecolor="white", markeredgewidth=1, zorder=3)
    axis.scatter(*points(["baseline"]), color=grey, s=72, marker="s",
                 edgecolors="white", linewidths=1, zorder=4)
    # The same historical 1×8 result is the endpoint of both series.
    axis.scatter(*points(["sprout-b8"]), color=blue, s=24, zorder=5)
    offsets = {
        "baseline": (13, 10, "left", "bottom"),
        "sprout-b1": (16, -26, "left", "top"),
        "sprout-b2": (-20, 23, "right", "bottom"),
        "sprout-b4": (16, 10, "left", "bottom"),
        "sprout-b8": (3, -24, "center", "top"),
        "sprout-b16": (0, 16, "center", "bottom"),
        "sprout-b32": (-5, 18, "center", "bottom"),
        "sprout-r8-b1": (-28, 22, "right", "bottom"),
        "sprout-r4-b2": (20, 16, "left", "bottom"),
        "sprout-r2-b4": (24, 0, "left", "center"),
    }
    for stage, row in rows.items():
        x, y = row["accepted_total_tokens"] / 1e6, row["audited_resolve_rate"] * 100
        label = row["label"] + (" (shared)" if stage == "sprout-b8" else "")
        if not row["tokens_complete"]:
            label += "*"
        dx, dy, ha, va = offsets[stage]
        color = orange if stage in round_order and stage != "sprout-b8" else blue
        if stage in ("baseline", "sprout-b8"):
            color = "#334155"
        axis.annotate(
            f"{label}\n{y:.2f}%", (x, y), xytext=(dx, dy), textcoords="offset points",
            ha=ha, va=va, fontsize=10.5, color=color,
            fontweight="bold" if stage == "sprout-r8-b1" else "normal",
            arrowprops={"arrowstyle": "-", "color": "#94a3b8", "linewidth": .65,
                        "shrinkA": 4, "shrinkB": 6},
            zorder=6,
        )
        if not row["tokens_complete"]:
            axis.annotate("", (x + 95, y), xytext=(x + 7, y),
                          arrowprops={"arrowstyle": "->", "color": blue, "linewidth": 1.4})

    axis.set(xlim=(300, 2040), ylim=(40, 101),
             xlabel="Total input + output tokens (millions)",
             ylabel="Resolve rate after test-edit audit (%)")
    axis.xaxis.set_major_locator(MultipleLocator(200))
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    axis.yaxis.set_major_locator(MultipleLocator(10))
    axis.xaxis.labelpad = axis.yaxis.labelpad = 10
    fig.text(.08, .945, "DeepSWE · GPT-5.6 LUNA · Branch scaling and round allocation",
             fontsize=19, fontweight="bold", color="#0f172a")
    fig.text(.08, .90, "113 tasks · Same reused baseline · Labels = rounds × branches per round",
             fontsize=11, color="#64748b")
    fig.legend(handles=[
        Line2D([], [], color=blue, marker="o", linewidth=2, label="Single round: 1–32 branches"),
        Line2D([], [], color=orange, marker="D", linewidth=2, linestyle="--",
               label="Round allocation: up to 8 new branches"),
        Line2D([], [], color=grey, marker="s", linestyle="none", label="Shared baseline"),
    ], loc="center left", bbox_to_anchor=(.075, .848), ncol=3, frameon=False,
        handlelength=2.4, columnspacing=2.4, fontsize=10.5)
    fig.text(.08, .145,
             "Accepted evaluations: each point includes the baseline once, plus actor/analyst/reviewer calls; input includes cache hits.",
             fontsize=9.5, color="#64748b")
    fig.text(.08, .102,
             "Both series use audited verdicts. Multi-round runs stop after a successful round; 1×8 is one shared historical result.",
             fontsize=9.5, color="#64748b")
    fig.text(.08, .059,
             "* 1×32 token use is a recorded lower bound (≥1,849.8M); the arrow indicates unrecorded usage may increase it.",
             fontsize=9.5, color="#64748b")

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = output / "scaling-and-rounds"
    fig.savefig(stem.with_suffix(".svg"), metadata={
        "Title": "DeepSWE GPT-5.6 LUNA: branch scaling and round allocation",
        "Description": "Single-round widths 1–32 and multi-round schedules 8×1, 4×2, 2×4 on one axis. "
                       "Rates are test-edit audited; token totals count the shared baseline once. "
                       "The 1×32 token total is a lower bound.",
    })
    fig.savefig(stem.with_suffix(".png"), dpi=180)
    plt.close(fig)
    source_files = [root / name for root in (single_root, multi_root)
                    for name in ("scaling.json", "audit-comparison.json", "completion-audit.json")]
    exported = {
        "model": single_data["model"], "tasks": single_data["tasks"], "axes": 1,
        "x": "accepted_total_tokens / 1e6", "y": "audited_resolve_rate * 100",
        "series": {"single_round": single_order, "round_allocation": round_order},
        "stages": list(rows.values()),
        "source_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files},
        "plot_program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    stem.with_suffix(".json").write_text(json.dumps(exported, indent=2, ensure_ascii=False) + "\n")
    with stem.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(next(iter(rows.values()))))
        writer.writeheader()
        writer.writerows(rows.values())
    print(stem.with_suffix(".svg"))


if __name__ == "__main__":
    main()
