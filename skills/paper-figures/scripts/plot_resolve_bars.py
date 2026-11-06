#!/usr/bin/env python3
"""Audited task resolution by branching setting, as a compact bar chart."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


BLUE, ORANGE, GREY = "#356A95", "#D47C4C", "#89939E"
ORDER = [
    "baseline",
    "sprout-b1", "sprout-b2", "sprout-b4", "sprout-b8", "sprout-b16", "sprout-b32",
    "sprout-r2-b1", "sprout-r2-b2", "sprout-r4-b1",
    "sprout-r2-b4", "sprout-r4-b2", "sprout-r8-b1",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    source = args.data.resolve()
    data = json.loads(source.read_text())
    for name, expected in data["source_sha256"].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Original experiment result changed: {name}")
    rows = {row["stage"]: row for row in data["stages"]}
    order = [stage for stage in ORDER if stage in rows]
    if set(rows) != set(order) or any(row["tasks"] != 113 for row in rows.values()):
        raise ValueError("Unexpected settings or mismatched cohort")
    values = [100 * rows[stage]["audited_resolve_rate"] for stage in order]
    for stage, value in zip(order, values):
        if abs(value - 100 * rows[stage]["audited_resolved"] / 113) > 1e-8:
            raise ValueError(f"Resolution count and rate disagree for {stage}")
    output = (args.output_dir or source.parent / "paper").resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = output / "resolve-rate-settings"
    positions, colors = [], []
    position = 0
    previous = None
    for stage in order:
        group = "baseline" if stage == "baseline" else "multi" if stage.startswith("sprout-r") else "single"
        if previous is not None:
            position += 1 + (.35 if previous == "baseline" else .6 if group != previous else 0)
        positions.append(position)
        colors.append(GREY if group == "baseline" else ORANGE if group == "multi" else BLUE)
        previous = group
    dense = len(order) > 10

    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "font.size": 8.5, "axes.labelsize": 9.5,
        "xtick.labelsize": 7.2 if dense else 8, "ytick.labelsize": 8.5,
        "text.color": "#30343B", "axes.labelcolor": "#30343B",
        "axes.edgecolor": "#7B8188", "xtick.color": "#535A63", "ytick.color": "#535A63",
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "savefig.facecolor": "white",
    })
    fig, axis = plt.subplots(figsize=(5.5, 3.1))
    fig.subplots_adjust(left=.115, right=.99, bottom=.19, top=.86)
    bars = axis.bar(positions, values, width=.7, color=colors, linewidth=0, zorder=3)
    value_labels = axis.bar_label(
        bars, labels=[f"{value:.1f}" for value in values], padding=3,
        fontsize=7.2 if dense else 8, color="#30343B",
    )
    axis.set(
        xlim=(-.73, positions[-1] + .75), ylim=(0, 100),
        xlabel="Rounds × branches per round", ylabel="Resolve rate (%)",
    )
    axis.set_xticks(positions, [rows[stage]["label"] for stage in order])
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
        loc="lower center", bbox_to_anchor=(.52, 1.015), ncol=2, frameon=False,
        fontsize=8.5, handlelength=1.2, handleheight=.8, columnspacing=2.2,
        borderaxespad=0,
    )
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = [axis.xaxis.label, axis.yaxis.label, *axis.get_xticklabels(),
             *axis.get_yticklabels(), *value_labels, *legend.get_texts()]
    for item in texts:
        box = item.get_window_extent(renderer)
        if (box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width + 1
                or box.y1 > fig.bbox.height + 1):
            raise ValueError(f"Text extends beyond the canvas: {item.get_text()}")
    boxes = [item.get_window_extent(renderer) for item in value_labels]
    if any(a.overlaps(b) for i, a in enumerate(boxes) for b in boxes[i + 1:]):
        raise ValueError("Value labels overlap; adjust spacing")
    for extension in ("pdf", "svg", "png"):
        fig.savefig(stem.with_suffix(f".{extension}"), dpi=300)
    plt.close(fig)
    caption = (
        "Test-edit-audited task resolution on DeepSWE (113 tasks) with GPT-5.6 LUNA. "
        "Each bar reports the fraction of the full cohort resolved by that setting, "
        "including the shared baseline successes. Labels denote rounds × branches per round. "
        "Multi-round settings allocate at most eight new branches per task and stop after "
        "a successful round. Values are percentages; this is not the success rate of individual branch rollouts."
    )
    if data.get("single_round_sampling"):
        caption += (
            f" Single-round bars use one nested subsample from each task's accepted 1×32 pool "
            f"(seed {data['single_round_sampling']['seed']}); multi-round bars retain the measured runs.")
    (output / "resolve-rate-settings-caption.md").write_text(caption + "\n")
    stem.with_suffix(".json").write_text(json.dumps({
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "plot_program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "figure_inches": [5.5, 3.1],
        "metric": "audited_resolved / 113", "denominator": 113, "baseline_successes_included": True,
        "y_min": 0, "stages": [rows[stage] for stage in order], "caption": caption,
        "single_round_sampling": data.get("single_round_sampling"),
    }, indent=2, ensure_ascii=False) + "\n")
    print(stem.with_suffix(".svg"))


if __name__ == "__main__":
    main()
