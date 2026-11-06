#!/usr/bin/env python3
"""Teaser figure: SPROUT scaling versus independent sampling on DeepSWE (GPT-5.6 Luna).

Reads the verified scaling-and-rounds comparison (SPROUT points) and the Pass@k curve
(independent base rollouts).  Four series only, ordered by visual weight:

  1. SPROUT, k rounds x 1 branch (1x1 -> 2x1 -> 4x1 -> 8x1)   bold, the hero line
  2. SPROUT, single round 1xk (1x1 ... 1x32)                   medium
  3. SPROUT, 8-branch budget split (8x1, 4x2, 2x4, 1x8)        thin, dashed
  4. Independent sampling Pass@1/2/4/8                          grey, dashed

The band between the Pass@k curve and the single-round curve (the weakest SPROUT series)
is shaded: it is the gain over independent sampling at equal token spend, without any text.
Pass@1 is the SPROUT root rollout itself.

`draw(ax, data, passk, scale)` draws the panel on any Axes (used by plot_front_figure.py);
`main()` renders the standalone figure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import FormatStrFormatter, NullLocator

INK, MUTED, GRID, SPINE = "#2B3440", "#6B7684", "#E6EAEF", "#AEB6C0"
GREY = "#8A939E"
BLUE = "#3A6EA5"
ORANGE = "#D98B4F"
GREEN = "#1F8A5A"
BAND = "#3A6EA5"

SINGLE = ["sprout-b1", "sprout-b2", "sprout-b4", "sprout-b8", "sprout-b16", "sprout-b32"]
ROUNDS = ["sprout-b1", "sprout-r2-b1", "sprout-r4-b1", "sprout-r8-b1"]
BUDGET8 = ["sprout-r8-b1", "sprout-r4-b2", "sprout-r2-b4", "sprout-b8"]

RC = {
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
    "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": SPINE,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none", "savefig.facecolor": "white",
}


def passk_curve(rows, passk, grade="official"):
    """[(label, tokens_B, rate)]: Pass@1 is the SPROUT root; Pass@2/4/8 from independent attempts."""
    base = rows["baseline"]
    first = ("Pass@1", base["accepted_total_tokens"] / 1e9, 100 * base[f"{grade}_resolve_rate"])
    return [first] + [(p["label"], p["tokens_B"], p["rate"]) for p in passk["points"] if p["k"] > 1]


def draw(ax, data, passk, scale=1.0, legend=True, compact=False, log=True, grade="official"):
    """Draw the scaling panel. `scale` shrinks fonts/markers for multi-panel use; `grade` picks the
    SPROUT resolve rate: official verifier verdicts or test-edit audited."""
    rows = {row["stage"]: row for row in data["stages"]}
    s = scale

    def xy(stage):
        row = rows[stage]
        return row["accepted_total_tokens"] / 1e9, 100 * row[f"{grade}_resolve_rate"]

    def series(stages):
        return np.array([xy(st) for st in stages]).T

    pk = passk_curve(rows, passk, grade)
    pk_x = np.array([p[1] for p in pk])
    pk_y = np.array([p[2] for p in pk])
    bx, by = xy("baseline")

    if log:
        ax.set_xscale("log")
        ax.set(xlim=(.33, 3.15), ylim=(40, 97))
        ax.set_xlabel("Total tokens (billions, log scale)", fontsize=10.5 * s)
        ax.set_xticks([.4, .6, .8, 1.2, 1.6, 2.0, 2.8])
    else:
        ax.set(xlim=(.25, 2.95), ylim=(40, 97))
        ax.set_xlabel("Total tokens (billions)", fontsize=10.5 * s)
        ax.set_xticks([.4, .8, 1.2, 1.6, 2.0, 2.4, 2.8])
    ax.set_ylabel("Resolve rate (%)", fontsize=10.5 * s)
    ax.xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_yticks([40, 50, 60, 70, 80, 90])
    ax.tick_params(labelsize=9 * s, length=3, width=.6, pad=4 * s)
    ax.grid(axis="y", color=GRID, linewidth=.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_linewidth(.7)

    sx, sy = series(SINGLE)
    if log:
        grid = np.geomspace(sx[0], sx[-1], 200)
        lower = np.interp(np.log(grid), np.log(pk_x), pk_y)
        upper = np.interp(np.log(grid), np.log(sx), sy)
    else:
        grid = np.linspace(sx[0], sx[-1], 200)
        lower = np.interp(grid, pk_x, pk_y)
        upper = np.interp(grid, sx, sy)
    ax.fill_between(grid, lower, upper, color=BAND, alpha=.10, linewidth=0, zorder=1)
    ax.plot([bx, sx[0]], [by, sy[0]], color=GREY, linewidth=.9 * s, linestyle=(0, (1.5, 2.5)), alpha=.8, zorder=2)

    ax.plot(pk_x, pk_y, color=GREY, linewidth=1.5 * s, linestyle=(0, (4.5, 2.5)), marker="s", markersize=5.5 * s,
            markerfacecolor="white", markeredgecolor=GREY, markeredgewidth=1.3 * s, zorder=3)
    b8x, b8y = series(BUDGET8)
    ax.plot(b8x, b8y, color=ORANGE, linewidth=1.3 * s, linestyle=(0, (3.2, 2.0)), marker="D", markersize=4.6 * s,
            markeredgecolor="white", markeredgewidth=.7, markevery=[1, 2], zorder=4)
    ax.plot(sx, sy, color=BLUE, linewidth=1.9 * s, marker="o", markersize=5.4 * s,
            markeredgecolor="white", markeredgewidth=.8, solid_capstyle="round", zorder=5)
    rx, ry = series(ROUNDS)
    ax.plot(rx, ry, color=GREEN, linewidth=2.8 * s, solid_capstyle="round", zorder=6)
    ax.plot(rx, ry, linestyle="none", marker="o", markersize=7.2 * s, color=GREEN,
            markeredgecolor="white", markeredgewidth=1.0, zorder=7)
    ax.plot(rx[-1], ry[-1], linestyle="none", marker="o", markersize=15 * s, markerfacecolor="none",
            markeredgecolor=GREEN, markeredgewidth=1.3, alpha=.55, zorder=7)

    label_specs = [
        (GREEN, True, {"sprout-b1": (-9, -4, "right", "top"), "sprout-r2-b1": (-9, 0, "right", "center"),
                       "sprout-r4-b1": (-9, 2, "right", "center"), "sprout-r8-b1": (-11, 6, "right", "bottom")}
         if not log else
                      {"sprout-b1": (8, -8, "left", "top"), "sprout-r2-b1": (-9, 0, "right", "center"),
                       "sprout-r4-b1": (-9, 2, "right", "center"), "sprout-r8-b1": (-11, 6, "right", "bottom")}),
        (BLUE, False, {"sprout-b2": (6, -8, "left", "top"), "sprout-b4": (-2, 8, "center", "bottom"),
                       "sprout-b8": (3, -10, "center", "top"), "sprout-b16": (0, 9, "center", "bottom"),
                       "sprout-b32": (0, 9, "center", "bottom")}
         if not log else
                      {"sprout-b2": (11, -5, "left", "top"), "sprout-b4": (0, 9, "center", "bottom"),
                       "sprout-b8": (0, -10, "center", "top"), "sprout-b16": (0, 9, "center", "bottom"),
                       "sprout-b32": (0, 9, "center", "bottom")}),
        (ORANGE, False, {"sprout-r4-b2": (7, 1, "left", "center"), "sprout-r2-b4": (8, -6, "left", "top")}
         if compact else {"sprout-r4-b2": (8, 6, "left", "bottom"), "sprout-r2-b4": (9, 0, "left", "center")}),
    ]
    for color, bold, specs in label_specs:
        for stage, (dx, dy, ha, va) in specs.items():
            ax.annotate(rows[stage]["label"], xy(stage), xytext=(dx * s, dy * s), textcoords="offset points",
                        fontsize=(9.6 if bold else 8.8) * s, fontweight="bold" if bold else "normal",
                        color=color, ha=ha, va=va, zorder=8)
    pk_offsets = {"Pass@1": (10, -2, "left", "center"), "Pass@2": (9, -4, "left", "top"),
                  "Pass@4": (0, -10, "center", "top"), "Pass@8": (0, -10, "center", "top")}
    for label, x, y in pk:
        dx, dy, ha, va = pk_offsets[label]
        ax.annotate(label, (x, y), xytext=(dx * s, dy * s), textcoords="offset points", fontsize=8.8 * s,
                    color=GREY, ha=ha, va=va, zorder=8)

    names = (["SPROUT, k rounds × 1 branch", "SPROUT, 1 round × k branches",
              "SPROUT, 8 branches, split rounds", "Pass@k, independent sampling"] if compact else
             ["SPROUT, k rounds × 1 branch", "SPROUT, single round × k branches",
              "SPROUT, 8 branches split across rounds", "Independent sampling, Pass@k"])
    handles = [
        Line2D([], [], color=GREEN, linewidth=2.8 * s, marker="o", markersize=6.5 * s, markeredgecolor="white",
               label=names[0]),
        Line2D([], [], color=BLUE, linewidth=1.9 * s, marker="o", markersize=5 * s, markeredgecolor="white",
               label=names[1]),
        Line2D([], [], color=ORANGE, linewidth=1.3 * s, linestyle="--", marker="D", markersize=4.3 * s,
               markeredgecolor="white", label=names[2]),
        Line2D([], [], color=GREY, linewidth=1.5 * s, linestyle="--", marker="s", markersize=5 * s,
               markerfacecolor="white", markeredgewidth=1.3 * s, label=names[3]),
    ]
    if legend:
        if compact:
            return ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=8.2 * s,
                             handlelength=2.0, labelspacing=.5, borderaxespad=.3, handletextpad=.6)
        return ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=8.6 * s,
                         handlelength=2.4, labelspacing=.6, borderaxespad=.4)
    return handles


GRADE_TEXT = {"official": "official verifier verdicts",
              "audited": "test-edit audited for SPROUT and official verifier verdicts for Pass@2/4/8"}


def caption(passk, grade="official"):
    p2 = next(p for p in passk["points"] if p["k"] == 2)
    return (
        "Scaling SPROUT on DeepSWE (113 tasks, GPT-5.6 Luna) against independent sampling. "
        "Labels denote rounds × branches per round. Green: one branch per round, more rounds. "
        "Blue: one round, more branches. Orange: eight branches split across rounds. "
        "Grey: independent sampling; Pass@1 is the SPROUT root rollout, Pass@2 "
        f"(attempts {p2['attempts'][0]} and {p2['attempts'][1]}, seed {passk['seed']}), Pass@4 and Pass@8 "
        "are unions of independent base rollouts with their summed tokens. "
        "The shaded band is the gap between independent sampling and the weakest SPROUT series at equal tokens. "
        f"Resolve rates are {GRADE_TEXT[grade]}; token totals include the root rollout and all actor, analyst and "
        "reviewer calls; the token axis is logarithmic."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path, help="scaling-and-rounds.json")
    parser.add_argument("passk", type=Path, help="luna-passk-curve.json")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--linear", action="store_true", help="linear token axis instead of log")
    parser.add_argument("--grade", choices=("official", "audited"), default="official",
                        help="SPROUT resolve rates: official verifier verdicts (default) or test-edit audited")
    args = parser.parse_args()
    data = json.loads(args.data.read_text())
    passk = json.loads(args.passk.read_text())
    output = (args.output_dir or args.data.resolve().parent / "paper").resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = output / ("scaling-teaser-linear" if args.linear else "scaling-teaser")

    plt.rcParams.update(RC)
    fig, ax = plt.subplots(figsize=(6.4, 4.3))
    fig.subplots_adjust(left=.10, right=.985, bottom=.255, top=.975)
    handles = draw(ax, data, passk, legend=False, log=not args.linear, grade=args.grade)
    legend = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.54, .01), ncol=2,
                        frameon=False, fontsize=8.6, handlelength=2.4, columnspacing=1.6, labelspacing=.6)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for item in [ax.xaxis.label, ax.yaxis.label, *ax.texts, *legend.get_texts()]:
        box = item.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width + 1 or box.y1 > fig.bbox.height + 1:
            raise ValueError(f"Text extends beyond the figure: {item.get_text()}")
    for ext in ("pdf", "svg", "png"):
        fig.savefig(stem.with_suffix(f".{ext}"), dpi=300)
    plt.close(fig)

    text = caption(passk, args.grade)
    rows = {row["stage"]: row for row in data["stages"]}
    if args.linear:
        text = text.replace("; the token axis is logarithmic", "")
    (output / (stem.name + "-caption.md")).write_text(text + "\n")
    stem.with_suffix(".json").write_text(json.dumps({
        "sources": {"scaling": str(args.data.resolve()), "passk": str(args.passk.resolve())}, "grade": args.grade,
        "series": {"rounds": ROUNDS, "single": SINGLE, "budget8": BUDGET8,
                   "passk": [{"label": l, "tokens_B": x, "rate": y} for l, x, y in passk_curve(rows, passk, args.grade)]},
        "caption": text}, indent=2, ensure_ascii=False) + "\n")
    print(stem.with_suffix(".png"))


if __name__ == "__main__":
    main()
