"""The fixed-count 4+3 SPROUT experiments (2 rounds, exactly 4 then 3 branches, stop after a
successful round) on podman, one per model, each continuing its own fresh root rollout: where
they live and how a stage's results are read.

Standard library only, so a script that needs the roots alone runs under any python3.
plot_front_figure.py takes panel (a)'s SPROUT points from here and fixed43_table_rows.py the
main-table rows. The trajectory-dataset skill's pack_fixed43_trajectories.py carries its own
copy of the constants because it ships in the Hugging Face package as pack.py and has to read
standalone.
"""
from __future__ import annotations

import json
from pathlib import Path

RUNS = Path.home() / "sprout-runs/qwen"
FIXED43_STAGE = "sprout-r2-b4-3"
FIXED43_ROOTS = {
    "GPT 5.6 Luna": RUNS / "deepswe-luna-rounds-4-3-20261007",
    "Kimi K3": RUNS / "deepswe-kimi-k3-rounds-4-3-20261008",
    "Claude Sonnet 5": RUNS / "deepswe-sonnet5-rounds-4-3-20261008",
}


def load_fixed43(grade="official", allow_incomplete=False):
    """{model: row} for each fixed 4+3 experiment: resolve rate (official or audited) and the
    stage's accepted tokens (root rollout once + branches + analyst/reviewer calls)."""
    points = {}
    for model, root in FIXED43_ROOTS.items():
        def rows(name):
            path = root / name
            return {r["stage"]: r for r in json.loads(path.read_text())["stages"]} if path.exists() else {}

        audit, stages = rows("audit-comparison.json"), rows("scaling.json")
        completion = root / "completion-audit.json"
        verified = completion.exists() and json.loads(completion.read_text()).get("complete") is True
        if FIXED43_STAGE not in audit or not stages.get(FIXED43_STAGE, {}).get("accepted_total_tokens"):
            if not allow_incomplete:
                raise SystemExit(f"{model}: fixed 4+3 stage has no results yet ({root})")
            print(f"{model:16s} fixed 4+3 has no stage results yet; keeping the main-table SPROUT point")
            continue
        row, a = stages[FIXED43_STAGE], audit[FIXED43_STAGE]
        complete = (verified and row["completed"] == row["tasks"] and a["audit_pending_tasks"] == 0
                    and row["accepted_total_tokens"] is not None)
        if not complete and not allow_incomplete:
            raise SystemExit(f"{model}: fixed 4+3 run is not complete and verified yet ({root})")
        resolved = a[f"{grade}_resolved"]
        points[model] = {
            "root": str(root), "grade": grade, "complete": complete, "tasks": row["tasks"],
            "resolved": resolved, "rate": round(100 * resolved / row["tasks"], 1),
            "official_resolved": a["official_resolved"], "audited_resolved": a["audited_resolved"],
            "tokens_M": (row["accepted_total_tokens"] or 0) / 1e6,
            "tokens_complete": row.get("tokens_complete"),
            "root_resolved": stages["baseline"]["resolved"],
        }
    return points
