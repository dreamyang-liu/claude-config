# Design patterns and visual rules

Read the section for the current figure type. This file is a decision guide, not a fixed template. Do not force every figure to have the same partitions, colors, or branch count.

## Intro / teaser: problem and benefit

Recommended reading order: how the problem appears, which existing progress can be kept, how the method changes the later exploration, and why that is worth it.

- A comparison figure keeps a comparable scale, symbol set, and task starting point. The rollouts of the conventional method are independent attempts. Repeated preparation does not mean that every action, context, and failure position is the same.
- You can align the common preparation steps and vary the later action sequence, length, or failure position. Then the reader does not think that one trajectory was copied.
- When tool icons replace plain dots on a trajectory, keep the rollout continuous with direction arrows, small tool cards, and short labels where needed. Do not add a second row of the same floating icons.
- A checkpoint uses a symbol that differs from an action. A branch must start from a visible, explicit saved position. Two different starting points are usually enough to explain "resume from several positions". The exact count follows the mechanism.
- The failed original continuation can be de-emphasized. Keep it, because it explains the difference between recovery and new exploration. Do not draw recovery as a re-execution of steps that are already complete.
- Move detailed reasoning, commands, and tool results to the workflow figure. The intro keeps only a compact symbol for the start turn, unless the user asks to expand it.
- When the two stacked panels must fit the paper layout, first re-arrange the explanations horizontally or remove redundant titles. Do not implement an aspect ratio change as a stretch of the graphics.

## Workflow / method: causality and state boundaries

First fix the steps, the trigger conditions, the saved states, the resume positions, and where the feedback goes. Then draw the partitions.

- Use grouping to show real relations: which states belong to one checkpoint, which components are inside the run boundary, and which steps belong to one turn.
- After a failure, the order of diagnosis, checkpoint selection, writing the next action, recovery, and exploration must be explicit. Show accurately which successful and failed trajectories the training collection includes.
- When two inputs enter the reviewer, give each one its own entry space. Do not crowd several polylines at a box edge, and do not use a detour polyline to fix a misalignment that moving the box would fix.
- When a branch curve comes close to the start-turn box, leave a gap, and stop the arrowhead outside the edge. The action execution line inside the box starts separately. Check that the result does not read as one line that passes through the box.
- Use different icons for "the optimization process" and "the updated policy", for example a descending curve and a policy/agent chip. Do not let one identical network icon carry both meanings.
- When an action needs an explanation, connect a separate inset with a leader line. Separate "assistant reasoning + tool call" from "tool result returned by the environment". The example must make semantic sense.
- First-person reasoning reads more like a real assistant turn than narration does. Example: "Before I edit, I need to check for an empty-input guard." After the command returns code, a red annotation points at the gap instead of only saying "inspect". This is an example, not a real experiment trajectory.
- When the panel labels are separate from the titles, the labels can sit centered below the outside of each panel, and the titles go in the caption. Keep one baseline, and remove top white space that is no longer needed. The exact position follows the user's current instruction.

## Results: effectiveness versus resources

- First verify the model, the task set, the completion status, the method, the budget definition, and the data version. A screenshot can show the layout. It cannot replace the latest result source.
- To show the joint relation of effect and cost, a scatter plot is usually more direct than two separate bar charts: x is token consumption, y is resolve rate. If the metric directions make it so, label clearly "Upper left is better".
- If x is `% of Pass@4`, state that it is normalized to each model's own baseline. Do not read it as the absolute token cost between different models.
- One combined scatter plot can encode the method by color and the model by shape. When it is crowded, first reduce the per-point numbers and adjust the labels and the legend. Then consider one small-multiple panel per model. Small multiples keep the same axis ranges and semantics.
- When four models go in one row, use a shared axis title and legend, so that the figure stays readable when it is reduced. Do not let long model names squeeze into the plot area.
- Do not distinguish Pass@1 from Pass@4 with two similar blue-grey colors only. A hollow circle versus a filled square, with different lightness, is usually clearer than color alone. When you highlight SPROUT, keep the comparison methods readable.
- Label only the key points and the key differences. A percentage saving is usually more direct than a large absolute token count. Whether to keep it depends on the information density of this figure.
- Reduction formula: `100 × (baseline_tokens − method_tokens) / baseline_tokens`. If x in the figure is already normalized, the saving is `100 − normalized_cost`. State the comparison target. Do not mix percentages and percentage points.
- A bar chart of positive values usually starts from zero, so that the bar length differences are not exaggerated. A scatter or line plot can narrow the axis range when that has an explanatory meaning. Then show the ticks clearly, and do not hide the baseline.
- When the user asks for a bar chart version, keep the model order, the method colors, the units, and the significant digits. Do not let a layout change also change the definition of the comparison.

## Storage / systems analysis: cost breakdown and boundaries

- Use a composition chart for real storage components such as memory, disk, and metadata. Stack only quantities that add up, and use one unit such as GiB or TiB.
- Explain storage cost, recovery semantics, and task effectiveness separately. A storage reduction does not by itself prove that recovery is equivalent, that runs are faster, or that effectiveness is unchanged.
- State whether the mechanism is a full memory snapshot, a persisted environment state, or another recovery mechanism. Do not treat the abstract names of the overview figure as implementation guarantees.
- When one figure shows composition, effect, and the recovery mechanism, let each panel answer one question. Put the long technical explanation in the body text or the caption.

## GitHub overview: a friendly and formal system diagram

The README reader needs to understand the main flow first, then the component details.

- The title says first what the project helps the reader do, then one short sentence explains the mechanism. Do not only list internal module names.
- The main flow connects task, strategy, queue or storage, worker, verification, and feedback clearly. Component diagrams sit under their stage. They do not compete with the main flow for reading order.
- Containment must be accurate. The runtime is drawn inside the sandbox. Different backends are alternative implementations, not sequential steps. Use compact sub-modules with one height to remove large meaningless white space.
- The tool interface uses a plug or tool connector symbol. Do not use a shield, which reads as a security gate.
- A mascot, a plant fork, or a tiny workbench can be livelier than in a paper figure, but the checkpoint, the action direction, and the failure and success markers stay explicit. Cuteness comes from geometry and small details, not from a screen full of faces.
- Keep the original logo and the icon series that the user selected: the same line weight, corner radius, and fill. Do not switch to a new set at each edit.

## Default visual parameters

These are the starting point of this series. They are not a mandatory palette for other brands.

| Use | Example color |
| --- | --- |
| Body text, dark | `#22333A` |
| Secondary text | `#596971` |
| Saved state, existing progress | `#5B748C` |
| SPROUT, new exploration, success | `#267F6B` |
| Guidance or corrective action | `#A76B3B` |
| Failure or defect | `#B86B68` |
| Borders | `#DFE6EA` |
| Light fills for checkpoint / exploration / training | `#F4F7FA` / `#FCFAF7` / `#F2F8F5` |

For text, Nunito 600/700/800 is an option. For code, IBM Plex Mono 500 is an option. Set the font sizes for the target print size. Do not take the px values of the authoring canvas as the final paper font size. Embed the fonts in the SVG, or also export a version with text converted to paths. Keep the font licenses.

## Common failures and targeted fixes

| Observed problem | Direction of the fix |
| --- | --- |
| The three rollouts look identical | Keep the alignment of the repeated work. Change the actions and the failure positions of the continuations. |
| One icon set on the line and another above it | Keep one set. Prefer the icons as the action nodes. |
| After "simplification", the mechanism is gone | Restore the key states, boundaries, and trigger relations. Remove the minor decoration. |
| "Cute" turned into a scratchy font | Use a slightly bold, upright, rounded font. Use cartoon elements only as a few semantic decorations. |
| A seed stands for the task and misleads | Use a task document or task card. Use the plant for growth or success metaphors. |
| The background boundary looks like a half block of color cut off | Align the semantic partitions and the boundary, and unify the outer outline. Or color the icons instead. |
| Arrows crowd at a box edge or enter the action box | First re-arrange the entry points and the white space. Then choose a straight line or a smooth curve. |
| Multi-model scatter labels pile up in one corner | Reduce the labels and place leader lines. When the labels still collide, split into small multiples with one scale. |
| Everything has a bold title or a color block | Keep only the main hierarchy. Group the secondary explanations with normal text and space. |
| The PNG changed but the paper PDF is still old | Regenerate the related formats from the same source, and check the final export. |
