---
name: paper-figures
description: Regenerate the SPROUT paper figures and main-table rows (front figure, scaling-vs-Pass@k teaser, branch-scaling/round-allocation figure, resolve bars, initial-failure yield, fixed 4+3 table rows) from the verified DeepSWE experiment roots under ~/sprout-runs/qwen. Read-only on the experiments; writes to <repo>/figures or a root's plots/paper. Needs the plots-env interpreter (the repo .venv has no matplotlib).
---

# Paper figures

Every renderer reads two data files -- the verified Luna scaling comparison and the Luna
Pass@k curve -- plus the three fixed 4+3 roots (`scripts/fixed43.py`), checks the
`source_sha256` of every experiment file it depends on (and refuses to draw if one changed),
and writes a JSON sidecar naming its inputs; the combined/bars/yield plots also record
`plot_program_sha256` of the script itself.

## Interpreter

`~/sprout-runs/qwen/plots-env/bin/python` (Python 3.12, matplotlib 3.11.2) for every
`plot_*.py` and for `fixed43_table_rows.py` (it imports the table data module, which imports
matplotlib). The repo `.venv` has no matplotlib. `/tmp/sprout-plots-env` is only a symlink to
plots-env and is gone after a reboot. `update_completed_figures.py` and
`subsample_single_round.py` are standard library and run the renderers themselves under
`PLOT_PYTHON` = that path (override with `SPROUT_PLOT_PYTHON`). `fixed43.py` is standard library.

## Inputs

- `SCALING=~/sprout-runs/qwen/deepswe-luna-rounds-20261005/plots/scaling-and-rounds.json`:
  13 stages (baseline; 1x1..1x32, a nested subsample with seed 42; 8x1, 4x2, 2x4, 4x1, 2x2, 2x1),
  series `single_round`, `round_allocation`, `round_allocation_2`, `round_allocation_4`,
  `single_round_sampling`. Its `source_sha256` names files under
  `deepswe-luna-scaling-20261004`, `-rounds-20261005` and `-rounds-small-20261005` (by the
  names those directories had before 2026-10-10, which remain as symlinks).
- `PASSK=~/ash-data/preparation/three-bench-candidate-20260923/full/deepswe-luna-pass8-campaign-20261007T0740Z/luna-passk-curve.json`
- Fixed 4+3 roots (`fixed43.py`: `FIXED43_ROOTS`, stage `sprout-r2-b4-3`):
  `~/sprout-runs/qwen/deepswe-luna-rounds-4-3-20261007`, `deepswe-kimi-k3-rounds-4-3-20261008`,
  `deepswe-sonnet5-rounds-4-3-20261008`; each needs `scaling.json`, `audit-comparison.json`, a
  complete `completion-audit.json`, `accepted-sources.json` and `accepted/`.
- Hand-typed constants: `plot_tokens_vs_resolve.DATA` (the main table: Pass@1 / Pass@4 / BPO /
  Shepherd / SPROUT per model) and `plot_front_figure.RL_*` (the RL bars). The fixed 4+3 points
  replace `DATA[model]["SPROUT"]` for Luna, Kimi K3 and Sonnet 5 (`use_fixed43`); Qwen keeps the
  table value.

## Scripts

`PY=~/sprout-runs/qwen/plots-env/bin/python`, `S=.claude/skills/paper-figures/scripts`, from the
repo root. Repo-local outputs go to `figures/` (gitignored).

| Command | Writes |
|---|---|
| `$PY $S/plot_front_figure.py $SCALING $PASSK` | `figures/front-figure.{png,pdf,svg,json}`. `--layout {two,grid,row}` (grid/row add the scaling panel and a `-grid`/`-row` suffix), `--left {all,qwen}` (`front-figure-qwen`), `--sprout-source {fixed43,table}` (`-table`), `--grade {official,audited}`, `--allow-incomplete` (`-preview`), `--output-dir DIR` |
| `$PY $S/fixed43_table_rows.py [--grade official] [--output FILE]` | `figures/fixed43-table-rows.json`: per model the rate, official/audited resolved, recovery vs the table's Pass@1 and vs its own root, steps (`tool.finished` events over the accepted journals), tokens |
| `$PY $S/plot_tokens_vs_resolve.py` | `figures/tokens-vs-resolve.{png,pdf}` (the four-panel form of panel (a)); also the `DATA` module |
| `$PY $S/plot_teaser.py` | `figures/teaser.{png,pdf}`: the relative-to-Pass@4 design with hand-copied Luna numbers; kept until the design decision is made (the front figure reads them live) |
| `$PY $S/plot_teaser_scaling.py $SCALING $PASSK [--output-dir DIR] [--linear] [--grade audited]` | `DIR/scaling-teaser[-linear].{pdf,svg,png,json}` + `-caption.md`; DIR defaults to `<dir of SCALING>/paper` |
| `$PY $S/plot_scaling_linear.py $SCALING $PASSK [--output-dir DIR] [--grade G] [--no-reported] [--no-level-text]` | `DIR/scaling-linear[-audited].{pdf,svg,png,json}` + `-caption.md`: linear token axis; a star at the Luna fixed 4+3 point (`fixed43.py`, the reported configuration); solid k×1 (green), long-dashed 1×k (blue), solid Pass@1..8 (grey), legend inside at lower right; dashed equal-budget lines, one colour and legend entry each (8: 8×1-4×2-2×4-1×8 orange, 4: 4×1-2×2-1×4 red; 2×1 and 1×2 are left unjoined); a grey dashed horizontal line at the Pass@8 rate from the y axis to Pass@8, the Pass@8 label carries its rate and 1×32 is followed by its rate and token saving; DIR defaults to `<dir of SCALING>/paper` |
| `$PY $S/plot_paper_combined.py $SCALING [--passk $PASSK] [--grade G] [--output-dir DIR]` | `scaling-combined[-passk].{pdf,svg,png,json,tex}`, `scaling-combined-caption.md` |
| `$PY $S/plot_resolve_bars.py $SCALING [--output-dir DIR]` | `resolve-rate-settings.{pdf,svg,png,json}` + caption |
| `$PY $S/plot_initial_failure_yield.py $SCALING [--output-dir DIR]` | `initial-failed-task-recovery.*`, `initial-failed-branch-yield.*`, `initial-failure-yield.{json,csv,md}` (re-reads every accepted task file and audit; slow) |
| `python3 $S/update_completed_figures.py --root ROOT --base-data $SCALING --publish-dir DIR [--wait]` | after a rounds root completes: merges its stages into the base data, renders the three paper figures under `ROOT/figure-update/builds/<ts>/paper`, validates, publishes to DIR and rewrites the base data; exit 2 = needs attention, 3 = not ready |
| `python3 $S/subsample_single_round.py --root ~/sprout-runs/qwen/deepswe-luna-scaling-20261004 --base-data $SCALING --output DIR [--seed 42] [--render]` | the nested 1xk points (`selection.json` is frozen: another seed or population against an existing selection raises) and with `--render` the figures under `DIR/paper` |
| `$PY $S/plot_scaling_and_rounds.py --single-round-root R1 --multi-round-root R2 --output-dir FRESH` | bootstrap only: the first (10-stage) `scaling-and-rounds.{json,csv,svg,png}` for a brand-new pair of roots |

The published paper directory is `~/sprout-runs/qwen/deepswe-luna-rounds-20261005/plots/paper`
(`scaling-combined*`, `resolve-rate-settings*`, `initial-failed-*`, `scaling-teaser*`,
`single-turn-*`). `figures/` holds the renders made before the move (front-figure, the
`-table`/`-qwen`/`-preview` variants, teaser, tokens-vs-resolve, `fixed43-table-rows.json`) and
`image.png`, the user's design mock-up of panel (a).

## Pitfalls

- Source hashes are strict: a change to any listed experiment file makes every renderer refuse.
  Program hashes are informational: moving or editing a script changes `plot_program_sha256` in
  new sidecars, and old sidecars stop matching the script on disk (expected).
- `--allow-incomplete` names the output `front-figure-preview.*` and records which models were
  complete; never ship a `-preview` file (`figures/front-figure-preview.*` is from when only Luna
  was complete).
- Grade: default `official` (verifier verdicts, as Pass@k); `--grade audited` uses the test-edit
  audit, and the captions say which.
- Never point `plot_scaling_and_rounds.py` at a root's published `plots/`: it writes the 10-stage
  original over the 13-stage file every other renderer reads (hence `--output-dir` is required).
- `update_completed_figures.py` and `plot_initial_failure_yield.py` hard-code the Luna cohort
  (113 tasks, 61 initially failed, 52 baseline successes; 13 settings, 12 yield stages) and the
  reused 2026-10-04 baseline; they do not fit the Sonnet/Kimi roots without edits.
- The teaser/combined renderers raise "Text extends beyond the figure" when a label leaves the
  canvas: adjust the offset tables rather than enlarging the figure silently.
- Nothing here launches a model call or writes into an experiment root except
  `update_completed_figures.py`'s own `figure-update/` directory and the publish directory.

## Tests

`env -u FORCE_COLOR NO_COLOR=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/ops/test_subsample_single_round.py tests/ops/test_fixed43.py`
(the nested sampler, and that the trajectory-dataset packer mirrors `fixed43.py` without matplotlib).

## Dropped when the scripts moved here (2026-10-09)

- `ops/plot_round_allocation.py` (S2-01): first-generation round-allocation plot, superseded
  by `plot_scaling_and_rounds.py` and then `plot_paper_combined.py`; it could read only the
  2026-10-05 Luna root.
- `ops/plot_paper_scaling.py` (S2-02): asserted exactly 10 stages, so it cannot run against the
  13-stage data; `plot_paper_combined.py` is the successor.

Both are archived with their outputs in
`~/sprout-runs/qwen/deepswe-luna-rounds-20261005/plots/superseded-scripts/`.
