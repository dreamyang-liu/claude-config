#!/usr/bin/env python3
"""Scaling figure, linear token axis: SPROUT rounds vs branches vs independent sampling (DeepSWE, Luna).

Reads the verified scaling-and-rounds comparison (SPROUT points) and the Pass@k curve
(independent base rollouts).  Lines, by visual weight:

  solid   SPROUT, k rounds x 1 branch      1x1 -> 2x1 -> 4x1 -> 8x1        (hero)
  dashed  SPROUT, 1 round x k branches     1x1 -> 1x2 -> ... -> 1x32   (long dashes)
  solid   independent sampling              Pass@1 -> Pass@2 -> Pass@4 -> Pass@8 (grey)
  dashed  equal branch budget, split across rounds, one colour per budget:
            8: 8x1 - 4x2 - 2x4 - 1x8      4: 4x1 - 2x2 - 1x4
          (2x1 and 1x2 are not joined: on a linear axis the pair sits under the k x 1 line)
  dashed  horizontal reference at the Pass@8 resolve rate, from the y axis to Pass@8 (grey),
          so every point can be read against it
  star    the configuration the main table reports: 2 rounds, 4 then 3 branches (fixed43.py,
          the Luna root, same reused root rollout as the scaling data)

Pass@1 is the SPROUT root rollout.  No log axis, no shaded band.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import FormatStrFormatter, NullLocator

from fixed43 import FIXED43_ROOTS, FIXED43_STAGE, load_fixed43

INK, MUTED, GRID, SPINE = "#2B3440", "#6B7684", "#E6EAEF", "#AEB6C0"
GREY = "#8A939E"
BLUE = "#3A6EA5"
GREEN = "#1F8A5A"
ORANGE, RED = "#D98B4F", "#B5473B"

ROUNDS = ["sprout-b1", "sprout-r2-b1", "sprout-r4-b1", "sprout-r8-b1"]
SINGLE = ["sprout-b1", "sprout-b2", "sprout-b4", "sprout-b8", "sprout-b16", "sprout-b32"]
# budget -> (stages from all-rounds to single-round, colour, marker for the intermediate points)
BUDGETS = {8: (["sprout-r8-b1", "sprout-r4-b2", "sprout-r2-b4", "sprout-b8"], ORANGE, "D"),
           4: (["sprout-r4-b1", "sprout-r2-b2", "sprout-b4"], RED, "^")}
LEVEL = ("sprout-b32", "Pass@8")
REPORTED_MODEL = "GPT 5.6 Luna"

RC = {
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
    "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": SPINE,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none", "savefig.facecolor": "white",
}

# (dx, dy, ha, va) in points; tuned for the linear axis, where every multi-round point sits
# between 0.43 and 0.75 B tokens.
SPROUT_LABELS = {
    "sprout-b1": (-7, -1, "right", "center"),
    "sprout-r2-b1": (-7, 0, "right", "center"),
    "sprout-r4-b1": (-7, 1, "right", "center"),
    "sprout-r8-b1": (-7, 4, "right", "bottom"),
    "sprout-b2": (7, -4, "left", "top"),
    "sprout-b4": (5, -5, "left", "top"),
    "sprout-b8": (5, -5, "left", "top"),
    "sprout-b16": (0, -8, "center", "top"),
    "sprout-b32": (0, -8, "center", "top"),
    "sprout-r2-b2": (7, -1, "left", "center"),
    "sprout-r4-b2": (7, 2, "left", "bottom"),
    "sprout-r2-b4": (8, 0, "left", "center"),
}
PASSK_LABELS = {"Pass@1": (9, 0, "left", "center"), "Pass@2": (8, -3, "left", "top"),
                "Pass@4": (0, -9, "center", "top"), "Pass@8": (0, -9, "center", "top")}


def passk_curve(rows, passk, grade):
    """[(label, tokens_B, rate)]: Pass@1 is the SPROUT root; Pass@2/4/8 from independent attempts."""
    base = rows["baseline"]
    first = ("Pass@1", base["accepted_total_tokens"] / 1e9, 100 * base[f"{grade}_resolve_rate"])
    return [first] + [(p["label"], p["tokens_B"], p["rate"]) for p in passk["points"] if p["k"] > 1]


def level_wording(rate_sprout, saved):
    return f"{rate_sprout:.1f}%, {100 * saved:.0f}% fewer tokens"


def draw(ax, data, passk, grade="official", level_text=True, reported=None):
    rows = {row["stage"]: row for row in data["stages"]}

    def xy(stage):
        row = rows[stage]
        return row["accepted_total_tokens"] / 1e9, 100 * row[f"{grade}_resolve_rate"]

    def series(stages):
        return np.array([xy(st) for st in stages]).T

    pk = passk_curve(rows, passk, grade)
    pk_x = np.array([p[1] for p in pk])
    pk_y = np.array([p[2] for p in pk])

    ax.set(xlim=(.2, 3.0), ylim=(40, 97))
    ax.set_xlabel("Total tokens (billions)", fontsize=10.5)
    ax.set_ylabel("Resolve rate (%)", fontsize=10.5)
    ax.set_xticks([.5, 1.0, 1.5, 2.0, 2.5])
    ax.xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_yticks([40, 50, 60, 70, 80, 90])
    ax.tick_params(labelsize=9, length=3, width=.6, pad=4)
    ax.grid(axis="y", color=GRID, linewidth=.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_linewidth(.7)

    # Pass@8 reference level first, under everything: horizontal, from the y axis to Pass@8
    lx, ly = xy(LEVEL[0])
    px, py = next((x, y) for label, x, y in pk if label == LEVEL[1])
    x0 = ax.get_xlim()[0]
    ax.plot([x0, px], [py, py], color=GREY, linewidth=1.0, linestyle=(0, (4.0, 3.0)), zorder=2)
    saved = (px - lx) / px
    if level_text:
        ax.annotate(level_wording(ly, saved), (lx, ly), xytext=(9, 2), textcoords="offset points",
                    fontsize=8.2, color=MUTED, ha="left", va="center", zorder=8)

    # independent sampling
    ax.plot(pk_x, pk_y, color=GREY, linewidth=1.5, marker="s", markersize=5.5, markerfacecolor="white",
            markeredgecolor=GREY, markeredgewidth=1.3, solid_capstyle="round", zorder=3)

    # equal-budget groups, dashed, one colour each
    label_colors = {}
    for stages, color, marker in BUDGETS.values():
        bx, by = series(stages)
        ax.plot(bx, by, color=color, linewidth=1.3, linestyle=(0, (3.2, 2.0)), zorder=4)
        inner = stages[1:-1]
        if inner:
            ix, iy = series(inner)
            ax.plot(ix, iy, linestyle="none", marker=marker, markersize=5.2 if marker == "^" else 4.6,
                    color=color, markeredgecolor="white", markeredgewidth=.7, zorder=5)
            label_colors.update({st: color for st in inner})

    # single round, long dashes
    sx, sy = series(SINGLE)
    ax.plot(sx, sy, color=BLUE, linewidth=1.9, linestyle=(0, (5.0, 2.5)), marker="o", markersize=5.4,
            markeredgecolor="white", markeredgewidth=.8, zorder=5)

    # rounds, solid, the hero
    rx, ry = series(ROUNDS)
    ax.plot(rx, ry, color=GREEN, linewidth=2.8, solid_capstyle="round", zorder=6)
    ax.plot(rx, ry, linestyle="none", marker="o", markersize=7.2, color=GREEN,
            markeredgecolor="white", markeredgewidth=1.0, zorder=7)

    # the reported configuration, a star above everything
    if reported is not None:
        rx43, ry43 = reported["tokens_M"] / 1e3, reported["rate"]
        ax.plot(rx43, ry43, linestyle="none", marker="*", markersize=13, color=INK,
                markeredgecolor="white", markeredgewidth=.8, zorder=9)
        ax.annotate("4+3 (reported)", (rx43, ry43), xytext=(12, -11), textcoords="offset points",
                    fontsize=8.8, color=INK, ha="left", va="top", zorder=9,
                    arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": .6, "shrinkA": 1, "shrinkB": 6})

    colors = {st: GREEN for st in ROUNDS}
    colors.update({st: BLUE for st in SINGLE[1:]})
    colors.update(label_colors)
    for stage, (dx, dy, ha, va) in SPROUT_LABELS.items():
        bold = stage in ROUNDS
        ax.annotate(rows[stage]["label"], xy(stage), xytext=(dx, dy), textcoords="offset points",
                    fontsize=9.6 if bold else 8.8, fontweight="bold" if bold else "normal",
                    color=colors[stage], ha=ha, va=va, zorder=8)
    for label, x, y in pk:
        dx, dy, ha, va = PASSK_LABELS[label]
        text = f"{label} ({y:.1f}%)" if label == LEVEL[1] else label
        ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=8.8,
                    color=GREY, ha=ha, va=va, zorder=8)

    def budget_name(k):
        stages = BUDGETS[k][0]
        return f"{k} branches split across rounds ({', '.join(rows[st]['label'] for st in stages)})"

    handles = [
        Line2D([], [], color=GREEN, linewidth=2.8, marker="o", markersize=6.5, markeredgecolor="white",
               label="SPROUT, k rounds × 1 branch"),
        Line2D([], [], color=BLUE, linewidth=1.9, linestyle=(0, (5.0, 2.5)), marker="o", markersize=5,
               markeredgecolor="white", label="SPROUT, 1 round × k branches"),
        Line2D([], [], color=GREY, linewidth=1.5, marker="s", markersize=5, markerfacecolor="white",
               markeredgewidth=1.3, label="Independent sampling, Pass@k"),
        Line2D([], [], color=GREY, linewidth=1.0, linestyle=(0, (4.0, 3.0)), label="Pass@8 resolve rate"),
    ] + ([Line2D([], [], linestyle="none", marker="*", markersize=11, color=INK, markeredgecolor="white",
                 label="SPROUT as reported: 2 rounds, 4 then 3 branches")] if reported is not None else []) + [
        Line2D([], [], color=color, linewidth=1.3, linestyle="--", marker=marker if len(stages) > 2 else None,
               markersize=4.8 if marker == "^" else 4.3, markeredgecolor="white", label=budget_name(k))
        for k, (stages, color, marker) in BUDGETS.items()
    ]
    return handles, {"level": {"sprout": LEVEL[0], "passk": LEVEL[1], "tokens_B": [lx, px], "rate": [ly, py],
                               "line_x": [x0, px], "tokens_saved_fraction": saved}}


GRADE_TEXT = {"official": "official verifier verdicts",
              "audited": "test-edit audited for SPROUT and official verifier verdicts for Pass@2/4/8"}


def caption(passk, grade, level, reported=None):
    p2 = next(p for p in passk["points"] if p["k"] == 2)
    star = ("" if reported is None else
            f"The star is the configuration the main table reports, two rounds of 4 then 3 branches: "
            f"{reported['rate']:.1f}% at {reported['tokens_M'] / 1e3:.2f} B tokens. ")
    return (
        "Scaling SPROUT on DeepSWE (113 tasks, GPT-5.6 Luna) against independent sampling, on a linear token axis. "
        "Labels denote rounds × branches per round. Green: one branch per round, more rounds. "
        "Blue: one round, more branches. Dashed, one colour per budget: the same branch budget (8 or 4 branches) "
        "split across rounds, from all rounds to a single round. "
        "Grey: independent sampling; Pass@1 is the SPROUT root rollout, Pass@2 "
        f"(attempts {p2['attempts'][0]} and {p2['attempts'][1]}, seed {passk['seed']}), Pass@4 and Pass@8 "
        "are unions of independent base rollouts with their summed tokens. "
        f"The grey dashed horizontal line marks the Pass@8 resolve rate across the whole token range ({level['rate'][1]:.1f}% at "
        f"{level['tokens_B'][1]:.2f} B tokens); 1×32 reaches {level['rate'][0]:.1f}% at {level['tokens_B'][0]:.2f} B "
        f"({100 * level['tokens_saved_fraction']:.0f}% fewer). "
        + star +
        f"Resolve rates are {GRADE_TEXT[grade]}; token totals include the root rollout and all actor, analyst and "
        "reviewer calls."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data", type=Path, help="scaling-and-rounds.json")
    parser.add_argument("passk", type=Path, help="luna-passk-curve.json")
    parser.add_argument("--output-dir", type=Path, help="default: <dir of data>/paper")
    parser.add_argument("--grade", choices=("official", "audited"), default="official",
                        help="SPROUT resolve rates: official verifier verdicts (default) or test-edit audited")
    parser.add_argument("--no-reported", action="store_true",
                        help="omit the star for the reported fixed 4+3 configuration")
    parser.add_argument("--no-level-text", action="store_true",
                        help="drop the rate and token-saving annotation beside 1×32")
    args = parser.parse_args()
    data = json.loads(args.data.read_text())
    for name, expected in data["source_sha256"].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source results changed: {name}")
    passk = json.loads(args.passk.read_text())
    reported = None if args.no_reported else load_fixed43(args.grade)[REPORTED_MODEL]
    output = (args.output_dir or args.data.resolve().parent / "paper").resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = output / ("scaling-linear" if args.grade == "official" else f"scaling-linear-{args.grade}")

    plt.rcParams.update(RC)
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    fig.subplots_adjust(left=.09, right=.985, bottom=.125, top=.975)
    handles, extra = draw(ax, data, passk, grade=args.grade, level_text=not args.no_level_text, reported=reported)
    legend = ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=8.2, handlelength=2.4,
                       labelspacing=.5, borderaxespad=.4)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for item in [ax.xaxis.label, ax.yaxis.label, *ax.texts, *legend.get_texts()]:
        box = item.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width + 1 or box.y1 > fig.bbox.height + 1:
            raise ValueError(f"Text extends beyond the figure: {item.get_text()}")
    for ext in ("pdf", "svg", "png"):
        fig.savefig(stem.with_suffix(f".{ext}"), dpi=300)
    plt.close(fig)

    rows = {row["stage"]: row for row in data["stages"]}
    text = caption(passk, args.grade, extra["level"], reported)
    if reported is not None:
        root = Path(reported["root"])
        extra["reported"] = {**reported, "model": REPORTED_MODEL, "stage": FIXED43_STAGE,
                             "source_sha256": {str(root / name): hashlib.sha256((root / name).read_bytes()).hexdigest()
                                               for name in ("scaling.json", "audit-comparison.json")}}
    (output / (stem.name + "-caption.md")).write_text(text + "\n")
    stem.with_suffix(".json").write_text(json.dumps({
        "sources": {"scaling": str(args.data.resolve()), "passk": str(args.passk.resolve())},
        "source_sha256": data["source_sha256"],
        "plot_program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "grade": args.grade, "x": "accepted_total_tokens / 1e9, linear", "y": f"{args.grade}_resolve_rate * 100",
        "series": {"rounds": ROUNDS, "single": SINGLE,
                   "budgets": {str(k): {"stages": v[0], "color": v[1]} for k, v in BUDGETS.items()},
                   "passk": [{"label": l, "tokens_B": x, "rate": y} for l, x, y in passk_curve(rows, passk, args.grade)],
                   **extra},
        "caption": text}, indent=2, ensure_ascii=False) + "\n")
    print(stem.with_suffix(".png"))


if __name__ == "__main__":
    main()
