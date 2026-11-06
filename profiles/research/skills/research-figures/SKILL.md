---
name: research-figures
description: Draws and iterates research figures: paper intro/teaser figures, method workflow figures, experiment result plots, system architecture diagrams, and GitHub project overview diagrams. Use it to make clear, vector-first scientific figures from a paper, code, data, or an existing draft, in particular for detail edits that keep the existing structure, a restrained cartoon style, and color and layout refinement. Not for general illustration, website UI, or full slide deck design.
---

# Research Figures

Organize the research content into a figure that the reader understands at first sight. Then support a close reading with an accurate structure, little text, and one consistent visual language. The defaults below come from one long-running figure collaboration. The user's current request and the template of the target journal or conference take priority over them.

## Decide what the figure must show

- Extract one core message from the request, the current draft, and the paper, code, or data that you need. Then extract two to four visual facts that support it. Understand the mechanism before you choose the graphic form. Do not use decoration to cover a relation that you do not yet understand.
- Separate schematic from measured. If the path lengths, branch counts, or checkpoint positions are schematic, do not present them as experiment data. In a quantitative figure, each number, unit, denominator, and comparison condition must have a source.
- Use the information that you already have. Ask only when a missing fact changes the meaning of the figure, the data, or the delivery format. Decide ordinary spacing, line widths, and icon choices yourself.
- When the user says "keep the overall structure", treat the partitions, the reading order, the key comparisons, and the data as fixed. Fix one label. Do not restructure the whole figure at the same time.
- Start from the most recently accepted version. Do not continue a direction that the user later withdrew. When the user cancels a side task, for example a slide deck, do not continue that side task.

## Organize by purpose

Read [Design patterns and visual rules](references/design-patterns.md) when you need it, and use only the relevant section:

| Purpose of the figure | Main task | Content that usually goes elsewhere |
| --- | --- | --- |
| Intro / teaser | Let the reader see the problem and the core benefit | the full execution flow, code examples, implementation details |
| Workflow / method | Let the reader understand how states, actions, feedback, and learning connect | long explanations of the principle, experiment conclusions |
| Results / storage analysis | Show the differences accurately under one comparison condition | large mascots, promotional phrases about the mechanism |
| GitHub overview | Build an overall picture of the task flow, the execution boundary, and the component relations | every config option, every function, every implementation branch |

When one figure carries too many tasks, split it into a mechanism figure and a results figure. Do not shrink every element instead. When the user asks to merge figures or to keep the partitions, solve the problem inside that constraint first.

When the work involves SPROUT, or the user asks you to continue the style of that collaboration, read [SPROUT terms and accepted examples](references/sprout.md). Do not apply its system details to an unrelated project.

## Visual decisions

- **Semantics first, then icons.** An icon stands for a task, an operation, a state, storage, or training. Do not replace it with a cuter symbol that changes the meaning.
- **Keep the explanatory power.** Remove repeated text. Do not remove the conditions, the state pairs, the branch origins, or the result feedback that the reader needs to follow the flow. Less text does not mean a few empty boxes.
- **Show actions along the line.** A tool icon on a rollout can replace a dot. Keep "sequential execution" readable with connectors, direction, and turn grouping. Do not draw the same icon set both on the line and above it.
- **Give the text a hierarchy.** By default, use a slightly bold, upright, clear typeface. Friendliness comes from rounded letterforms and a few illustrations, not from a scratchy handwriting font or italics. Use a monospace font for code.
- **Keep the lines in order.** Lines with the same meaning have the same width, arrowhead, and spacing. Prefer a direct arrow where one is possible. A natural fork can use a smooth curve. Do not read "make it straight" as "turn every branch into right-angle polylines".
- **Let color carry a role.** The method, reuse or success, failure, and corrective actions each get one stable semantic color. Use a background only when it helps grouping. White space, light fills, and icon colors can also carry hierarchy. Do not force every figure to have, or not have, a background.
- **Keep cartoon elements restrained.** A small sprout, a leaf, or a light character can echo the project name. The core flow, the numbers, the text, and the connectors stay editable vectors. When the user says "animated elements", they may mean cartoon visuals. Do not make a motion animation unless they ask for one.
- **Design for the final size.** Check the fonts and the line widths at the paper column width or the README display width. When the figure must become wider and shorter, re-arrange the content. Do not stretch the image horizontally, and do not shrink all the text.

## Build and modify

1. Locate the real source file, the generator script, and the current exports. Do not treat a screenshot as the only editable source. If only a screenshot exists, you can rebuild from it, but separate a reproduction from a new design.
2. Choose the implementation that fits the delivery. Use a vector tool such as SVG or Figma for a schematic. Use a standard plotting library for experiment curves and scientific plots. When a vector source exists, edit that source. Do not redraw the whole figure with image generation. Generate a bitmap only for a separate, complex cartoon decoration that the figure needs, and say which parts are bitmaps.
3. When you use Figma, PDF, image generation, or presentation tools, load the matching skill that is available at that time, and follow its operating and delivery rules. Do not claim that the canvas is synchronized when you did not write to Figma.
4. Before you modify, state what stays and what changes. Keep a recoverable version before a large change. When the user asks only for a text or alignment change, keep the other geometry and content unchanged.
5. When the user asks for several options, give real differences in reading structure, icon metaphor, or information density. A color comparison keeps the geometry the same. A layout comparison keeps the facts the same. Then the user can tell where each difference comes from.
6. Divide the work between the in-figure text and the caption. The figure labels the necessary objects, actions, and results. The caption explains the panels, the mechanism, and the boundaries. When a change affects an existing caption, glossary, or legend, update it in the same change.

## Export and acceptance

Deliver by purpose. A paper figure is usually a vector PDF, an editable SVG, and a PNG preview. A GitHub figure is usually a self-contained SVG and a PNG. Keep the established file names and output locations. Do not create a format that the user did not ask for.

- Generate the related outputs from one source. Separate clearly an SVG that keeps live text from an SVG with text converted to paths. Converting to paths avoids font substitution, but the text is no longer editable.
- Render the final file and check it. Look for clipped text, label collisions, crowded arrows, gaps between icons and connectors, branch origins, edge margins, background boundaries, and readability.
- Check the key facts and geometry from the source to the output: names, numbers, denominators, success and failure mapping, state pairs, equally spaced objects, and the page boundary. For a small change, run only the related checks. Do not grow the check into an unrelated test project.
- Look at the whole figure and at the changed area. Check it once at the target display size. Two similar colors in a legend must not be the only way to tell items apart.
- In a quantitative figure, check the precision, the tick marks, the units, the comparison range, and the formula. Do not copy "latest data" from an old screenshot.
- If rendering or compilation fails, fix it or state the limitation clearly. A successful write of the source file does not mean that the export is verified.

Before you deliver, run `python3 scripts/svg-check.py --summary <svg>`. The script reports these items for each SVG:

- the viewBox
- the font families
- the font size range
- the colors, with the colors that are not in the default palette
- embedded bitmaps

The script cannot judge whether the figure says the right thing. You still render the figure and check it by eye.

When you deliver, give the user the finished figure and the file links that they need, and one sentence that states what changed. Say "updated" or "verified" only when that is true. Do not describe a local export as a remote publication. When you provide a caption, give TeX that the user can paste, as the user requests.

## Files

- `scripts/svg-check.py`: the SVG check script. After you change the script, run `python3 scripts/svg-check.py --selftest`.
- `references/design-patterns.md`: design patterns by figure purpose, the default visual parameters, and common failures with their fixes.
- `references/sprout.md`: the terms, semantics, and accepted conventions of the SPROUT figure series, with example renders in `references/examples/`.
