#!/usr/bin/env python3
"""Package the fixed 4+3 DeepSWE trajectories (root rollout + SPROUT branches) of the three podman
experiments for a Hugging Face dataset. Read-only on the experiment roots.

Layout (staging dir -> tar.gz):
  <model>/<task>/
    meta.json            root verdict (official, test-edit audit), SPROUT outcome
    root/                the root rollout SPROUT branched from (the experiment's fresh baseline)
    branch1/ ...         SPROUT branches in execution order: round 1 (exactly 4), round 2 (exactly 3)
    sprout/              plan-round*.json, reviews/, contexts/, summary.json
  <model>/experiment/    scaling.json, audit-comparison.json, token-breakdown.json, test-edit-audit/,
                         launch-config.json, implementation.json, program-hashes.json
  index.json, index.csv, pack.py (this script; the dataset card README.md is hand-written in the staging dir)

Each unit (root/, branchN/): journal.jsonl (the sprout journal), trajectory.atif.json (ATIF export),
trajectory.traj.json (mini-swe-agent native), model.patch, verifier/, harbor-result.json, meta.json.

Run:  python3 .claude/skills/trajectory-dataset/scripts/pack_fixed43_trajectories.py \\
          --out ~/sprout-runs/qwen/hf-stage/deepswe-fixed43-<date>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import tarfile
from collections import Counter
from pathlib import Path

# The fixed 4+3 experiments: a mirror of the paper-figures skill's fixed43.py
# (.claude/skills/paper-figures/scripts/fixed43.py), kept inline because this file ships in the
# package as pack.py and has to read standalone.
RUNS = Path.home() / "sprout-runs/qwen"
FIXED43_STAGE = "sprout-r2-b4-3"
FIXED43_ROOTS = {
    "GPT 5.6 Luna": RUNS / "deepswe-luna-rounds-4-3-20261007",
    "Kimi K3": RUNS / "deepswe-kimi-k3-rounds-4-3-20261008",
    "Claude Sonnet 5": RUNS / "deepswe-sonnet5-rounds-4-3-20261008",
}

MODEL_KEY = {"GPT 5.6 Luna": "luna", "Claude Sonnet 5": "sonnet5", "Kimi K3": "kimi-k3"}
EXPERIMENT_FILES = ["scaling.json", "audit-comparison.json", "token-breakdown.json", "launch-config.json",
                    "implementation.json", "program-hashes.json", "baseline-reuse.json", "completion-audit.json"]
UNIT_FIELDS = ["model", "task", "unit", "original_name", "round", "base", "branch_step", "status", "reward",
               "resolved", "audit_verdict", "steps"]


def read(p: Path):
    return json.loads(Path(p).read_text())


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def journal_facts(journal: Path) -> dict:
    """fork.origin record (branches), tool steps and model calls, from one pass over the journal."""
    origin, steps, calls = None, 0, 0
    with open(journal, errors="replace") as fh:
        for line in fh:
            if '"tool.finished"' in line:
                steps += 1
            elif '"raw.mini-swe-agent"' in line:
                calls += 1
            elif origin is None and '"fork.origin"' in line:
                row = json.loads(line)
                origin = {k: v for k, v in row.items() if k not in ("v", "seq", "agent_id", "sandbox_id")}
    return {"fork_origin": origin, "steps": steps, "model_calls": calls}


def copy_trial(trial: Path, out: Path, meta: dict) -> dict:
    """Copy one Harbor trial's trajectory, patch and grading into `out` and write its meta.json."""
    out.mkdir(parents=True)
    agent = trial / "agent"
    journal = agent / "trajectory.jsonl"
    files = {}
    shutil.copy2(journal, out / "journal.jsonl")
    files["journal"] = "journal.jsonl"
    if (agent / "trajectory.json").is_file():
        shutil.copy2(agent / "trajectory.json", out / "trajectory.atif.json")
        files["atif"] = "trajectory.atif.json"
    native = agent / "mini-native"
    session = None
    for traj in sorted(native.glob("*.traj.json")) if native.is_dir() else []:
        session = traj.name[: -len(".traj.json")]
        shutil.copy2(traj, out / "trajectory.traj.json")
        files["native"] = "trajectory.traj.json"
        break  # the native .jsonl log repeats the .traj.json content; it is left out (1.9 GB over the package)
    patch = trial / "artifacts/logs/artifacts/model.patch"
    if patch.is_file():
        shutil.copy2(patch, out / "model.patch")
        files["patch"] = "model.patch"
    if (trial / "verifier").is_dir():
        shutil.copytree(trial / "verifier", out / "verifier")
        files["verifier"] = "verifier/"
    if (trial / "result.json").is_file():
        shutil.copy2(trial / "result.json", out / "harbor-result.json")
        files["harbor_result"] = "harbor-result.json"
    facts = journal_facts(journal)
    meta = {**meta, "steps": facts["steps"], "model_calls": facts["model_calls"],
            "native_session_id": session, "files": files, "source_trial": str(trial),
            "journal_sha256": sha256(journal)}
    if facts["fork_origin"] is not None:
        meta["fork_origin"] = facts["fork_origin"]
    (out / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
    return meta


def audit_index(root: Path) -> dict:
    """(stage, trial path resolved) -> test-edit audit case."""
    out = {}
    results = root / "test-edit-audit/results.json"
    if results.is_file():
        for case in read(results)["cases"]:
            out[(case["stage"], str(Path(case["trial"]).resolve()))] = case
    return out


def audit_of(cases: dict, stage: str, trial: Path) -> dict:
    """Audit outcome of one resolved trial: the audit only runs on trials whose official verdict passed and
    that touched existing tests or test config; `not_flagged` means the official verdict stands as is."""
    case = cases.get((stage, str(trial.resolve())))
    if case is None:
        return {"verdict": "not_flagged"}
    return {"verdict": case["verdict"], "paths": case.get("paths"), "control": case.get("control"),
            "filtered": case.get("filtered"), "case_id": case.get("id")}


def pack_model(label: str, root: Path, stage_dir: Path, index: list) -> dict:
    model = MODEL_KEY[label]
    accepted = read(root / "accepted-sources.json")
    cases = audit_index(root)
    scaling = {r["stage"]: r for r in read(root / "scaling.json")["stages"]}
    tasks = sorted(accepted["baseline"])
    if len(tasks) != 113 or set(accepted[FIXED43_STAGE]) != set(tasks):
        raise SystemExit(f"{model}: accepted sources do not cover the 113 tasks")
    totals = Counter()
    for task in tasks:
        base_src = accepted["baseline"][task]
        base_root = (Path(base_src["task_root"]) / "baseline").resolve()
        attempts = sorted(base_root.glob("attempt-*/summary.json"))
        trials = sorted(base_root.glob("attempt-*/trials/*-parent"))
        if len(attempts) != 1 or len(trials) != 1:
            raise SystemExit(f"{model}/{task}: expected one baseline attempt under {base_root}, "
                             f"found {len(attempts)} summaries / {len(trials)} trials")
        summary = read(attempts[0])
        parent = next((a for a in summary["attempts"] if a["name"] == "parent"), None)
        if parent is None:
            raise SystemExit(f"{model}/{task}: baseline summary has no parent attempt ({attempts[0]})")
        task_dir = stage_dir / model / task
        root_meta = {"model": model, "task": task, "unit": "root", "original_name": "parent", "round": 0,
                     "status": parent["status"], "reward": parent["reward"], "resolved": bool(parent["resolved"]),
                     "audit": audit_of(cases, "baseline", trials[0]),
                     "verifier_timeout_regrade": summary.get("verifier_timeout_regrade"),
                     "baseline_attempt": base_src["attempt"]}
        root_meta = copy_trial(trials[0], task_dir / "root", root_meta)
        shutil.copy2(attempts[0], task_dir / "root" / "summary.json")
        index.append({**root_meta, "audit_verdict": root_meta["audit"]["verdict"]})
        row = {"model": model, "task": task, "root": {k: root_meta[k] for k in ("status", "reward", "resolved",
                                                                                "audit", "steps")},
               "root_source": str(base_root), "baseline_attempt": base_src["attempt"]}
        totals["root_resolved"] += root_meta["resolved"]

        sprout_src = Path(accepted[FIXED43_STAGE][task]["task_root"]) / "sprout"
        if not (sprout_src / "summary.json").is_file():
            if not root_meta["resolved"]:
                raise SystemExit(f"{model}/{task}: root unresolved but no SPROUT summary at {sprout_src}")
            row["sprout"] = {"branched": False, "reason": "root resolved"}
            (task_dir / "meta.json").write_text(json.dumps(row, indent=1, ensure_ascii=False) + "\n")
            continue
        ssum = read(sprout_src / "summary.json")
        sparent = next(a for a in ssum["attempts"] if a["name"] == "parent")
        if not Path(sparent["journal"]).resolve().is_relative_to(base_root):
            raise SystemExit(f"{model}/{task}: SPROUT parent {sparent['journal']} is not the accepted root")
        branches = [a for a in ssum["attempts"] if a["round"] > 0]
        # fork.origin names the base by its journal; map journal directories (trial dirs) to unit labels
        label_of = {Path(sparent["journal"]).resolve().parents[1]: "root"}
        name_of = {Path(sparent["journal"]).resolve().parents[1]: "parent"}
        for k, a in enumerate(branches, 1):
            label_of[Path(a["journal"]).resolve().parents[1]] = f"branch{k}"
            name_of[Path(a["journal"]).resolve().parents[1]] = a["name"]
        branch_metas = []
        for k, a in enumerate(branches, 1):
            trial = Path(a["journal"]).parent.parent
            m = re.match(r"r(\d+)b(\d+)", a["name"])
            meta = {"model": model, "task": task, "unit": f"branch{k}", "original_name": a["name"],
                    "round": a["round"], "index_in_round": int(m.group(2)) if m else None,
                    "status": a["status"], "reward": a["reward"], "resolved": bool(a["resolved"]),
                    "seconds": a.get("seconds"), "audit": audit_of(cases, FIXED43_STAGE, trial)}
            meta = copy_trial(trial, task_dir / f"branch{k}", meta)
            origin = meta.get("fork_origin") or {}
            base_dir = Path(origin["parent_journal"]).resolve().parents[1] if origin.get("parent_journal") else None
            if base_dir not in label_of:
                raise SystemExit(f"{model}/{task}/{a['name']}: base journal {origin.get('parent_journal')} is not "
                                 f"the root or an earlier branch of this task")
            meta.update(base=label_of[base_dir], base_original_name=name_of[base_dir],
                        branch_step=origin.get("branch_step"))
            (task_dir / f"branch{k}" / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
            branch_metas.append(meta)
            index.append({**meta, "audit_verdict": meta["audit"]["verdict"]})
        sp = task_dir / "sprout"
        sp.mkdir()
        for p in sorted(sprout_src.glob("plan-round*.json")):
            shutil.copy2(p, sp / p.name)
        for sub in ("reviews", "contexts"):
            if (sprout_src / sub).is_dir():
                shutil.copytree(sprout_src / sub, sp / sub)
        shutil.copy2(sprout_src / "summary.json", sp / "summary.json")
        solved = [b["unit"] for b in branch_metas if b["resolved"]]
        row["sprout"] = {"branched": True, "branches": len(branch_metas),
                         "rounds_run": sorted({b["round"] for b in branch_metas}),
                         "resolved": bool(solved), "resolved_by": solved,
                         "audit_dependent": [b["unit"] for b in branch_metas
                                             if b["resolved"] and b["audit"]["verdict"] == "depends_on_test_edits"],
                         "source": str(sprout_src.parent)}
        totals["branched"] += 1
        totals["branches"] += len(branch_metas)
        totals["branch_steps"] += sum(b["steps"] for b in branch_metas)
        totals["sprout_rescued"] += bool(solved)
        (task_dir / "meta.json").write_text(json.dumps(row, indent=1, ensure_ascii=False) + "\n")

    exp = stage_dir / model / "experiment"
    exp.mkdir(parents=True)
    for name in EXPERIMENT_FILES:
        if (root / name).is_file():
            shutil.copy2(root / name, exp / name)
    if (root / "test-edit-audit").is_dir():
        shutil.copytree(root / "test-edit-audit", exp / "test-edit-audit")
    audit = {r["stage"]: r for r in read(root / "audit-comparison.json")["stages"]}[FIXED43_STAGE]
    summary = {"label": label, "source_root": str(root), "tasks": len(tasks),
               "root_resolved": totals["root_resolved"], "tasks_branched": totals["branched"],
               "branches": totals["branches"], "branch_steps": totals["branch_steps"],
               "sprout_rescued": totals["sprout_rescued"],
               "sprout_official_resolved": audit["official_resolved"],
               "sprout_audited_resolved": audit["audited_resolved"],
               "test_edit_dependent_tasks": audit["test_edit_dependent_tasks"],
               "root_tokens": scaling["baseline"]["accepted_total_tokens"],
               "sprout_tokens": scaling[FIXED43_STAGE]["accepted_total_tokens"]}
    if summary["root_resolved"] + summary["sprout_rescued"] != summary["sprout_official_resolved"]:
        raise SystemExit(f"{model}: root {summary['root_resolved']} + rescued {summary['sprout_rescued']} != "
                         f"official {summary['sprout_official_resolved']}")
    print(json.dumps(summary), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="output directory (staging dir + tarball)")
    parser.add_argument("--name", default="deepswe-fixed43-trajectories")
    args = parser.parse_args()
    stage_dir = args.out / args.name
    if stage_dir.exists():
        raise SystemExit(f"{stage_dir} exists; remove it first")
    args.out.mkdir(parents=True, exist_ok=True)
    index, summaries = [], {}
    for label, root in FIXED43_ROOTS.items():
        summaries[MODEL_KEY[label]] = pack_model(label, root, stage_dir, index)
    rows = [{k: r.get(k) for k in UNIT_FIELDS} for r in index]
    (stage_dir / "index.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    with (stage_dir / "index.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=UNIT_FIELDS)
        w.writeheader()
        w.writerows(rows)
    (args.out / "summary.json").write_text(json.dumps(summaries, indent=1) + "\n")
    shutil.copy2(Path(__file__), stage_dir / "pack.py")
    tarball = args.out / f"{args.name}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(stage_dir, arcname=args.name)
    n_files = sum(1 for p in stage_dir.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in stage_dir.rglob("*") if p.is_file())
    (args.out / "tarball.json").write_text(json.dumps({
        "tarball": str(tarball), "sha256": sha256(tarball), "bytes": tarball.stat().st_size,
        "unpacked_bytes": size, "files": n_files, "units": len(rows)}, indent=1) + "\n")
    print((args.out / "tarball.json").read_text())


if __name__ == "__main__":
    main()
