---
name: doc-writing
description: Rules for writing, rewriting and reviewing documentation prose (README, docs/*.md, design notes, runbooks, CLI/config/API reference), in English or Chinese. Background, design rationale and recommendations follow NASA plain-language style (point first, then reason and detail, direct wording). Procedures, code logic and state transitions follow ASD-STE100 Simplified Technical English (explicit actor, condition, action, order and result, one possible reading). Mixed documents use NASA for the overall structure and STE for each specific behavior. Three or more enumerated items always go in a vertical list. Architecture and graph relationships (components, flows, dependencies, trees, state graphs) get an SVG diagram. Use it whenever you produce or edit documentation text. For comments and docstrings in source code, use code-comments instead.
---

# Documentation writing

Every block of a document does one of two jobs. It helps the reader understand or decide, or
it tells the reader exactly what to do or what the system does. Write the first kind in NASA
plain-language style. Write the second kind in ASD-STE100 Simplified Technical English (STE).

## Choose the mode for each block

| Content | Standard | What the text must do |
|---|---|---|
| Background, design rationale, trade-offs, results, recommendations | NASA | State the point first. Then give the reason, then the detail. Use natural, direct words. |
| Procedures, code logic, state transitions, CLI and config behavior, error handling | STE | Name the actor, condition, action, order and result. Leave only one possible reading. |
| A document that has both | Mixed | Use NASA to organize the whole document. Use STE to write each specific behavior. |
| Architecture, data and control flow, dependencies, trees, state graphs | SVG diagram | Draw an SVG figure of the structure. Write the point and the exact behavior in the text too. |

Choose the mode per section or paragraph, not per document. Use this test: if the reader acts
on the text or predicts system behavior from it, use STE. If the reader understands or decides
from it, use NASA.

## Length: say less

The user reads short documents and skips long ones. Apply these rules to every document:

1. A markdown document has at most 800 lines. `gate/checks/doc_length.py` rejects a longer one.
   Aim well below the limit.
2. Write only what the reader needs to use or change the component. Leave out what the code
   already shows, such as each field, each error message and each private function.
3. State each fact in one place. Link to the document that owns it instead of repeating it.
4. Draw complex logic as a figure: states, branches, flows and three or more parts that interact.
   Under the figure, give a short table or list. Do not explain it in long paragraphs.
5. Prefer one table to several paragraphs of cases.

## Lists: three or more items

Write three or more items as a vertical list, with one item on each line. Do not write them
inline in a sentence. In a list, the reader can scan the items and check each one.
The rule applies in both modes and to every kind of item, for example:

- names from the code, such as request fields and config keys
- values, such as states and backend names
- cases, each with its own condition
- steps and actions
- reasons and requirements

Write each list by these rules:

1. Introduce the list with a full sentence that says what the items are. End the sentence with
   a colon.
2. Use a numbered list when the order matters. Use bullets when it does not.
3. Make the items parallel. Write all of them as noun phrases, or all of them as sentences.
4. Write the condition or detail of an item inside that item. If two items each have their own
   condition, put them in a list too.
5. Use a table when each item has two or more attributes. For example, give each backend its
   check and its cleanup in one row.
6. Do not nest lists more than two levels deep.

Write the items inline only where a list cannot render, such as in a table cell or a heading.

## Diagrams: architecture and graph relationships

When the text explains architecture or a graph relationship, draw an SVG figure. Read
`references/diagrams.md` before you draw. These are the main rules:

1. Draw SVG. Do not use ASCII art or Mermaid instead.
2. Use the figure together with the text:
   - Before the figure, write the point in NASA style.
   - Under the figure, write a caption of one sentence.
   - After the figure, write the exact behavior in STE or in a table.
3. Use the same names in the figure as in the text and the code.
4. Give each relation type one line style, and label each arrow.
5. Put the file in `docs/figures/`. Put drafts and preview renders in `scratch/`.
6. Render the SVG to PNG and look at it before you finish.

A linear sequence of steps is not a graph. Write it as a numbered list.

## NASA: point first

This style is based on two sources:

- the Federal Plain Language Guidelines, which NASA applies under the Plain Writing Act of 2010
- the NASA Systems Engineering Handbook (NASA/SP-2016-6105 Rev 2), Appendix C, "How to Write a
  Good Requirement"

Apply these rules:

1. **Lead with the point.** The first sentence states the point, such as the conclusion or the
   decision. This applies at every level, from the whole document down to each paragraph. The
   reason comes next. Details and evidence come last. A reader who stops after the first
   sentence has the most important fact.
2. **Write for a named reader.** Before you write, decide who reads the text and what they must
   know or do afterward. Remove what that reader does not need.
3. **Use the active voice and name the actor.** Write "The worker removes the subvolume", not
   "The subvolume is removed". Use the passive voice only when the actor is irrelevant. If you
   do not know the actor, find it in the code. Do not hide the gap with the passive voice.
4. **Use short sentences and common words.** Put one main idea in each sentence. Keep the
   average near 20 words. Write "use", not "utilize". Write "to", not "in order to".
5. **Address the reader as "you".** In a design document, refer to the authors as "we".
6. **Make every claim measurable.** Replace each vague word with a measurable statement.
   [Vague words](#vague-words) gives the replacements.
7. **Make headings informative.** In design and analysis sections, a heading can state the
   conclusion: "Per-turn checkpoints are disk-only". In reference sections, a short noun
   heading is enough: "Start", "Boundaries".
8. **Use tables for comparisons.** Use a list for three or more items, as
   [Lists](#lists-three-or-more-items) says. Keep prose for reasoning.
9. **Make recommendations complete.** A recommendation has these parts:
   - the recommendation
   - the reason
   - the main cost
   - the alternatives you rejected, and why
   - the evidence that would change the decision
10. **Use one set of obligation words.** In most documents, use this set:
    - `must` / `must not`: required
    - `should`: recommended
    - `can`: possible or permitted

    In a formal requirements specification, use the NASA set instead:
    - `shall`: a requirement
    - `will`: a fact or an intent
    - `should`: a goal

    Do not use both `must` and `shall` in one document.

## STE: one possible reading

This style is based on ASD-STE100 Simplified Technical English. This skill applies the STE
writing rules. It does not apply the STE controlled dictionary.

### The five elements

Each statement about behavior must make these five elements clear.

| Element | Question | Example |
|---|---|---|
| Actor | Who or what does it? | the worker manager, `claim()`, you |
| Condition | When, or if what? | "If the lease expires", "When `--check` is set" |
| Action | What exactly happens? | "removes the container" |
| Order | Before or after what? | numbered steps, "then", "before you start" |
| Result | Which state, output or error follows? | "The job state changes to `quarantined`." |

If you cannot fill an element, read the code. If the code does not decide it, write that:
"The order of these two checks is not defined." Do not cover the gap with a vague verb.

### Words

- Use one term for one concept, and one concept for each term. Define the term once. Do not
  change between synonyms, such as attempt and trial, for variety.
- Spell every name from the code exactly as the code does, and put it in backticks.
- Use a verb for an action. Write "The worker validates the config", not "Validation of the
  config is performed".
- Use a one-word verb when a clear one exists. Write "remove", not "get rid of".
- Use a maximum of three words in a noun cluster. Write "the timeout for snapshot cleanup
  retries", not "the snapshot cleanup retry timeout".
- Keep articles and small words. Write "Restart the worker.", not "Restart worker."
- Do not use an "-ing" clause without an actor. Write "When the worker runs", not "When running".

### Sentences and paragraphs

- A procedural sentence has a maximum of 20 words. A descriptive sentence has a maximum of 25.
- Write one instruction in each procedural sentence. Write one fact in each descriptive sentence.
- Put the condition first: "If the lease expires, the manager quarantines the job."
- Use the present tense for behavior. Use the past tense only for events that occurred, such as
  measurements and incidents.
- Do not use semicolons. Make two sentences or a list.
- Do not put a clause that has its own actor and verb in parentheses. Give it its own sentence.
- A paragraph has one topic and a maximum of six sentences.
- Write negatives where a reader can assume the opposite: "The worker does not retry review jobs."
- Give the exact scope of each quantifier, such as "always" or "only".

### Procedures

1. Number the steps. Write one action in each step. Start each step with the verb.
2. Put a condition or a warning before the step it applies to. Start a warning with the
   instruction, then give the risk: "Do X. If you do not, Y occurs."
3. After a step, write the result the reader sees: "The command prints `ok`."
4. Give each command and value exactly as the reader must type it. Write placeholders as `<name>`.
5. Write a branch inside its step: "If the check fails, go to step 5."
6. Keep the reasons out of the steps. Put one short "why" paragraph before or after the list.

### Code logic and state transitions

- Write each behavior as: "When <trigger>, <actor> <action>. <Result>."
- For more than three transitions, use a table with this header row:
  `| From | Trigger and condition | Actor | To |`.
- Write each of these, in addition to the normal path:
  - the failure path
  - the timeout path
  - the retry limit
  - the actions that the system does not take
- Name the function or file that owns each transition, so that the reader can verify it.

## Mixed documents

Use this structure for a design document or any document with both kinds of text:

1. **Summary** (NASA): two to five sentences that give:
   - what the subject is
   - the key decision or result
   - who must read further
2. **Background** (NASA): the problem and the constraints.
3. **Design** (mixed): start each section with one NASA sentence that states what the section
   establishes. Add an SVG figure for the architecture. Write the behavior that follows in STE.
4. **Procedures and reference** (STE).
5. **Alternatives and risks** (NASA), with the open questions.

A shorter document can drop sections. Each section still starts with its point.

## Chinese documents

The STE dictionary applies only to English. In Chinese, apply the STE structure rules:

- 写出主语。中文常省略主语。描述行为时，每句都写清是谁做，例如 `worker` 或"你"。
- 条件在前："如果租约过期，manager 把 job 的状态改为 `quarantined`。"
- 一句写一个动作。如果"然后""并且"连接两个动作，拆成两句或编号步骤。
- 用动词，不用"进行/实现/完成 + 名词"。写"校验配置"，不写"对配置进行校验"。
- 一个概念只用一个词。不要中英同义词混用。代码标识符保持原文，加反引号。
- 罗列三项及以上时，用竖排列表，一行一项。不要用顿号串在句子里。
- 用具体的条件或数字替换模糊词，例如"一般"和"适当"。列举要写全，不用"等"。

## Vague words

| Do not write | Write instead |
|---|---|
| fast, slow, large, small, cheap | the number and its unit |
| robust, reliable, safe | the failure it survives, or the check it makes |
| supports | the exact operation: reads, accepts, runs on |
| handles | what it does with the input: retries, rejects, logs |
| as appropriate, if needed, when necessary | the condition |
| etc., and so on | the complete list, or "for example" before a partial list |
| and/or | "A, B or both" |
| may, might, could (for behavior) | the condition under which it occurs. Use "can" for capability. |
| ensure | "check that", "make sure", or the mechanism |
| simply, just, easily, obviously | nothing. Remove the word. |
| it, this, that (unclear reference) | the noun |
| utilize, leverage, facilitate | use, help |
| a number of, various | the count or the list |

## Workflow

When you write or edit documentation, do these steps:

1. Write one sentence for yourself: who reads the document, and what they must do or decide.
2. Mark each planned section as NASA or STE. Mark each section that explains architecture or a
   graph relationship. That section gets an SVG figure.
3. Write the summary and the first sentence of each section. Read only these sentences. They
   must give the full message. If they do not, fix them before you continue.
4. Write the STE blocks. For each behavior statement, find the code that does it. Check each of
   the five elements against that code.
5. Do the checklist below. Fix each item that fails.

Before the checklist, run `python3 scripts/doc-lint.py <files>` as a mechanical first pass. The
script checks these items:

- the document length
- inline enumerations and list lead-ins
- list depth
- vague words
- the use of both `must` and `shall`
- Mermaid blocks and ASCII art
- the `<title>`, `<desc>` and background of each SVG

When the script finds `ste-lint.py` and `nasa-lint.py` in this repository, it runs them on the
same files and merges their findings. Give `--no-delegate` to skip them. The script cannot check
that the point comes first or that a behavior matches the code. Check these two by hand.

When you edit an existing document, apply these rules to the text that you write or change.
Rewrite other text only when the user asks. Keep every fact. If a fact is ambiguous and the code
does not resolve it, ask the user. Do not guess.

## Checklist

Both modes:

- [ ] Each section that explains architecture or a graph relationship has an SVG figure.
- [ ] Each enumeration of three or more items is a vertical list, except in a table cell or a heading.
- [ ] Each list has a lead-in sentence and parallel items.

NASA blocks:

- [ ] The first sentence of the document and of each section states the point.
- [ ] Each recommendation has all the parts that NASA rule 9 gives.
- [ ] No word from [Vague words](#vague-words) remains. Claims have numbers or conditions.
- [ ] Each heading tells the reader what the section contains or concludes.

Diagrams:

- [ ] The text states the point before the figure. A one-sentence caption is under it.
- [ ] The figure uses the same names as the text and the code.
- [ ] The SVG has a `<title>`, a full `<desc>` and an opaque background.
- [ ] You rendered the SVG and checked the PNG for overlaps and clipped text.

STE blocks:

- [ ] Each behavior sentence names its actor. No passive voice hides an actor.
- [ ] Each condition comes before its action.
- [ ] Steps are numbered, with one action each. Results are written after their steps.
- [ ] Procedural sentences have 20 words or fewer. Descriptive sentences have 25 or fewer.
- [ ] No semicolons. No clause with its own actor and verb in parentheses.
- [ ] Each term has one meaning. Names from the code match the code.
- [ ] The paths that [Code logic and state transitions](#code-logic-and-state-transitions)
      requires are written, not only the normal path.
- [ ] Each behavior statement agrees with the code.

## Examples

`references/run-store-states.svg` is a worked SVG figure: the Run Store job state graph. It shows the
states of 2026-10-16. The current graph is `docs/figures/runstore-job-states.svg`.

`references/examples.md` has before-and-after rewrites of text from this repository:

1. a design rationale (NASA)
2. a dense boundary paragraph with inline lists (STE with lists)
3. a procedure with its reason (mixed)
4. the Run Store job states (STE table)
5. a Chinese description (STE structure rules)

Read it before your first rewrite in a session.

## Files

This skill has these files:

- `scripts/doc-lint.py`: the mechanical first pass that [Workflow](#workflow) describes. Run
  `python3 scripts/doc-lint.py --selftest` after you change it.
- `references/diagrams.md`: the rules for SVG figures.
- `references/examples.md`: before-and-after rewrites.
- `references/run-store-states.svg`: a worked SVG figure.
