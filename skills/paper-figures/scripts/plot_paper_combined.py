#!/usr/bin/env python3
"""Compact combined paper figure for branching width and round allocation."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FormatStrFormatter, NullLocator


BLUE = "#356A95"
ORANGE = "#D47C4C"
GREY = "#89939E"
GREEN = "#409586"
PURPLE = "#8E73B0"
RED = "#B5473B"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--passk", type=Path, help="luna-passk-curve.json: independent-sampling Pass@1/2/4/8 "
                        "curve (resolve + token totals) drawn as its own baseline series")
    parser.add_argument("--grade", choices=("official", "audited"), default="official",
                        help="SPROUT resolve rates: official verifier verdicts (default) or test-edit audited")
    args = parser.parse_args()
    passk = json.loads(args.passk.read_text()) if args.passk else None
    source = args.data.resolve()
    data = json.loads(source.read_text())
    for name, expected in data["source_sha256"].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source results changed: {name}")
    rows = {row["stage"]: row for row in data["stages"]}
    expected = set().union(*data["series"].values())
    if set(rows) != expected or len(rows) not in (10, 13):
        raise ValueError("Unexpected comparison data points")
    output = (args.output_dir or source.parent / "paper").resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = output / ("scaling-combined-passk" if passk else "scaling-combined")
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "font.size": 8.3, "axes.labelsize": 9.3,
        "xtick.labelsize": 8.2, "ytick.labelsize": 8.2,
        "text.color": "#344052", "axes.labelcolor": "#344052",
        "axes.edgecolor": "#A4ADB8", "xtick.color": "#657184", "ytick.color": "#657184",
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "savefig.facecolor": "white",
    })
    fig, axis = plt.subplots(figsize=(5.5, 4.0 if passk else 3.45))
    fig.subplots_adjust(left=.115, right=.985, bottom=.285 if passk else .165, top=.975 if passk else .965)
    axis.set_xscale("log")
    axis.set(xlim=(.32, 3.1) if passk else (.36, 2.04), ylim=(38, 98) if passk else (42, 98),
             xlabel="Total tokens (B, log scale)", ylabel="Resolve rate (%)")
    axis.set_xticks([.4, .6, .8, 1.2, 1.6, 2.0, 2.8] if passk else [.4, .6, .8, 1.2, 1.6, 2.0])
    axis.xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    axis.xaxis.set_minor_locator(NullLocator())
    axis.set_yticks([40, 50, 60, 70, 80, 90] if passk else [50, 60, 70, 80, 90])
    axis.grid(axis="y", color="#E3E8EE", linewidth=.45)
    axis.set_axisbelow(True)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_linewidth(.6)
    axis.tick_params(length=2.8, width=.6, pad=3.5)
    axis.xaxis.labelpad = 7
    axis.yaxis.labelpad = 7

    def xy(stage):
        row = rows[stage]
        return row["accepted_total_tokens"] / 1e9, 100 * row[f"{args.grade}_resolve_rate"]

    def points(order):
        return list(zip(*(xy(stage) for stage in order)))

    single = data["series"]["single_round"]
    axis.plot(*points(single[:2]), color=GREY, linewidth=.75,
              linestyle=(0, (1.5, 2.5)), alpha=.7, zorder=2)
    axis.plot(*points(single[1:]), color=BLUE, linewidth=1.6, marker="o", markersize=4.7,
              markeredgecolor="white", markeredgewidth=.7, solid_capstyle="round", zorder=3)
    stage_colors = {}
    multiseries = [
        ("round_allocation", ORANGE, "D", 8),
        ("round_allocation_4", GREEN, "^", 4),
        ("round_allocation_2", PURPLE, "s", 2),
    ]
    handles = [Line2D([], [], color=BLUE, marker="o", markersize=4, linewidth=1.5,
                      label="SPROUT, single round" if passk else "Single round")]
    expanded = "round_allocation_4" in data["series"]
    for key, color, marker, budget in multiseries:
        if key not in data["series"]:
            continue
        rounds = data["series"][key]
        axis.plot(*points(rounds), color=color, linewidth=1.35, linestyle=(0, (3.4, 2.1)),
                  marker=marker, markersize=4.7, markeredgecolor="white", markeredgewidth=.7,
                  markevery=range(len(rounds) - 1), zorder=4)
        stage_colors.update({stage: color for stage in rounds[:-1]})
        handles.append(Line2D(
            [], [], color=color, marker=marker, markersize=4, linewidth=1.4, linestyle="--",
            label=(f"SPROUT, multi-round, budget {budget}" if passk else f"Multi-round, budget {budget}")
            if expanded else "Multiple rounds"))
        # The endpoint is an existing single-round measurement, not another run.
        axis.plot(*xy(rounds[-1]), marker="o", markersize=4.7, color=BLUE,
                  markeredgecolor="white", markeredgewidth=.7, zorder=5)
    if not passk:
        axis.plot(*xy("baseline"), marker="o", markersize=4.7, markerfacecolor="white",
                  markeredgecolor=GREY, markeredgewidth=1, zorder=5)

    offsets = {
        "baseline": (9, 0, "left", "center"),
        "sprout-b1": (7, -9, "left", "top"),
        "sprout-b2": (-11, 4, "right", "center"),
        "sprout-b4": (0, -10, "center", "top"),
        "sprout-b8": (0, -10, "center", "top"),
        "sprout-b16": (0, 9, "center", "bottom"),
        "sprout-b32": (-2, 9, "center", "bottom"),
        "sprout-r8-b1": (-8, 10, "right", "bottom"),
        "sprout-r4-b2": (9, 6, "left", "bottom"),
        "sprout-r2-b4": (10, 0, "left", "center"),
        "sprout-r4-b1": (-11, 4, "right", "bottom"),
        "sprout-r2-b2": (11, -1, "left", "center"),
        "sprout-r2-b1": (-13, 1, "right", "center"),
    }
    labels = []
    if passk:
        rounds_series = [st for st in ("sprout-b1", "sprout-r2-b1", "sprout-r4-b1", "sprout-r8-b1") if st in rows]
        axis.plot(*points(rounds_series), color=RED, linewidth=1.25, linestyle=(0, (5, 1.6, 1, 1.6)),
                  solid_capstyle="round", zorder=3.5)
        handles.append(Line2D([], [], color=RED, linewidth=1.25, linestyle=(0, (5, 1.6, 1, 1.6)),
                              label="SPROUT, rounds scaling, k×1"))
    if passk:
        # Independent sampling: Pass@1, Pass@2, Pass@4, Pass@8 of the base rollouts (own token totals).
        # Pass@1 is the SPROUT root rollout itself (the baseline stage); Pass@2/4/8 come from the
        # independent base attempts.
        bx, by = xy("baseline")
        curve = [{"label": "Pass@1", "tokens_B": bx, "rate": by}] + [pt for pt in passk["points"] if pt["k"] > 1]
        px = [pt["tokens_B"] for pt in curve]
        py = [pt["rate"] for pt in curve]
        axis.plot(px, py, color=GREY, linewidth=1.3, linestyle=(0, (4, 2)), marker="s", markersize=4.4,
                  markerfacecolor="white", markeredgecolor=GREY, markeredgewidth=1.1, zorder=3)
        handles.append(Line2D([], [], color=GREY, marker="s", markersize=4, linewidth=1.3, linestyle="--",
                              markerfacecolor="white", markeredgewidth=1.1, label="Independent sampling, Pass@k"))
        passk_offsets = {"Pass@1": (9, 0, "left", "center"), "Pass@2": (8, -4, "left", "top"),
                         "Pass@4": (0, -9, "center", "top"), "Pass@8": (0, -9, "center", "top")}
        for pt in curve:
            dx, dy, ha, va = passk_offsets[pt["label"]]
            labels.append(axis.annotate(pt["label"], (pt["tokens_B"], pt["rate"]), xytext=(dx, dy),
                                        textcoords="offset points", fontsize=8.3, color=GREY, ha=ha, va=va, zorder=6))
    for stage, row in rows.items():
        if stage == "baseline" and passk:
            continue  # labelled as Pass@1 above
        dx, dy, ha, va = offsets[stage]
        color = stage_colors.get(stage, BLUE)
        if stage == "baseline":
            color = GREY
        text = row["label"]
        if stage == "baseline" and passk:
            text = "SPROUT root"
        labels.append(axis.annotate(
            text, xy(stage), xytext=(dx, dy), textcoords="offset points",
            fontsize=8.3, color=color, ha=ha, va=va,
            fontweight="bold" if stage == "sprout-r8-b1" else "normal",
            arrowprops={"arrowstyle": "-", "color": color, "alpha": .4,
                        "linewidth": .45, "shrinkA": 3, "shrinkB": 4}
            if stage.startswith("sprout-r") or stage == "sprout-b2" else None,
            zorder=6,
        ))
    if passk:
        legend = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.54, .005), ncol=2,
            frameon=False, fontsize=7.2, handlelength=2.0, columnspacing=1.4,
            labelspacing=.55, borderaxespad=.2)
    else:
        legend = axis.legend(handles=handles, loc="lower right", bbox_to_anchor=(.995, .055),
            frameon=False, fontsize=7.7, handlelength=2.1,
            labelspacing=.7, borderaxespad=.35)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    visible_text = [axis.xaxis.label, axis.yaxis.label, *axis.get_xticklabels(),
                    *axis.get_yticklabels(), *labels, *legend.get_texts()]
    for item in visible_text:
        box = item.get_window_extent(renderer)
        if (box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width + 1
                or box.y1 > fig.bbox.height + 1):
            raise ValueError(f"Text extends beyond the figure: {item.get_text()}")
    for ext in ("pdf", "svg", "png"):
        fig.savefig(stem.with_suffix(f".{ext}"), dpi=300)
    plt.close(fig)
    caption = (
        "Branch scaling and round allocation on DeepSWE (113 tasks) with GPT-5.6 LUNA. "
        "Labels denote rounds × branches per round. Resolve rates are "
        + ("official verifier verdicts; " if args.grade == "official" else "test-edit audited; ") +
        "token totals include the shared baseline and actor/analyst/reviewer calls. "
        "Multi-round curves connect configurations with the same maximum number of new branches "
        "and stop after a successful round. Single-round endpoints are shared with the blue curve."
    )
    caption += " The token axis uses a logarithmic scale."
    if passk:
        p2 = next(pt for pt in passk["points"] if pt["k"] == 2)
        caption += (" The grey dashed series is independent sampling: Pass@1 is the SPROUT root rollout itself; "
                    f"Pass@2 (one random pair of the four base attempts, attempts {p2['attempts'][0]} and {p2['attempts'][1]}, seed {passk['seed']}), "
                    "Pass@4 (attempts 1-4) and Pass@8 (attempts 1-8) come from independent base rollouts of a separate cohort, "
                    "with the summed tokens of the attempts used. The red dash-dotted line follows the number of rounds "
                    "at one branch per round (1×1, 2×1, 4×1, 8×1).")
    if data.get("single_round_sampling"):
        caption += (
            f" Single-round points use one nested sample without replacement from each task's "
            f"accepted 1×32 branch pool (seed {data['single_round_sampling']['seed']}). "
            "Their token totals include the selected actors, the shared baseline once, and all recorded "
            "original 32-branch analyst/reviewer usage once. These are post-hoc subsamples, not new 1×k runs.")
    (output / "scaling-combined-caption.md").write_text(caption + "\n")
    latex_caption = caption.replace("×", r"$\times$")
    stem.with_suffix(".tex").write_text(
        "\\begin{figure}[t]\n"
        "  \\centering\n"
        "  \\includegraphics[width=\\linewidth]{scaling-combined.pdf}\n"
        f"  \\caption{{{latex_caption}}}\n"
        "  \\label{fig:branch-scaling}\n"
        "\\end{figure}\n")
    stem.with_suffix(".json").write_text(json.dumps({
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "plot_program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "figure_inches": [5.5, 4.0 if passk else 3.45], "x": "accepted_total_tokens / 1e9", "x_scale": "log",
        "y": f"{args.grade}_resolve_rate * 100", "series": data["series"],
        "stages": data["stages"], "caption": caption,
        "single_round_sampling": data.get("single_round_sampling"),
        "passk": passk,
    }, indent=2, ensure_ascii=False) + "\n")
    print(stem.with_suffix(".svg"))


if __name__ == "__main__":
    main()
