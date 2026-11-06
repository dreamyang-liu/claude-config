---
name: trajectory-dataset
description: Package the fixed 4+3 DeepSWE trajectories (root rollout + SPROUT branches, three models) for the Hugging Face dataset and run the branch-turn analysis pipeline (fork position, continuation labels, token cost, verified statistics). Read-only on the experiment roots; standard-library Python only (python3, no sprout import, no matplotlib).
---

# Trajectory dataset and branch-turn analysis

`pack_fixed43_trajectories.py` copies, per model and task, the accepted root trial and every
SPROUT branch trial (`journal.jsonl`, `trajectory.atif.json`, `trajectory.traj.json`,
`model.patch`, `verifier/`, `harbor-result.json`, `meta.json` with fork origin, base, branch
step and audit verdict) plus `sprout/plan-round*.json`, `reviews/`, `contexts/`, `summary.json`
and the experiment-level JSONs, writes `index.json`/`index.csv` and `summary.json`, copies itself
in as `pack.py`, and tars the staging directory. The analysis scripts read only that package and
write under one analysis directory.

## Interpreter

`python3` (standard library; 3.9+ for `Path.is_relative_to`). No sprout import, no matplotlib.
`pack.py` ships inside the dataset, so the packer carries its own copy of the fixed 4+3 roots
(the master list is `.claude/skills/paper-figures/scripts/fixed43.py`;
`tests/ops/test_fixed43.py` pins the mirror and the standalone property). The HF upload runs
under `~/ash-data/venv/bin/python` (huggingface_hub) and is run by the user.

## Inputs

The three fixed 4+3 roots under `~/sprout-runs/qwen`: `deepswe-luna-rounds-4-3-20261007`,
`deepswe-kimi-k3-rounds-4-3-20261008`, `deepswe-sonnet5-rounds-4-3-20261008` (stage
`sprout-r2-b4-3`): `accepted-sources.json`, the accepted trial directories,
`test-edit-audit/results.json`, `scaling.json`, `audit-comparison.json`, `token-breakdown.json`,
`launch-config.json`, `implementation.json`, `program-hashes.json`, `baseline-reuse.json`,
`completion-audit.json`.

## Scripts

`S=.claude/skills/trajectory-dataset/scripts`,
`PKG=~/sprout-runs/qwen/hf-stage/deepswe-fixed43-20261008/deepswe-fixed43-trajectories`,
`OUT=~/sprout-runs/qwen/analysis/fixed43-branch-turns-20261008`. Run in this order.

| Command | Writes |
|---|---|
| `python3 $S/pack_fixed43_trajectories.py --out ~/sprout-runs/qwen/hf-stage/deepswe-fixed43-<date> [--name deepswe-fixed43-trajectories]` | `<out>/<name>/` (`luna/`, `sonnet5/`, `kimi-k3/`, `index.json`, `index.csv`, `pack.py`), `<out>/summary.json`, `<out>/<name>.tar.gz`, `<out>/tarball.json` (sha256, bytes, files, units) |
| `python3 $S/extract_branch_turns.py --package $PKG --out $OUT` | `$OUT/<model>/<task>__branchN.json`, `$OUT/branches.jsonl` (position, continuation length, reviewer turn and observations, analyst report, verdict) |
| `python3 $S/branch_turn_stats.py $OUT` | `stats.json`, `stats.md` (fork position / continuation length by model, round, outcome) |
| `python3 $S/extract_continuation_turns.py --package $PKG --out $OUT` | `$OUT/continuations/{<model>/..., continuations.jsonl, continuation-stats.md, continuation-stats.json}`: every actor turn after the reviewer turn, labelled lexically (edit / test / lint / probe / git / inspect / submit); needs `branches.jsonl` |
| `python3 $S/branch_turn_token_cost.py --package $PKG --analysis $OUT` | `turn-token-cost.md`, `turn-token-cost.json`: analyst/reviewer call tokens amortised per branch against the actor's per-turn tokens; needs `branches.jsonl` |
| `python3 $S/branch_turn_verified_stats.py $OUT` | `verified-stats.md`, `verified-stats.json`, `branch-list-<model>.md`, `branch-list.csv` (Mann-Whitney, Fisher, Spearman, sign test); needs `branches.jsonl` and `continuations/continuations.jsonl`, uses `classifications.json` if present |
| user only: `~/ash-data/venv/bin/python ~/sprout-runs/qwen/hf-stage/deepswe-fixed43-20261008/upload.py` | the private dataset `mliu444/sprout-deepswe-fixed43-trajectories` (card, index, pack.py, summary.json, tarball); asserts `tarball.json` bytes == tarball size |

The current package is `~/sprout-runs/qwen/hf-stage/deepswe-fixed43-20261008` (826 MB tarball,
7.6 GB unpacked, 21,743 files, 1,142 units). The analysis lives in
`~/sprout-runs/qwen/analysis/fixed43-branch-turns-20261008/`; its `REPORT.md` is hand-written,
and `classifications.json`, `workflow1-*.json`, `workflow2-*.json`, `ids.json`, `lexical.md`
and `continuation-turns-hist.*` come from LLM labelling workflows outside this skill.

## Pitfalls

- The HF upload must be run by the user (credentials, an 826 MB push), never by an agent;
  `upload.py` lives in the staging directory, not in the repo.
- `pack` refuses an existing staging directory ("remove it first"). The dataset card `README.md`
  there is hand-written and would go with it: copy it out before re-packing and put it back (its
  sha256 line comes from `tarball.json`). The packer writes no README.
- Keep `pack_fixed43_trajectories.py` standard-library and self-contained: it ships as `pack.py`.
- The first packing attempt, `~/sprout-runs/qwen/hf-stage/deepswe-fixed43-trajectories-20261008`
  (with `mini-native.jsonl`, 208 MB), is superseded; do not reference it.
- Step counts are textual: a journal line containing `"tool.finished"` is one step and
  `"raw.mini-swe-agent"` one model call (the same rule as the paper-figures
  `fixed43_table_rows.py`).
- A branch journal numbers its steps from 1 at the reviewer turn; `fork_step_absolute` = the
  base's fork step + its own step (round-2 branches fork off a round-1 branch).
- `MODELS` / `MODEL_KEY` are hard-coded (luna, sonnet5, kimi-k3); a fourth model needs edits in
  the packer and every analysis script.
- `branch_turn_verified_stats.py` hard-codes the 90-branch re-rating agreement numbers and the
  hypotheses verified for the 2026-10-08 report: it is that report's reproducible appendix, not
  a generic tool.
- Read-only on the experiment roots; every write goes under `--out` / `--analysis`.

## Tests

`env -u FORCE_COLOR NO_COLOR=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/ops/test_fixed43.py`
(the packer imports without matplotlib and mirrors `fixed43.py`).
