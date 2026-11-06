# SPROUT: terms, semantics, and style reference

This file records the figure conventions that one collaboration established. It was compiled on 2026-10-16. It is a design reference. It does not replace the latest code, data, or experiment conclusions. Later changes by the user take priority.

## Which example to look at first

Open an image only when you need to match the style of that figure type. Do not load all of them by default.

- [Intro preview](examples/sprout-intro-ab-wide-jade.png): a top-bottom comparison, a wide canvas, tool cards along the line, different failed continuations, two resume points.
- [Workflow preview](examples/sprout-workflow-jade.png): three columns with light semantic fills, recovery and branching, a separate corrective-turn inset, panel labels centered below.
- [GitHub overview preview](examples/sprout-github-overview-cartoon.png): more cartoon-like icons and plant forks, compact modules, an explicit execution chain and container boundary.

Use these images to understand the layout and the visual language. Do not deliver a whole PNG as a new editable figure. Re-check every number and system detail.

## Core semantics

- A checkpoint is a pair of states: **Agent context + Environment snapshot**. The overview figure uses this abstraction level by default. Do not narrow it to a VM filesystem snapshot. Make the exact distinction only when you introduce the storage implementation.
- A checkpoint is saved at a **turn boundary**. One turn can contain several tool calls. Do not draw each tool call as a full turn.
- The agent can resume from any saved checkpoint and continue to explore. Different branches can use different checkpoints. If the mechanism allows it, a checkpoint on a branch can fork again.
- Recovery reuses the progress that is already complete. It does not re-execute the earlier actions.
- **Corrective start turn = assistant reasoning + tool call(s)**. The tool result that follows comes from the environment. Do not mix it into the assistant reasoning. The missing empty-input check in the command output is an example, not a measured conclusion about real code.
- Use **Agent context** as the one term for context in the figures. When you need to explain the shared prefix, draw the coverage range or a bracket. Do not let the removal of the word "prefix" also remove the position of the reusable progress.
- The first complete attempt is the **Original rollout**. Do not switch to "root" without a definition. In the training figure, Original and Branch stay in correspondence.
- Both successful and failed trajectories can enter the training set. Do not connect only the green successful branches to training, because that implies a wrong selection policy.

## Chosen visual conventions

- The top panel title of the intro is **"(a) Standard RL rollout"**. The bottom panel is SPROUT. Do not restore "Independent rollouts" without a request.
- Division of work between intro and workflow: the short start-turn icon stays in the intro. The detailed reasoning, commands, and tool results are in the workflow.
- In the workflow, the **Original rollout is horizontally centered in the left panel**. **(a), (b), and (c) sit centered below the outside of each panel.** The top has already been tightened.
- The three workflow section titles moved to the caption: **Checkpoint each turn**, **Review, restore & explore**, **Learn from rollouts**.
- Two branches from two different checkpoints are enough for the current workflow. Do not add a third one for "richness".
- The task uses a document or task card. Do not embed a seed with a face in the Task icon. A seed, a leaf, or a small sprout can be a light decoration for the brand, for fork growth, or near a result.
- Do not use a scratchy handwriting font. Keep rounded, slightly bold, upright text and consistent lines.
- The white intro background and the light-filled workflow are both accepted directions. Do not apply one local request to "remove the background color" to every figure type.

## GitHub system diagram conventions

- Main chain: **Task → Strategy → Run Store → Worker rollout → Verifier**. The verification feedback goes back to the strategy of later attempts. Rollouts and rewards can go into training.
- **ToolAccess is the interface to the available tools.** It is not a gate or a security check. The icon uses a connection or plug meaning.
- **Sprout runtime is inside the sandbox.** The sandbox runs on the **Podman** backend or the **Firecracker** backend. Show them as alternatives.
- Do not write "Shell runtime", and do not mark it as shell-only. The current example calls a shell. That is not the capability boundary of the runtime.
- The Sprout runtime uses a compact box. The backend options align with it at the same height. Avoid an over-long runtime box and empty corners.
- The dataset icons use the Tiny workbench series: DeepSWE is a code window with a wrench, TerminalBench is a small terminal, SWE-bench Pro is a toolbox, SWE-rebench is a task card with a refresh symbol. Keep the series. Do not switch to another metaphor set such as bugs or trophies.
- The GitHub overview can use a more visible plant growth fork. It must keep the semantics of checkpoint, direction, success and failure, and the ability to fork again.

## Existing source files on this machine (optional shortcut)

These paths belong to that collaboration. They may not exist in another environment. The skill does not depend on them. Before you modify, confirm that the current source, the exported version, and the file that the user gave you agree. Do not overwrite a file only because the name matches.

Working directory: `/Users/mliu/Documents/Codex/2026-09-26/figma-plugin-figma-openai-curated-remote-2`

| Figure | Authoring source | Export prefix |
| --- | --- | --- |
| Intro | `work/build-intro-ab-wide.py` | `outputs/sprout-intro-ab-wide-jade` |
| Workflow | `work/build-workflow-jade-aligned.py` | `outputs/sprout-workflow-jade` |
| GitHub | `work/build-github-overview-cartoon.py` | `outputs/sprout-github-overview-cartoon` |

- The current workflow authoring canvas is 1800 × 792. The body is shifted with `CONTENT_DY`. When you change a position, separate local coordinates, transformed page coordinates, and PDF points.
- In the current workflow, the horizontal spacing of C1–C4 is 145 authoring units. The gap between the C4 recovery arrow and the start-turn card is 12 units. These are regression checks for that version. They are not fixed parameters for other figures.
- `work/github-overview-flow-body.py` is a copy of the body of the GitHub builder. It is not an imported module. When you change one, check whether the other needs the same change. The actual generator is the reference.
- `work/vector_export.py` does the vector export and the fonts. fontTools for the local Python may come from `work/vector-libs`. Reuse the existing build entry point to avoid an inconsistent environment.
- This series maintains the PDF, the SVG, the PNG, and the related caption, layout, data, and source files. Update only the metadata that this change affects.

## Data and implementation boundaries

Do not hard-code old benchmark values, model names, storage ratios, or README details from the chat as default data of the skill. A new figure reads the current paper or result files and records the source. If only old material exists, state the version and the limitation.

"Environment snapshot" in the overview does not imply RAM, processes, or the full OS state. When you discuss storage mechanisms such as memory snapshot, disk-only restoration, or the clock, check the current implementation and the experiment setup. Do not infer a guarantee from a schematic figure.
