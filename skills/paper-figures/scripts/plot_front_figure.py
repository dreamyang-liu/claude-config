#!/usr/bin/env python3
"""Front (teaser) figure. Default layout (`two`), one row in two halves:

  left   (a) 2 x 2 small panels, one per model: resolve rate vs tokens (% of Pass@4) on DeepSWE,
             Pass@1 / Pass@4 / Shepherd / SPROUT, arrow = SPROUT's token saving against Pass@4
  right  (b) RL: resolve rate after training (Base / GRPO / SPROUT, three benchmarks, left axis)
             and wall-clock time per training step (GRPO versus SPROUT, right axis)

Layout `row` (three thirds) and `grid` (two rows) add the scaling panel:

  left   (a) 2 x 2 small panels, one per model: resolve rate vs tokens (% of Pass@4) on DeepSWE,
             Pass@1 / Pass@4 / Shepherd / SPROUT, arrow = SPROUT's token saving against Pass@4
  middle (b) SPROUT scaling versus independent sampling (GPT-5.6 Luna, DeepSWE)
  right  (c) RL: resolve rate after training, Base / GRPO / SPROUT, three benchmarks
         (d) RL: wall-clock time per training step, GRPO versus SPROUT

Inputs: the main-table data (plot_tokens_vs_resolve.DATA), the verified scaling comparison,
the Luna Pass@k curve, and the RL numbers below (RL_* constants).

Run:  ~/sprout-runs/qwen/plots-env/bin/python .claude/skills/paper-figures/scripts/plot_front_figure.py \\
        ~/sprout-runs/qwen/deepswe-luna-rounds-20261005/plots/scaling-and-rounds.json \\
        ~/ash-data/preparation/three-bench-candidate-20260923/full/deepswe-luna-pass8-campaign-20261007T0740Z/luna-passk-curve.json
      (writes front-figure*.{png,pdf,svg,json} into <repo>/figures unless --output-dir says otherwise)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plot_teaser_scaling as scaling  # noqa: E402
from fixed43 import FIXED43_ROOTS, load_fixed43  # noqa: E402
from plot_tokens_vs_resolve import DATA, FIGURES  # noqa: E402

INK, MUTED, GRID, SPINE = scaling.INK, scaling.MUTED, scaling.GRID, scaling.SPINE
GREEN, BLUE, GREY, ORANGE = scaling.GREEN, scaling.BLUE, scaling.GREY, scaling.ORANGE
GOLD = "#C9962E"
PURPLE = "#8B5EA8"
STEEL = "#5B7FA6"
FS = 8.0  # base font size

# ---------------------------------------------------------------- RL results (Qwen3.8 27B policy)
RL_BENCHMARKS = ["SWE-bench Pro\nv2 Hard", "DeepSWE", "Terminal-\nBench 2.1"]
RL_RESOLVE = {           # resolve rate (%) per benchmark, in RL_BENCHMARKS order
    "Base (no RL)": [62.7, 37.2, 49.4],
    "GRPO": [74.5, 33.6, 39.3],
    "SPROUT": [84.3, 40.7, 64.0],
}
RL_TIME_PER_STEP_H = {"GRPO": 3.77, "SPROUT": 2.28}
RL_COLORS = {"Base (no RL)": "#B8BEC6", "GRPO": STEEL, "SPROUT": GREEN}

# ---------------------------------------------------------------- (a) per-model panels
MODELS = ["Qwen3.8 27B", "Kimi K3", "Claude Sonnet 5", "GPT 5.6 Luna"]
METHOD_STYLE = {  # marker, face, edge, label colour, size
    "Pass@1": ("o", "white", "#8A8F98", "#6B7280", 30),
    "Pass@4": ("s", GOLD, GOLD, "#A67A1D", 34),
    "Shepherd": ("D", PURPLE, PURPLE, PURPLE, 28),
    "SPROUT": ("o", GREEN, GREEN, GREEN, 46),
    "BPO": ("^", STEEL, "white", STEEL, 20),
}
# value-label offsets per (model, method) when the default collides
LABEL_OVERRIDE = {
    ("Qwen3.8 27B", "Pass@4"): (6, 5, "left", "center"),
    ("Qwen3.8 27B", "Shepherd"): (0, -7, "center", "top"),
}
ARROW_LABEL_SIDE = {"Claude Sonnet 5": +1}         # label above the arrow (default below)
ARROW_LABEL_T = {"Claude Sonnet 5": 0.32, "Qwen3.8 27B": 0.62}  # position along the arrow, 0 = Pass@4 end


# Panel (a) takes Luna's, Kimi K3's and Sonnet 5's SPROUT points from the fixed 4+3 experiments
# (fixed43.py); Pass@1/Pass@4/Shepherd and Qwen stay main-table values.
def use_fixed43(points):
    for model, p in points.items():
        DATA[model]["SPROUT"] = (p["rate"], None, None, p["tokens_M"])


def token_pct(model, method):
    return 100.0 * DATA[model][method][3] / DATA[model]["Pass@4"][3]


def style(ax, fs=FS):
    ax.tick_params(labelsize=fs, length=2.5, width=.6, pad=3)
    ax.grid(axis="y", color=GRID, linewidth=.55)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_linewidth(.7)


def draw_model(ax, model, show_xlabel, show_ylabel, scale=1.0, with_bpo=False, title=None, compact=True,
               arrow_label_side=None, top_pad=0.95):
    k = scale
    fs = (FS - 1) * k
    rows = DATA[model]
    methods = ["Pass@1", "Pass@4", "Shepherd", "SPROUT"]
    if with_bpo and "BPO" in rows:
        methods.insert(2, "BPO")
    ys = [rows[m][0] for m in methods]
    lo, hi = min(ys), max(ys)
    pad = max(6.0, 0.24 * (hi - lo))
    # compact panels are short: the Pass@1 value under its point needs more room above the x-axis
    ax.set_ylim(lo - pad * (1.7 if compact else 1.0), hi + pad * top_pad)
    # compact panels put the SPROUT value left of its point; room on the left keeps it off the axis
    ax.set_xlim(-22 if compact else 0, 120)
    ax.set_xticks([0, 50, 100])
    ax.grid(color=GRID, linewidth=.55, linestyle=(0, (3, 3)))
    ax.grid(axis="x", visible=False)
    style(ax, fs)
    ax.set_title(title or model, fontsize=fs + 1.5, fontweight="bold", color=INK, pad=4)
    if show_xlabel:
        ax.set_xlabel("Tokens (% of Pass@4)", fontsize=fs + .5)
    if show_ylabel:
        ax.set_ylabel("Resolve rate (%)", fontsize=fs + .5)
    for method in methods:
        m, face, edge, text, size = METHOD_STYLE[method]
        x, y = token_pct(model, method), rows[method][0]
        ax.scatter([x], [y], s=size * k * k, marker=m, facecolor=face, edgecolor=edge, linewidth=1.1,
                   zorder=4.5 if method == "BPO" else 4)
        if method == "BPO":
            continue  # coincides with Pass@4 (same resolve rate, 99% of its tokens); the legend names it
        default = (0, 6 if method == "SPROUT" else -7, "center", "bottom" if method == "SPROUT" else "top")
        if compact and method == "SPROUT":
            default = (-6, 0, "right", "center")
        dx, dy, ha, va = LABEL_OVERRIDE.get((model, method), default)
        ax.annotate(f"{y:.1f}", (x, y), xytext=(dx * k, dy * k), textcoords="offset points", ha=ha, va=va,
                    fontsize=fs - .3, fontweight="bold" if method == "SPROUT" else "normal", color=text, zorder=5)
    # Pass@4 -> SPROUT: dashed riser to SPROUT's height, then a horizontal arrow.
    xp, yp = token_pct(model, "Pass@4"), rows["Pass@4"][0]
    xs, ysv = token_pct(model, "SPROUT"), rows["SPROUT"][0]
    if abs(yp - ysv) > 0.3:
        ax.annotate("", xy=(xp, ysv), xytext=(xp, yp), arrowprops=dict(arrowstyle="-", color=GREEN, linewidth=.9,
                                                                       linestyle=(0, (3, 3)), shrinkA=5, shrinkB=0))
        shrink_a = 0
    else:
        shrink_a = 5
    ax.annotate("", xy=(xs, ysv), xytext=(xp, ysv),
                arrowprops=dict(arrowstyle="-|>,head_length=0.45,head_width=0.25", color=GREEN, linewidth=1.1,
                                shrinkA=shrink_a, shrinkB=6), zorder=3)
    side = arrow_label_side if arrow_label_side else (+1 if compact else ARROW_LABEL_SIDE.get(model, -1))
    t = 0.5 if compact else ARROW_LABEL_T.get(model, 0.5)
    ax.annotate(f"−{100 - xs:.0f}%" + ("" if compact else " tokens"), (xp + t * (xs - xp), ysv),
                xytext=(0, side * 7 * k),
                textcoords="offset points", ha="center", va="bottom" if side > 0 else "top",
                fontsize=fs - .3, fontweight="bold", color=GREEN,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=.85), zorder=5)


def model_legend_handles(with_bpo=False):
    out = []
    for method in ("Pass@1", "Pass@4", "BPO", "Shepherd", "SPROUT"):
        if method == "BPO" and not with_bpo:
            continue
        m, face, edge, _, _ = METHOD_STYLE[method]
        out.append(Line2D([], [], ls="none", marker=m, ms=5.5 if method != "Shepherd" else 4.8,
                          mfc=face, mec=edge if method != "BPO" else STEEL, mew=1.1,
                          label="BPO (entropy)" if method == "BPO" else method))
    return out


# ---------------------------------------------------------------- (c) RL resolve
def draw_rl_resolve(ax):
    fs = FS
    methods = list(RL_RESOLVE)
    n, width = len(methods), .27
    x = np.arange(len(RL_BENCHMARKS))
    for i, method in enumerate(methods):
        vals = RL_RESOLVE[method]
        pos = x + (i - (n - 1) / 2) * width
        bars = ax.bar(pos, vals, width * .9, color=RL_COLORS[method], zorder=3, edgecolor="white", linewidth=.6)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.1f}", (b.get_x() + b.get_width() / 2, v), xytext=(0, 2), textcoords="offset points",
                        ha="center", va="bottom", fontsize=fs - 1.8,
                        color=GREEN if method == "SPROUT" else INK, fontweight="bold" if method == "SPROUT" else "normal")
    for j in range(len(RL_BENCHMARKS)):
        g, s = RL_RESOLVE["GRPO"][j], RL_RESOLVE["SPROUT"][j]
        xg, xs = x[j], x[j] + width
        top = s + 9.5
        ax.plot([xg, xg, xs, xs], [g + 7, top, top, s + 7], color=GREEN, linewidth=.8,
                linestyle=(0, (3, 2)), zorder=4)
        ax.annotate(f"+{s - g:.1f} pp", ((xg + xs) / 2, top), xytext=(0, 1.5), textcoords="offset points",
                    ha="center", va="bottom", fontsize=fs - 1.2, color=GREEN, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(RL_BENCHMARKS, fontsize=fs - .5, linespacing=1.1)
    ax.set_xlim(-.55, len(RL_BENCHMARKS) - .45)
    ax.set_ylim(20, 110)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_ylabel("Resolve rate (%)", fontsize=fs + .5)
    style(ax, fs)
    ax.legend(handles=[Patch(color=RL_COLORS[m], label=m) for m in methods], loc="upper left",
              bbox_to_anchor=(-.02, 1.03), frameon=False, fontsize=fs - 1, ncol=3, handlelength=1.1,
              handletextpad=.4, columnspacing=.9, borderaxespad=0)


# ---------------------------------------------------------------- (b) RL resolve + time, two axes
def draw_rl_combined(ax):
    fs = FS
    methods = list(RL_RESOLVE)
    n, width = len(methods), .26
    x = np.arange(len(RL_BENCHMARKS))
    for i, method in enumerate(methods):
        vals = RL_RESOLVE[method]
        pos = x + (i - (n - 1) / 2) * width
        bars = ax.bar(pos, vals, width * .9, color=RL_COLORS[method], zorder=3, edgecolor="white", linewidth=.6)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.1f}", (b.get_x() + b.get_width() / 2, v), xytext=(0, 2), textcoords="offset points",
                        ha="center", va="bottom", fontsize=fs - 2,
                        color=GREEN if method == "SPROUT" else INK, fontweight="bold" if method == "SPROUT" else "normal")
    for j in range(len(RL_BENCHMARKS)):
        g, s = RL_RESOLVE["GRPO"][j], RL_RESOLVE["SPROUT"][j]
        xg, xs = x[j], x[j] + width
        top = s + 9.5
        ax.plot([xg, xg, xs, xs], [g + 7, top, top, s + 7], color=GREEN, linewidth=.8,
                linestyle=(0, (3, 2)), zorder=4)
        ax.annotate(f"+{s - g:.1f} pp", ((xg + xs) / 2, top), xytext=(0, 1.5), textcoords="offset points",
                    ha="center", va="bottom", fontsize=fs - 1.4, color=GREEN, fontweight="bold")
    # time per step on a second axis, as a fourth group
    xt = len(RL_BENCHMARKS) + .15
    ax2 = ax.twinx()
    tm = list(RL_TIME_PER_STEP_H)
    tv = [RL_TIME_PER_STEP_H[m] for m in tm]
    tpos = [xt - width * .95, xt + width * .95]
    bars = ax2.bar(tpos, tv, width * .9, color=[RL_COLORS[m] for m in tm], zorder=3, edgecolor="white",
                   linewidth=.6, hatch="////")
    for b in bars:
        b._hatch_color = (1, 1, 1, .55)
        b.stale = True
    for b, v, m in zip(bars, tv, tm):
        # the SPROUT label starts at its bar's left edge so it clears the arrow in the gap
        anchor = b.get_x() if m == "SPROUT" else b.get_x() + b.get_width() / 2
        ax2.annotate(f"{v:.2f} h", (anchor, v), xytext=(0, 2), textcoords="offset points",
                     ha="left" if m == "SPROUT" else "center", va="bottom", fontsize=fs - 1.6,
                     color=GREEN if m == "SPROUT" else INK, fontweight="bold" if m == "SPROUT" else "normal")
    g, s = tv
    ax2.annotate("", xy=(xt, s), xytext=(xt, g), arrowprops=dict(arrowstyle="-|>,head_length=0.4,head_width=0.2",
                                                                color=GREEN, linewidth=1.1), zorder=4)
    ax2.annotate(f"−{100 * (g - s) / g:.1f}%", (xt, (g + s) / 2), xytext=(4, 0), textcoords="offset points",
                 ha="left", va="center", fontsize=fs - 1, color=GREEN, fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=.85), zorder=5)
    ax2.set_ylim(1, 1 + (110 - 20) / 20)  # 1 h per 20 pp: right ticks on the left axis' gridlines
    ax2.set_yticks([1, 2, 3, 4, 5])
    ax2.set_ylabel("Time per RL step (h)", fontsize=fs + .5)
    ax2.tick_params(labelsize=fs, length=2.5, width=.6, pad=3)
    ax2.spines[["top", "left", "bottom"]].set_visible(False)
    ax2.spines["right"].set_linewidth(.7)
    ax2.grid(False)
    sep = len(RL_BENCHMARKS) - .5 + .05
    ax.axvline(sep, color=SPINE, linewidth=.7, linestyle=(0, (4, 3)), zorder=2)

    ax.set_xticks([*x, xt])
    ax.set_xticklabels(["SWE-bench\nPro v2 Hard", "DeepSWE", "Terminal-\nBench 2.1", "Time per\nRL step"],
                       fontsize=fs - 1.3, linespacing=1.1)
    ax.set_xlim(-.55, xt + .7)
    ax.set_ylim(20, 110)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_ylabel("Resolve rate (%)", fontsize=fs + .5)
    style(ax, fs)
    ax.spines["right"].set_visible(True)
    ax.spines["right"].set_linewidth(.7)
    ax.legend(handles=[Patch(color=RL_COLORS[m], label=m) for m in methods], loc="upper left",
              bbox_to_anchor=(-.02, 1.03), frameon=False, fontsize=fs - 1, ncol=3, handlelength=1.1,
              handletextpad=.4, columnspacing=.9, borderaxespad=0)
    return ax2


# ---------------------------------------------------------------- (d) RL time per step
def draw_rl_time(ax):
    fs = FS
    methods = list(RL_TIME_PER_STEP_H)
    vals = [RL_TIME_PER_STEP_H[m] for m in methods]
    x = np.arange(len(methods))
    bars = ax.bar(x, vals, .55, color=[RL_COLORS[m] for m in methods], zorder=3, edgecolor="white", linewidth=.6)
    for b, v, m in zip(bars, vals, methods):
        ax.annotate(f"{v:.2f} h", (b.get_x() + b.get_width() / 2, v), xytext=(0, 2.5), textcoords="offset points",
                    ha="center", va="bottom", fontsize=fs - 1, color=GREEN if m == "SPROUT" else INK,
                    fontweight="bold" if m == "SPROUT" else "normal")
    g, s = vals[0], vals[1]
    xa = 1.5
    ax.plot([0.28, xa + .05], [g, g], color=GREY, linewidth=.7, linestyle=(0, (3, 2.5)), zorder=2)
    ax.plot([1.28, xa + .05], [s, s], color=GREY, linewidth=.7, linestyle=(0, (3, 2.5)), zorder=2)
    ax.annotate("", xy=(xa, s), xytext=(xa, g), arrowprops=dict(arrowstyle="-|>,head_length=0.45,head_width=0.22",
                                                               color=GREEN, linewidth=1.2), zorder=4)
    ax.annotate(f"−{100 * (g - s) / g:.1f}%", (xa, (g + s) / 2), xytext=(-5, 0), textcoords="offset points",
                ha="right", va="center", fontsize=fs, color=GREEN, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=fs - .5)
    ax.set_xlim(-.6, 1.75)
    ax.set_ylim(1, 4.6)
    ax.set_yticks([1, 2, 3, 4])
    ax.set_ylabel("Time per RL step (h)", fontsize=fs + .5)
    style(ax, fs)


def panel_letter(fig, x, y, letter):
    fig.text(x, y, letter, fontsize=11, fontweight="bold", color=INK, ha="left", va="top")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scaling", type=Path, help="scaling-and-rounds.json")
    parser.add_argument("passk", type=Path, help="luna-passk-curve.json")
    parser.add_argument("--output-dir", type=Path, default=FIGURES, help="default: <repo>/figures")
    parser.add_argument("--layout", choices=("two", "grid", "row"), default="two",
                        help="two: (a) 2x2 models + (b) RL resolve and time on two axes, one row (default); "
                             "grid: two rows at text width with the scaling panel; row: one row in three thirds")
    parser.add_argument("--left", choices=("all", "qwen"), default="all",
                        help="left third: 2x2 of all four models, or one large Qwen3.8 27B panel")
    parser.add_argument("--sprout-source", choices=("fixed43", "table"), default="fixed43",
                        help="panel (a) SPROUT for Luna, Kimi K3 and Sonnet 5: the fixed 4+3 podman runs "
                             "(default) or the main-table (adaptive) values")
    parser.add_argument("--grade", choices=("official", "audited"), default="official",
                        help="SPROUT resolve rates in (a) and (b): official verifier verdicts (as Pass@k) or test-edit audited")
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="preview with fixed 4+3 runs that are still running (output name gets -preview)")
    args = parser.parse_args()
    data = json.loads(args.scaling.read_text())
    passk = json.loads(args.passk.read_text())
    fixed43 = None
    if args.sprout_source == "fixed43":
        fixed43 = load_fixed43(args.grade, args.allow_incomplete)
        use_fixed43(fixed43)
        for model, p in fixed43.items():
            pct = 100 * p["tokens_M"] / DATA[model]["Pass@4"][3]
            print(f"{model:16s} SPROUT 4+3 fixed: {p['resolved']}/{p['tasks']} = {p['rate']}% ({p['grade']}; "
                  f"official {p['official_resolved']}, audited {p['audited_resolved']}) | {p['tokens_M']:.0f}M tokens "
                  f"= {pct:.0f}% of Pass@4 | root {p['root_resolved']}/113 | complete {p['complete']}")

    plt.rcParams.update(scaling.RC)
    if args.layout == "two":
        fig = plt.figure(figsize=(7.2, 3.3))
        outer = GridSpec(1, 2, figure=fig, left=.07, right=.93, bottom=.20, top=.90,
                         width_ratios=[1.12, 1.18], wspace=.28)
        spec_a, spec_b = outer[0], outer[1]
        left = GridSpecFromSubplotSpec(2, 2, subplot_spec=spec_a, wspace=.58, hspace=.75)
        scale_b, legend_gap = 1.0, .13
    elif args.layout == "row":
        fig = plt.figure(figsize=(16.0, 4.9))
        outer = GridSpec(1, 3, figure=fig, left=.038, right=.992, bottom=.17, top=.90, wspace=.16)
        spec_a, spec_b, spec_cd = outer[0], outer[1], outer[2]
        left = GridSpecFromSubplotSpec(2, 2, subplot_spec=spec_a, wspace=.32, hspace=.62)
        right = GridSpecFromSubplotSpec(1, 2, subplot_spec=spec_cd, width_ratios=[2.2, 1], wspace=.42)
        scale_b, legend_gap = .84, .09
    else:
        # Two rows at double-column text width: (a) 2x2 + (b) on top, (c) + (d) below.
        fig = plt.figure(figsize=(7.2, 7.4))
        outer = GridSpec(2, 1, figure=fig, left=.085, right=.985, bottom=.075, top=.955,
                         height_ratios=[1.0, .78], hspace=.42)
        top_row = GridSpecFromSubplotSpec(1, 2, subplot_spec=outer[0], width_ratios=[1.0, 1.0], wspace=.28)
        spec_a, spec_b = top_row[0], top_row[1]
        left = GridSpecFromSubplotSpec(2, 2, subplot_spec=spec_a, wspace=.38, hspace=.70)
        right = GridSpecFromSubplotSpec(1, 2, subplot_spec=outer[1], width_ratios=[2.3, 1], wspace=.30)
        scale_b, legend_gap = .80, .075

    model_axes = []
    if args.left == "all":
        for i, model in enumerate(MODELS):
            ax = fig.add_subplot(left[i // 2, i % 2])
            # two-half layout: the saving label goes under the arrow, except where Pass@4 sits right under
            # it (Sonnet), which gets the label above and room under the title for it
            side = None if args.layout != "two" else ARROW_LABEL_SIDE.get(model, -1)
            draw_model(ax, model, show_xlabel=i >= 2, show_ylabel=i % 2 == 0,
                       arrow_label_side=side, top_pad=1.6 if side == +1 else 0.95)
            model_axes.append(ax)
    else:
        ax = fig.add_subplot(spec_a)
        draw_model(ax, "Qwen3.8 27B", show_xlabel=True, show_ylabel=True, scale=1.3, with_bpo=True,
                   title="Qwen3.8 27B on DeepSWE", compact=False)
        ax.legend(handles=model_legend_handles(with_bpo=True), loc="lower right", frameon=False,
                  fontsize=FS - .3, handletextpad=.4, borderaxespad=.6, labelspacing=.55)
        model_axes.append(ax)
    ax_b = fig.add_subplot(spec_b)
    if args.layout == "two":
        draw_rl_combined(ax_b)
    else:
        scaling.draw(ax_b, data, passk, scale=scale_b, legend=True, compact=args.layout == "grid", grade=args.grade)
        ax_c = fig.add_subplot(right[0])
        ax_d = fig.add_subplot(right[1])
        draw_rl_resolve(ax_c)
        draw_rl_time(ax_d)

    if args.left == "all":
        # Shared legend for the four model panels, under the 2 x 2 block.
        block = model_axes[2].get_position()
        block_right = model_axes[3].get_position()
        fig.legend(handles=model_legend_handles(), loc="upper center",
                   bbox_to_anchor=((block.x0 + block_right.x1) / 2, block.y0 - legend_gap), ncol=4, frameon=False,
                   fontsize=FS - .5, handletextpad=.35, columnspacing=1.1, borderaxespad=0)

    def letter(ax, text):
        pos = ax.get_position()
        dx = {"row": .028, "grid": .062, "two": .06}[args.layout]
        dy = {"row": .03, "grid": .012, "two": .03}[args.layout]
        fig.text(pos.x0 - dx, pos.y1 + dy, text, fontsize=11, fontweight="bold", color=INK, ha="left", va="bottom")

    letter(model_axes[0], "(a)")
    letter(ax_b, "(b)")
    if args.layout != "two":
        letter(ax_c, "(c)")
        letter(ax_d, "(d)")

    out = args.output_dir / ("front-figure" if args.left == "all" else "front-figure-qwen")
    if args.layout != "two":
        out = out.with_name(out.name + "-" + args.layout)
    if args.sprout_source == "table":
        out = out.with_name(out.name + "-table")
    if fixed43 is not None and (set(fixed43) != set(FIXED43_ROOTS)
                                or not all(p["complete"] for p in fixed43.values())):
        out = out.with_name(out.name + "-preview")
    out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(out.with_suffix(f".{ext}"), dpi=220)
    plt.close(fig)
    out.with_suffix(".json").write_text(json.dumps({
        "sprout_source": args.sprout_source, "grade": args.grade, "fixed43": fixed43,
        "panel_a": {m: {k: DATA[m][k] for k in ("Pass@1", "Pass@4", "Shepherd", "SPROUT")} for m in MODELS},
        "scaling": str(args.scaling.resolve()), "passk": str(args.passk.resolve()),
    }, indent=2) + "\n")
    print(out.with_suffix(".png"))


if __name__ == "__main__":
    main()
