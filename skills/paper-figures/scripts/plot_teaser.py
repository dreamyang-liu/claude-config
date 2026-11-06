"""Teaser figure: every method relative to Pass@4, all four models in one panel.

x: token consumption as % of Pass@4.  y: resolve-rate difference to Pass@4 in
percentage points.  Pass@4 is the reference point at (100, 0); the shaded
quadrant is "better AND cheaper than Pass@4".

Run:  ~/sprout-runs/qwen/plots-env/bin/python .claude/skills/paper-figures/scripts/plot_teaser.py
      (writes teaser.{png,pdf} into <repo>/figures)
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_tokens_vs_resolve import DATA, FIGURES, STYLE, INK, MUTED, GRID, PANEL_EDGE  # noqa: E402

SHORT = {
    "Qwen3.8 27B": "Qwen3.8 27B",
    "Kimi K3": "Kimi K3",
    "Claude Sonnet 5": "Sonnet 5",
    "GPT 5.6 Luna": "GPT 5.6 Luna",
}
MODELS = ["Qwen3.8 27B", "GPT 5.6 Luna"]  # models shown
METHODS = ["Pass@1", "Shepherd", "BPO", "SPROUT"]
SIZE = {"Pass@1": 95, "Shepherd": 90, "BPO": 110, "SPROUT": 150}
STYLE = dict(STYLE)
STYLE["BPO"] = dict(marker="^", face="#2f6db5", edge="#2f6db5", text="#285e9c")

# Single-round SPROUT width scaling on GPT 5.6 Luna: one round with k branches,
# k = 1..32, nested subsample of the 32-branch run (seed 42).  Audited resolve
# rate and accepted tokens from
# ~/sprout-runs/qwen/deepswe-luna-rounds-20261005/plots/scaling-and-rounds.json
SINGLE_ROUND_MODEL = "GPT 5.6 Luna"
SINGLE_ROUND = [  # (k, resolve %, tokens M)
    (1, 68.14, 436.95),
    (2, 72.57, 482.13),
    (4, 75.22, 573.60),
    (8, 76.11, 745.20),
    (16, 76.99, 1097.22),
    (32, 77.88, 1849.84),
]

# Per-point label placement (dx, dy in points, ha).
LABEL = {
    ("SPROUT", "Qwen3.8 27B"):      (11, -9, "left"),
    ("SPROUT", "Kimi K3"):          (-11, 5, "right"),
    ("SPROUT", "Claude Sonnet 5"):  (11, 9, "left"),
    ("SPROUT", "GPT 5.6 Luna"):     (-11, 0, "right"),
    ("BPO", "Qwen3.8 27B"):         (-10, -12, "right"),
    ("Shepherd", "Qwen3.8 27B"):    (0, -13, "center"),
    ("Shepherd", "Kimi K3"):        (10, 0, "left"),
    ("Shepherd", "Claude Sonnet 5"): (-10, 0, "right"),
    ("Shepherd", "GPT 5.6 Luna"):   (10, 0, "left"),
    ("Pass@1", "Qwen3.8 27B"):      (10, 0, "left"),
    ("Pass@1", "Kimi K3"):          (10, 0, "left"),
    ("Pass@1", "Claude Sonnet 5"):  (10, 0, "left"),
    ("Pass@1", "GPT 5.6 Luna"):     (10, 0, "left"),
}


def rel(model: str, method: str) -> tuple[float, float]:
    base = DATA[model]["Pass@4"]
    row = DATA[model][method]
    return 100.0 * row[3] / base[3], row[0] - base[0]


def main() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.edgecolor": PANEL_EDGE,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
    })
    green = STYLE["SPROUT"]["face"]
    gold = STYLE["Pass@4"]["face"]

    fig, ax = plt.subplots(figsize=(10.5, 6.2), facecolor="white")
    fig.subplots_adjust(left=0.085, right=0.985, top=0.97, bottom=0.11)

    ax.set_xlim(0, 140)
    ax.set_ylim(-40, 15)
    ax.set_xticks([0, 25, 50, 75, 100, 125])
    ax.set_yticks([-40, -30, -20, -10, 0, 10])
    ax.set_yticklabels(["−40", "−30", "−20", "−10", "Pass@4", "+10"])
    ax.grid(color=GRID, linewidth=0.7, linestyle=(0, (3, 3)))
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)

    # "Better and cheaper" quadrant.
    ax.axvspan(0, 100, ymin=(0 + 40) / 55, ymax=1, color=green, alpha=0.07, zorder=0)
    ax.axvspan(100, 140, ymin=(0 + 40) / 55, ymax=1, color=MUTED, alpha=0.05, zorder=0)
    ax.axhline(0, color=gold, linewidth=1.1, linestyle=(0, (4, 3)), zorder=1)
    ax.axvline(100, color=gold, linewidth=1.1, linestyle=(0, (4, 3)), zorder=1)
    ax.text(97, 13.6, "Better than Pass@4, fewer tokens", fontsize=10,
            fontweight="bold", color=green, va="top", ha="right")
    ax.text(3, -39.2, "Cheaper, but worse", fontsize=9.5, color=MUTED, va="bottom")
    ax.text(137, 13.6, "Better, but costlier", fontsize=9.5, color=MUTED, va="top", ha="right")

    # Pass@4 reference.
    ax.scatter([100], [0], s=130, marker="s", facecolor=gold, edgecolor=gold,
               linewidth=1.6, zorder=4)
    ax.annotate("Pass@4\n(reference)", (100, 0), xytext=(9, 10),
                textcoords="offset points", ha="left", va="bottom", fontsize=9.5,
                color=STYLE["Pass@4"]["text"])

    for method in METHODS:
        st = STYLE[method]
        for model in MODELS:
            if method not in DATA[model]:
                continue
            x, y = rel(model, method)
            ax.scatter([x], [y], s=SIZE[method], marker=st["marker"],
                       facecolor=st["face"], edgecolor=st["edge"], linewidth=1.6,
                       zorder=5)
            dx, dy, ha = LABEL[(method, model)]
            if method == "SPROUT":
                sign = "+" if y > 0 else "±" if abs(y) < 0.05 else "−"
                text = f"{SHORT[model]}\n{sign}{abs(y):.1f} pp, −{100 - x:.0f}% tokens"
                color, weight, size = st["text"], "bold", 9.4
            else:
                text = SHORT[model]
                color, weight, size = st["text"], "normal", 8.8
            ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points",
                        ha=ha, va="center", fontsize=size, fontweight=weight,
                        color=color, zorder=6)

    # Single-round width scaling (Luna), relative to Luna's Pass@4.
    base = DATA[SINGLE_ROUND_MODEL]["Pass@4"]
    sx = [100.0 * t / base[3] for _, _, t in SINGLE_ROUND]
    sy = [r - base[0] for _, r, _ in SINGLE_ROUND]
    ax.plot(sx, sy, color=green, linewidth=1.1, linestyle=(0, (2.5, 2.5)), zorder=3)
    ax.scatter(sx, sy, s=34, marker="o", facecolor="white", edgecolor=green, linewidth=1.4, zorder=5)
    series_label = {1: (0, -9, "center", "top"), 2: (0, -9, "center", "top"), 4: (0, -9, "center", "top"),
                    8: (0, 9, "center", "bottom"), 16: (0, 9, "center", "bottom"), 32: (0, -9, "center", "top")}
    for (k, _, _), x, y in zip(SINGLE_ROUND, sx, sy):
        dx, dy, ha, va = series_label[k]
        ax.annotate(f"1×{k}", (x, y), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, va=va, fontsize=8.4, color=green, zorder=6)

    ax.set_xlabel("Token consumption (% of Pass@4)", fontsize=11, labelpad=8)
    ax.set_ylabel("Resolve rate vs. Pass@4 (percentage points)", fontsize=11,
                  labelpad=8)

    handles = [
        Line2D([], [], linestyle="none", marker=STYLE[m]["marker"],
               markersize=8.5 if m != "Shepherd" else 7.5,
               markerfacecolor=STYLE[m]["face"], markeredgecolor=STYLE[m]["edge"],
               markeredgewidth=1.6, label=m)
        for m in ["Pass@1", "Pass@4", "Shepherd", "BPO", "SPROUT"]
    ]
    handles[-2].set_label("BPO (entropy)")
    handles.append(Line2D([], [], color=green, linewidth=1.1, linestyle=(0, (2.5, 2.5)),
                          marker="o", markersize=5.5, markerfacecolor="white",
                          markeredgecolor=green, markeredgewidth=1.4,
                          label="SPROUT, single round 1×k (Luna)"))
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9.2,
              handletextpad=0.5, borderaxespad=0.8, labelcolor=INK, ncol=2,
              columnspacing=1.0)

    FIGURES.mkdir(parents=True, exist_ok=True)
    out = FIGURES / "teaser"
    fig.savefig(out.with_suffix(".png"), dpi=220, facecolor="white")
    fig.savefig(out.with_suffix(".pdf"), facecolor="white")
    print(f"wrote {out}.png and {out}.pdf")


if __name__ == "__main__":
    main()
