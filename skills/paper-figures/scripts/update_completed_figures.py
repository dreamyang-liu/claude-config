#!/usr/bin/env python3
"""Publish refreshed comparison figures after an experiment and its audits finish.

Figure renderers run under ~/sprout-runs/qwen/plots-env/bin/python (the repo .venv has no
matplotlib; override with SPROUT_PLOT_PYTHON). This script itself is standard library.
"""

import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET


PLOT_PYTHON = os.environ.get("SPROUT_PLOT_PYTHON") or str(Path.home() / "sprout-runs/qwen/plots-env/bin/python")
RENDERERS = ("plot_paper_combined.py", "plot_resolve_bars.py", "plot_initial_failure_yield.py")
FIGURES = ("scaling-combined", "resolve-rate-settings",
           "initial-failed-task-recovery", "initial-failed-branch-yield")


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def readiness(root):
    controller = read(root / "controller-status.json", {})
    watch = read(root / "watch-status.json", {})
    reasons = []
    if controller.get("status") != "complete":
        reasons.append("task evaluations are not complete")
    if watch.get("status") != "complete":
        reasons.append("audit watcher has not completed")
    if read(root / "completion-audit.json", {}).get("complete") is not True:
        reasons.append("trial and restoration verification is not complete")
    if read(root / "initial-failure-yield.json", {}).get("complete") is not True:
        reasons.append("positive-sample accounting is not complete")
    config = read(root / "launch-config.json", {})
    stages = ("baseline", *config.get("schedules", {}))
    audit = read(root / "audit-comparison.json", {}).get("stages", [])
    if ({row["stage"] for row in audit} != set(stages)
            or any(row["completed_tasks"] != 113 or row["audit_pending_tasks"]
                   or row["audited_resolve_rate"] is None for row in audit)):
        reasons.append("audited task outcomes are incomplete")
    attention = (controller.get("status") in ("stopped", "needs_attention")
                 or watch.get("status") == "needs_attention")
    return reasons, attention


def collect(root, base_source):
    base = read(base_source)
    for filename, expected in base["source_sha256"].items():
        if sha(filename) != expected:
            raise ValueError(f"Historical result changed: {filename}")
    rows = {row["stage"]: row for row in base["stages"]}
    config = read(root / "launch-config.json")
    current = read(root / "scaling.json")
    audit = {row["stage"]: row for row in read(root / "audit-comparison.json")["stages"]}
    if current["model"] != base["model"] or current["tasks"] != base["tasks"]:
        raise ValueError("New results use a different model or cohort")
    baseline = next(row for row in current["stages"] if row["stage"] == "baseline")
    if baseline["accepted_total_tokens"] != rows["baseline"]["accepted_total_tokens"]:
        raise ValueError("New results use a different baseline")
    original_root = Path(rows["baseline"]["source_root"])
    if Path(config["baseline_root"]).resolve() != (original_root / "accepted/baseline").resolve():
        raise ValueError("New run did not reuse the historical baseline")
    manifests = [read(directory / "accepted/baseline/manifest-baseline.json")
                 for directory in (original_root, root)]
    for field in ("tasks", "dataset_digest", "model", "reasoning_effort", "max_turns",
                  "max_output_tokens", "command_timeout", "review_timeout",
                  "prompt_budget_chars", "backend", "store", "branch_count_mode"):
        if manifests[0][field] != manifests[1][field]:
            raise ValueError(f"Experiment configurations differ in {field}")
    for row in current["stages"]:
        if row["stage"] == "baseline":
            continue
        checked = audit[row["stage"]]
        if row["completed"] != 113 or checked["official_resolved"] != row["resolved"]:
            raise ValueError("Final metrics and audits disagree")
        schedule = config["schedules"][row["stage"]]
        rows[row["stage"]] = {
            "stage": row["stage"], "label": f"{len(schedule)}×{schedule[0]}",
            "tasks": row["tasks"], "official_resolved": row["resolved"],
            "official_resolve_rate": row["resolve_rate"], "audited_resolved": checked["audited_resolved"],
            "audited_resolve_rate": checked["audited_resolve_rate"],
            "accepted_total_tokens": row["accepted_total_tokens"],
            "accepted_branch_tokens": row["accepted_total_tokens"] - baseline["accepted_total_tokens"],
            "tokens_complete": row["tokens_complete"], "source_root": str(root),
            "series": [f"round_allocation_{sum(schedule)}"],
        }
    series = dict(base["series"])
    for budget in sorted({sum(schedule) for schedule in config["schedules"].values()}):
        grouped = sorted(
            (stage for stage, schedule in config["schedules"].items() if sum(schedule) == budget),
            key=lambda stage: len(config["schedules"][stage]), reverse=True,
        )
        reference = f"sprout-b{budget}"
        if reference not in rows:
            raise ValueError(f"Missing same-budget single-round reference: {reference}")
        series[f"round_allocation_{budget}"] = [*grouped, reference]
    if len(rows) != 13 or set(rows) != set().union(*series.values()):
        raise ValueError("Expected thirteen unique measured settings")
    sources = {Path(row["source_root"]) for row in rows.values()}
    files = [directory / name for directory in sources
             for name in ("scaling.json", "audit-comparison.json", "completion-audit.json")]
    files += [root / "initial-failure-yield.json"]
    return {
        "model": base["model"], "tasks": base["tasks"], "axes": 1,
        "x": "accepted_total_tokens / 1e9", "y": "audited_resolve_rate * 100",
        "series": series, "stages": list(rows.values()),
        "source_sha256": {str(path): sha(path) for path in sorted(files)},
    }


def publish(root, base_source, destination, state_dir):
    data = collect(root, base_source)
    version = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    build = state_dir / "builds" / version
    build.mkdir(parents=True)
    source = build / "scaling-and-rounds.json"
    write(source, data)
    output = build / "paper"
    output.mkdir()
    for renderer in RENDERERS:
        result = subprocess.run(
            [PLOT_PYTHON, str(Path(__file__).with_name(renderer)), str(source),
             "--output-dir", str(output)],
            text=True, capture_output=True, timeout=180,
        )
        (build / (renderer + ".log")).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"{renderer} failed: {result.stderr[-1800:]}")
    for name in FIGURES:
        for extension in ("pdf", "svg", "png"):
            path = output / f"{name}.{extension}"
            if not path.exists() or path.stat().st_size < 1000:
                raise ValueError(f"Missing rendered artifact: {path}")
        ET.parse(output / f"{name}.svg")
    rate_data = read(output / "resolve-rate-settings.json")
    yield_data = read(output / "initial-failure-yield.json")
    if len(rate_data["stages"]) != 13 or len(yield_data["stages"]) != 12:
        raise ValueError("Not every measured setting appears in the updated figures")
    if len(yield_data["initial_failed_tasks"]) != 61:
        raise ValueError("Failed-task denominator changed")
    for row in yield_data["stages"]:
        original = next(item for item in data["stages"] if item["stage"] == row["stage"])
        if row["audited_rescued_tasks"] + 52 != original["audited_resolved"]:
            raise ValueError("Updated task and trajectory statistics do not reconcile")
    # Check again before replacing the user-facing plots.
    if readiness(root)[0]:
        raise RuntimeError("Experiment readiness changed during rendering")
    for filename, expected in data["source_sha256"].items():
        if sha(filename) != expected:
            raise RuntimeError(f"Result changed during rendering: {filename}")
    destination.mkdir(parents=True, exist_ok=True)

    def copy(source_file, target):
        temporary = target.with_suffix(target.suffix + ".updating")
        shutil.copy2(source_file, temporary)
        temporary.replace(target)

    published = []
    for path in sorted(output.iterdir()):
        copy(path, destination / path.name)
        published.append(str(destination / path.name))
    copy(source, base_source)
    # Refresh the earlier combined-chart links as well as the latest paper figures.
    for extension in ("svg", "png"):
        copy(output / f"scaling-combined.{extension}",
             base_source.parent / f"scaling-and-rounds.{extension}")
    with (build / "scaling-and-rounds.csv").open("w", newline="") as stream:
        fields = list(dict.fromkeys(key for row in data["stages"] for key in row))
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data["stages"])
    copy(build / "scaling-and-rounds.csv", base_source.with_suffix(".csv"))
    totals = [
        {"setting": row["label"], "audited_resolved": row["audited_resolved"],
         "overall_rate": row["audited_resolve_rate"], "total_tokens": row["accepted_total_tokens"]}
        for row in data["stages"]
    ]
    write(destination / "all-settings-summary.json", {"tasks": 113, "settings": totals})
    return {"build": str(build), "published_files": published,
            "settings": len(data["stages"]), "source": str(base_source)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base-data", type=Path, required=True)
    parser.add_argument("--publish-dir", type=Path, required=True)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    root, source, destination = args.root.resolve(), args.base_data.resolve(), args.publish_dir.resolve()
    state_dir = root / "figure-update"
    state_dir.mkdir(exist_ok=True)
    status_file = state_dir / "status.json"
    with (state_dir / "update.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            while True:
                reasons, attention = readiness(root)
                if not reasons:
                    break
                write(status_file, {"status": "needs_attention" if attention else "waiting",
                                    "updated_at": time.time(), "reasons": reasons})
                if attention or not args.wait:
                    return 2 if attention else 3
                time.sleep(30)
            write(status_file, {"status": "rendering", "updated_at": time.time()})
            result = publish(root, source, destination, state_dir)
            write(status_file, {"status": "complete", "updated_at": time.time(), **result})
            print(json.dumps(result, indent=2))
            return 0
        except BaseException as error:
            write(status_file, {"status": "error", "updated_at": time.time(),
                                "error": f"{type(error).__name__}: {error}"})
            raise


if __name__ == "__main__":
    raise SystemExit(main())
