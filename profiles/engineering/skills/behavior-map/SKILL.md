---
name: behavior-map
description: Method and tool for discussing requirements and architecture with the user, grounded in real user behavior. List the behaviors of real actors (actor, goal, trigger, outcome, steps, source), allocate each step to the major component that handles it, then decompose a component into subcomponents and allocate its steps again. Each component must trace to a step of a real behavior. Draws an interactive scratch HTML page from assets/behavior-map.html (an actor lane plus a swimlane per component for each behavior and extension, zoom into a component, a component tree with trace counts, a trace matrix, automatic trace checks), then renders and checks it with scripts/render.sh (headless Chrome, PNG and check report). Use it whenever you discuss a feature, a requirement, a design or an architecture change with the user, or before a change that touches more than one major component.
---

# Behavior map

An architecture is correct only for the behaviors that it serves. So a design discussion starts
from what a real actor does, not from the components. The map shows three things, in this
order:

1. the behaviors of the actors, step by step
2. the component that handles each step
3. the parts inside one component, with the steps that each part handles

Each component on the map must handle at least one step of a real behavior. If a component
handles no step, either a behavior is missing or the component is not needed.

The method comes from these sources:

- A. Cockburn, *Writing Effective Use Cases* (Addison-Wesley, 2000): an actor with a goal, a main
  scenario, and extensions that start at a step
- I. Jacobson et al., *Object-Oriented Software Engineering: A Use Case Driven Approach*
  (Addison-Wesley, 1992): use cases drive the design, and each step of a use case is allocated to
  the objects that handle it
- S. Brown, the C4 model (https://c4model.com): zoom from the large parts of a system into the
  components of one part

## When to use it

- The user discusses a requirement, a feature, a design or an architecture change.
- A change touches more than one major component.
- The user asks how a flow works from end to end.

Do not use it for a fix inside one component. Do not use the scratch page as a figure in
`docs/`. After a decision, draw the final figure as SVG, as the doc-writing skill says.

## Workflow

Do these steps in order:

1. **Collect the behaviors.** For each behavior, write these fields:
   - the actor: a person or a program outside the system, such as an experiment script or the
     RL trainer
   - the goal: what the actor wants, at the level of one sitting. "Run one task as a rollout and
     get its result" is a goal. "Press enter" is too small. "Do the research" is too large.
   - the trigger: the situation that starts the behavior
   - the outcome: what the actor has at the end
   - the source: where the behavior comes from. Use the user's words with the date, a CLI
     command, an API endpoint, a section of `docs/`, a code path or a run log.

   If a behavior has no source, ask the user. Do not invent a behavior.
2. **Write the main scenario.** Write 3 to 15 steps. Each step is one action of the actor, or
   one response of one component. Write each step with a verb first, such as "claims the job".
3. **Write the extensions.** An extension is a condition that the actor can see, such as a
   failure, a timeout or a stop. It starts at one step of the main scenario. Write only the
   extensions that matter for the decision.
4. **List the major components.** Use 3 to 7 top-level components: processes, services, or
   top-level packages. For an existing component, give its code path from the current tree. For
   a proposed component, set its status to `new`, `changed` or `removed`.
5. **Allocate each step to one owner.** The owner is the component that does the work of the
   step, or `actor` for a step that the actor does. If a step needs two components, split the
   step. For each step, write the `message`: the call, the request or the event that hands
   control to the step, such as `POST /v1/jobs`.
6. **Render and check the map.** Run `scripts/render.sh` (see [Files](#files)). Fix each
   problem in the report:
   - A step without an owner: allocate it.
   - A component without a step: find the real behavior that needs it, or remove the component.
     Do not add a behavior only to keep a component.
7. **Decompose only the component under discussion.** Add its subcomponents as `children`. Then
   allocate each step of that component to one child, in each behavior. The check reports each
   step that still names the parent. Decompose a child the same way, if the discussion needs it,
   down to the level of modules.
8. **Look at the views that matter.** Render each behavior and each zoom level that the
   discussion uses. Read each PNG. Check that no text overlaps and that each arrow goes from
   one step to the next.
9. **Discuss with the map.** Refer to the step numbers and the component names. After each
   decision, update the model and render it again. Change the behaviors first, then the
   components.
10. **Check the decisions.** When the discussion ends with a decision, apply the
    architecture-decisions skill. Copy the behaviors and the allocation that the decision
    depends on into the ADR, because `scratch/` is not tracked.

## Rules

- **Start from the behavior.** Do not draw components before the behaviors exist.
- **Keep each behavior real.** Each behavior has a source. Each existing component has a code
  path that you checked in the current tree.
- **One owner for each step.** Allocate a step to the deepest component that the map shows.
- **No orphan component.** Each component, at each level, handles at least one step. A
  component with the status `removed` is the only exception.
- **Show what changes.** Mark each proposed component and each proposed step as `new`,
  `changed` or `removed`. Leave the status out for an existing one.
- **Keep one level of detail in a behavior.** Write the steps at the level of the finest
  decomposition that the discussion needs. In a coarser view, the page joins the consecutive
  steps of one component into one box.

## Files

1. Copy `assets/behavior-map.html` to `scratch/<topic>/behavior-map.html`. `scratch/` is in
   `.gitignore`, and `CLAUDE.md` puts drafts there.
2. Replace the JSON in `<script type="application/json" id="model">`. Do not edit the rest of
   the page. If the page needs a new feature, change the template in this skill.
3. Render and check:

   ```bash
   .claude/skills/behavior-map/scripts/render.sh scratch/<topic>/behavior-map.html
   .claude/skills/behavior-map/scripts/render.sh scratch/<topic>/behavior-map.html 'behavior=<id>&focus=<component id>' 2000x2600
   ```

   The script writes a PNG next to the HTML and prints the check report. It exits 0 when the
   report starts with `OK`, 1 when it lists problems, and 2 when it finds no headless Chrome.
   It uses the Playwright build under `~/.cache/ms-playwright`, or the binary that `CHROME`
   names.
4. Tell the user the path of the HTML file, so that they can open it in a browser.

The model in the template is an example: the Run Store submit and branch behaviors, from
`docs/RUNSTORE.md` and the `src/` layout of 2026-10-16. Check it against the code before you
reuse any part of it.

## Model

```json
{
  "title": "the subject of the map",
  "question": "the decision under discussion",
  "drawn_from": "the sources of the whole map",
  "components": [
    {"id": "worker", "name": "Worker", "code": "src/sprout/worker/", "children": [
      {"id": "worker.run", "name": "run orchestrator", "code": "src/sprout/worker/run/runner.py"},
      {"id": "worker.cache", "name": "result cache", "status": "new"}
    ]}
  ],
  "behaviors": [
    {"id": "submit", "actor": "...", "goal": "...", "trigger": "...", "outcome": "...", "source": "...",
     "steps": [
       {"id": "claim", "owner": "worker.run", "message": "the call into this step", "text": "claims the job"},
       {"owner": "actor", "message": "...", "text": "picks a point"}
     ],
     "extensions": [
       {"at": "claim", "condition": "the claim fails", "outcome": "optional", "steps": [ ... ]}
     ]}
  ]
}
```

| Field | Rule |
|---|---|
| component `id` | unique. `actor` is reserved. Use dotted IDs for children, such as `worker.run`. |
| component `status` | `existing` (the default), `new`, `changed` or `removed` |
| step `owner` | a component ID without children, or `actor` |
| step `id` | needed only when an extension starts at the step |
| step `message` | the label of the arrow into the step |
| extension `at` | the `id` of a step in the main scenario. The page numbers the extension `13a`, its steps `13a1`, `13a2`. |

## The page

- The check report is at the top. It is green with `OK`, or red with each problem.
- A tab for each behavior shows the actor, the goal, the trigger, the outcome and the source.
- The allocation view draws the main scenario and each extension as swimlanes:
  - The first lane is the actor. It holds the trigger, the outcome and the actor's own steps.
  - Each other lane is a component at the current zoom.
  - Arrows hand control from one step to the next, labeled with the `message`.
  - A click on a lane head with `+` shows the subcomponents. A click on a dashed group head hides
    them. A step that names an expanded component appears in a red "not allocated" lane.
- The component tree shows the number of steps for each component, and marks each untraced one.
- The trace matrix shows the step numbers that each component handles at the current zoom. A red
  column has no step.
- The URL hash keeps the view, for example `#behavior=submit&focus=worker`.

## Checklist

- [ ] Each behavior has an actor, a goal, a trigger, an outcome and a source.
- [ ] No behavior was invented. Each source is the user, a doc, an entry point or a code path.
- [ ] Each step has one owner, at the deepest level that the map shows.
- [ ] `render.sh` prints `OK`.
- [ ] Each proposed component and step has a status.
- [ ] You read the PNG of each view that the discussion uses.
- [ ] The user has the path of the HTML file.
