"""DeepSWE: resolve rate vs token consumption (% of Pass@4), one panel per model.

Data: the main comparison table (Pass@1, Pass@4, BPO, Shepherd, SPROUT).
BPO is only available for Qwen3.8 27B and sits on top of its Pass@4 point
(71.7 % at 99 % tokens), so it is left out of the plot and kept in the table.

Run:  ~/sprout-runs/qwen/plots-env/bin/python .claude/skills/paper-figures/scripts/plot_tokens_vs_resolve.py
      (writes tokens-vs-resolve.{png,pdf} into <repo>/figures)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# Figure outputs go to <repo>/figures (gitignored); this file lives at
# <repo>/.claude/skills/paper-figures/scripts. The other figure scripts import this constant.
FIGURES = Path(__file__).resolve().parents[4] / "figures"

# model -> method -> (resolve %, recovery %, steps, tokens M)
DATA = {
    "Qwen3.8 27B": {
        "Pass@1":   (37.2, 0.0, 16_708, 1921),
        "Pass@4":   (71.7, 54.9, 64_136, 8673),
        "BPO":      (71.7, 54.9, 45_549, 8589),
        "Shepherd": (67.3, 47.9, 55_280, 9026),
        "SPROUT":   (78.6, 64.8, 23_174, 4123),
    },
    "Kimi K3": {
        "Pass@1":   (72.3, 0.0, 13_001, 1154),
        "Pass@4":   (92.0, 71.2, 52_003, 4614),
        "Shepherd": (78.8, 23.2, 20_668, 2272),
        "SPROUT":   (92.9, 74.4, 14_790, 1345),
    },
    "Claude Sonnet 5": {
        "Pass@1":   (46.9, 0.0, 15_362, 1872),
        "Pass@4":   (78.8, 60.0, 61_450, 7487),
        "Shepherd": (72.6, 48.3, 33_395, 4328),
        "SPROUT":   (78.8, 60.0, 26_050, 3688),
    },
    "GPT 5.6 Luna": {
        "Pass@1":   (42.5, 0.0, 6_020, 352),
        "Pass@4":   (68.1, 44.6, 24_081, 1409),
        "Shepherd": (62.8, 35.4, 13_886, 985),
        "SPROUT":   (77.9, 61.5, 7_478, 534),
    },
}

PLOTTED = ["Pass@1", "Pass@4", "Shepherd", "SPROUT"]

# marker, face, edge, label-colour.  Pass@1 is a hollow neutral circle so the
# three coloured methods carry identity by hue AND shape.
STYLE = {
    "Pass@1":   dict(marker="o", face="white",   edge="#8a8f98", text="#555b66"),
    "Pass@4":   dict(marker="s", face="#c9962e", edge="#c9962e", text="#a67a1d"),
    "Shepherd": dict(marker="D", face="#8b5ea8", edge="#8b5ea8", text="#7a4f97"),
    "SPROUT":   dict(marker="o", face="#2f7d5b", edge="#2f7d5b", text="#2f7d5b"),
}
SIZE = {"Pass@1": 110, "Pass@4": 120, "Shepherd": 95, "SPROUT": 140}

# Value-label offsets in points (dx, dy) and alignment, when the default
# (SPROUT above, everything else below) would collide with a neighbour.
LABEL_OVERRIDE = {
    ("Qwen3.8 27B", "Pass@4"): dict(xytext=(13, 3), ha="left", va="center"),
    ("Qwen3.8 27B", "Shepherd"): dict(xytext=(0, -14), ha="center", va="center"),
}
# Side of the Pass@4 -> SPROUT arrow on which its saving label sits.
ARROW_LABEL_SIDE = {"Claude Sonnet 5": +1}  # default: below (-1)
# Position of the label along the arrow, 0 = Pass@4 end, 1 = SPROUT end.
ARROW_LABEL_T = {"Claude Sonnet 5": 0.32, "Qwen3.8 27B": 0.62}

INK = "#1f2328"
MUTED = "#6b7280"
GRID = "#e5e7eb"
PANEL_EDGE = "#d7dade"


def token_pct(model: str, method: str) -> float:
    base = DATA[model]["Pass@4"][3]
    return 100.0 * DATA[model][method][3] / base


def main() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.edgecolor": PANEL_EDGE,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
    })

    models = list(DATA)
    fig, axes = plt.subplots(1, len(models), figsize=(13.2, 4.2), facecolor="white")
    fig.subplots_adjust(left=0.045, right=0.99, top=0.80, bottom=0.21, wspace=0.28)

    for ax, model in zip(axes, models):
        rows = DATA[model]
        ys = [rows[m][0] for m in PLOTTED]
        lo, hi = min(ys), max(ys)
        pad = max(6.0, 0.22 * (hi - lo))
        ax.set_ylim(lo - pad, hi + pad * 0.9)
        ax.set_xlim(0, 118)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.grid(color=GRID, linewidth=0.7, linestyle=(0, (3, 3)))
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.tick_params(length=0)
        ax.set_title(model, fontsize=12, fontweight="bold", color=INK, pad=10)

        for method in PLOTTED:
            st = STYLE[method]
            x, y = token_pct(model, method), rows[method][0]
            ax.scatter(
                [x], [y], s=SIZE[method], marker=st["marker"],
                facecolor=st["face"], edgecolor=st["edge"], linewidth=1.6,
                zorder=4,
            )
            # Direct value label: SPROUT above, the rest below.
            kw = dict(xytext=(0, 11 if method == "SPROUT" else -14), ha="center", va="center")
            kw.update(LABEL_OVERRIDE.get((model, method), {}))
            ax.annotate(
                f"{y:.1f}", (x, y), textcoords="offset points", fontsize=10, **kw,
                fontweight="bold" if method == "SPROUT" else "normal",
                color=st["text"], zorder=5,
            )

        # Arrow from Pass@4 to SPROUT, always horizontal at SPROUT's height.
        # When Pass@4 sits at a different height, a dashed riser first
        # extends from its marker up (or down) to that level.
        xp, yp = token_pct(model, "Pass@4"), rows["Pass@4"][0]
        xs, ysv = token_pct(model, "SPROUT"), rows["SPROUT"][0]
        saving = 100.0 - xs
        green = STYLE["SPROUT"]["face"]
        if abs(yp - ysv) > 0.3:
            ax.annotate(
                "", xy=(xp, ysv), xytext=(xp, yp),
                arrowprops=dict(
                    arrowstyle="-", color=green, linewidth=1.2,
                    linestyle=(0, (3, 3)), shrinkA=9, shrinkB=0,
                ),
                zorder=3,
            )
            shrink_a = 0
        else:
            shrink_a = 9
        ax.annotate(
            "", xy=(xs, ysv), xytext=(xp, ysv),
            arrowprops=dict(
                arrowstyle="-|>,head_length=0.55,head_width=0.3",
                color=green, linewidth=1.5, shrinkA=shrink_a, shrinkB=10,
            ),
            zorder=3,
        )
        side = ARROW_LABEL_SIDE.get(model, -1)
        t = ARROW_LABEL_T.get(model, 0.5)
        xm = xp + t * (xs - xp)
        ax.annotate(
            f"−{saving:.1f}% tokens", (xm, ysv), xytext=(0, side * 14),
            textcoords="offset points", ha="center",
            va="bottom" if side > 0 else "top",
            fontsize=9.6, fontweight="bold", color=green,
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.85),
            zorder=5,
        )

    axes[0].set_ylabel("Resolve rate (%)", fontsize=10.5, labelpad=8)
    fig.text(
        0.52, 0.075, "Token consumption (% of Pass@4)",
        ha="center", va="center", fontsize=11.5, fontweight="bold",
        color=STYLE["SPROUT"]["face"],
    )
    fig.text(
        0.52, 0.025, "DeepSWE, 113 tasks · arrow: SPROUT's token saving relative to Pass@4",
        ha="center", va="center", fontsize=9.5, color=MUTED,
    )

    handles = [
        Line2D([], [], linestyle="none", marker=STYLE[m]["marker"],
               markersize=8.5 if m != "Shepherd" else 7.5,
               markerfacecolor=STYLE[m]["face"], markeredgecolor=STYLE[m]["edge"],
               markeredgewidth=1.6, label=m)
        for m in PLOTTED
    ]
    fig.legend(
        handles=handles, loc="upper center", ncol=4, frameon=False,
        bbox_to_anchor=(0.52, 0.985), fontsize=10, handletextpad=0.5,
        columnspacing=2.2, labelcolor=INK,
    )

    FIGURES.mkdir(parents=True, exist_ok=True)
    out = FIGURES / "tokens-vs-resolve"
    fig.savefig(out.with_suffix(".png"), dpi=220, facecolor="white")
    fig.savefig(out.with_suffix(".pdf"), facecolor="white")
    print(f"wrote {out}.png and {out}.pdf")


if __name__ == "__main__":
    main()
