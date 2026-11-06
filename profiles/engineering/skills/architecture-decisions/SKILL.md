---
name: architecture-decisions
description: When and how to record an architecture decision record (ADR), one file for each decision in docs/decisions/, listed in docs/decisions/README.md. Apply the revert test to each decision. Record a decision when one git revert cannot undo its effects, for example a changed stored or wire format, a schema, rewritten history or deleted data, a published result, an interface that another process or repository uses, a reported experiment protocol, or a dependency on infrastructure. Ask the user once before you record a significant decision that one revert can undo. Record nothing else. Each ADR follows Nygard's format (status, context, decision, consequences) plus the alternatives and the revert cost. Nobody edits an accepted ADR. A new ADR supersedes it. Use it at the end of each discussion that reached a decision, when the user says that something is decided, and before you propose a design in an area that an ADR covers.
---

# Architecture decisions

An ADR records a decision that the code cannot explain and that is expensive to undo. Most
decisions do not need an ADR. The code, the tests, the commit messages and the PR descriptions
keep the rest. A short list of real decisions stays read. A long list of everything does not.

The rules come from these sources:

- M. Nygard, "Documenting Architecture Decisions" (2011,
  https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions): one decision for
  each record, with its status, context, decision and consequences. A new record supersedes an
  old one. Nobody edits the old one.
- J. Bezos, letter to Amazon shareholders (2015): one-way doors and two-way doors. A decision that
  you cannot reverse needs care. A decision that you can reverse needs speed.

## Decide whether to record

At the end of a discussion that reached a decision, apply the revert test to each decision. Ask:
"If this decision is wrong, does one `git revert` of one commit restore the earlier state, for
each user and for all data?"

| Class | Revert test | Action |
|---|---|---|
| One-way | fails | Record it. Tell the user that you will write an ADR, and show the draft. |
| Two-way and significant | passes, but the decision sets a convention for many files, chooses between real alternatives that someone will propose again, or crosses components | Ask the user once. Record it only if the user says yes. |
| Two-way and local | passes | Do not record it. Do not ask. |

A decision fails the revert test when it does one of these:

- It changes a stored format or a schema, such as the PostgreSQL schema, the journal, the
  snapshots, the run manifests or the training exports. After a revert, the data that was
  written stays in the new format, or a migration must run back.
- It changes a wire format or an interface that another process or repository uses, such as the
  runtime's JSON-RPC and `runtime/schema/tools.json`, the Run Store HTTP API, or the RL driver's
  contract with Miles. A revert breaks the other side, or the other side has already shipped.
- It deletes or rewrites history or data, such as a force-push, a rewrite of the history, or
  deleted runs, backups or images.
- It publishes something, such as a number in the paper, a Hugging Face dataset, a release or a
  public page.
- It fixes the protocol of an experiment whose results are reported. The compute and the model
  budget are spent, and the runs cannot be repeated for free.
- It adds a dependency on infrastructure or on a third party, such as a sandbox backend, a
  storage layout or a host service.
- It sets a boundary that later changes build on, such as the layering of the packages. One
  revert undoes the boundary, but not the changes built on it after the decision.

These are two-way and local: a name, a refactoring inside one package, the signature of a function
with one caller, the design of a test, a default value behind a flag, and a choice that one commit
message explains.

Rules for asking:

- Ask at most once in a discussion, at its end. List all the candidate decisions in one message.
  Give each one its class and a one-line reason. For example: "这两个决定里，第一个改了 Run Store
  的 schema，回滚一次解决不了，我会写 ADR。第二个可以回滚，要不要也记？"
- Record only what the user decided. A proposal that the user did not accept is not an ADR.
- If the user says not to record a decision, do not ask about it again.

## Where the ADRs live

Each ADR is one file: `docs/decisions/<NNNN>-<slug>.md`, for example
`docs/decisions/0007-podman-btrfs-backend.md`. `<NNNN>` is the next four-digit number after the
highest one in `docs/decisions/`. Never reuse a number. `<slug>` is a short kebab-case name of the
decision.

`docs/decisions/README.md` is the index. It has one row for each ADR, the oldest first:

```markdown
# Decisions

The architecture decisions that one revert cannot undo, and the significant ones that the team
chose to record. Each file is one decision. Nobody edits an accepted decision. A later decision
supersedes it.

| ADR | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-<slug>.md) | <the decision, as a short statement> | Accepted | <YYYY-MM-DD> |
```

### Set up the directory with the first ADR

`docs/decisions/` does not exist yet. `gate/checks/docs_layout.py` requires README.md to link to
each markdown file under `docs/`, so an ADR that only the index links to fails the gate. In the PR
of the first ADR, do these steps:

1. Create `docs/decisions/README.md` with the opening above.
2. Add this row to the table in the README section "Learn more":

   ```markdown
   | [Decisions](docs/decisions/README.md) | The architecture decisions that one revert cannot undo, with their context and consequences |
   ```
3. Change `gate/checks/docs_layout.py`: a markdown file in `docs/decisions/` passes when
   `docs/decisions/README.md` links to it. Each other markdown file under `docs/` still needs a
   link from README.md.
4. Change the row of `checks/docs_layout.py` in `gate/README.md` to match.
5. Run `gate/hooks/pre-commit`.

## Write the ADR

Use this template for the file `docs/decisions/<NNNN>-<slug>.md`:

```markdown
# ADR-0007: <the decision, as a short statement>

- **Status:** Accepted
- **Date:** <YYYY-MM-DD>
- **Revert cost:** <why one revert does not undo it, or "one revert undoes it" for a two-way ADR>

## Context

<The problem, the user behavior that it affects, the constraints and the measurements. Name each
source, such as a behavior, a run, an issue or a section of docs/.>

## Decision

<What we do, in STE: the actor, the action, the conditions. Start with "We".>

## Alternatives

- **<alternative>:** <why we did not choose it>

## Consequences

- <what becomes easier, what becomes harder, what each later change must keep true, and the
  follow-up work. Include the bad consequences.>

## Links

- <the PR, the commits, the docs sections and the code paths>
```

Rules for the content:

- **One decision for each file.** If a discussion reached two one-way decisions, write two ADRs.
- **Add the row to the index** in the same commit as the ADR.
- **Keep it to about one screen.** Put the details in `docs/*.md`, and link that file.
- **Write it in English, in the doc-writing style.** Use NASA style for the context and the
  consequences. Use STE for the decision.
- **Copy what a scratch page holds.** `scratch/` is not tracked, so a behavior map is lost after
  the session. Write the behaviors and the allocation that the decision depends on into the
  context, as a short list. If the decision needs a figure, draw it as an SVG in
  `docs/figures/`, as the doc-writing skill says.
- **Commit the ADR as the commit-and-review skill says.** Put it in the PR of the change that it
  decides. If the decision comes before the code, give it its own PR.

Run `python3 scripts/adr-lint.py docs/decisions` before the commit. It checks the file names, the
numbers, the status and date lines, the sections, the supersede links and the index. With `--git`,
it also reports an edit to an accepted ADR. It cannot judge the revert test.

## Change a decision

- Do not edit the context, the decision or the consequences of an accepted ADR. You can fix a
  typo or a broken link.
- To change a decision, write a new ADR. Its context says "Supersedes ADR-0003" and why. Then
  change only the status line of the old ADR to `Superseded by ADR-0009`, and its status in the
  index.
- To end a decision without a replacement, set the status of the old ADR to `Deprecated`, and
  give the date and the reason in the same line. Change its status in the index too.
- Do not delete or rename an ADR file. Other ADRs and PRs link to it.

## Use the ADRs

- Before you propose a design, read the index in `docs/decisions/README.md`, and the ADRs of
  the same area. If the
  proposal contradicts an accepted ADR, say so, and propose a new ADR that supersedes it.
- If you find code that contradicts an accepted ADR, tell the user. Either the code is wrong, or
  the decision changed without a new ADR.
- When an ADR records a decision that a memory note also holds, shorten the note to a pointer to
  the ADR.

## Checklist

- [ ] Each decision of the discussion got the revert test.
- [ ] Each one-way decision has an ADR. Each significant two-way decision was offered once.
- [ ] No ADR records a proposal that the user did not accept.
- [ ] Each ADR has a status, a date, the revert cost, the context, the decision, the alternatives,
      the consequences and the links.
- [ ] No accepted ADR was edited, except its status line, a typo or a link.
- [ ] Each ADR is its own file in `docs/decisions/`, and the index has its row and status.
- [ ] README.md links to the index, and `gate/hooks/pre-commit` passes.

## Files

- `scripts/adr-lint.py`: the checks above, for one ADR directory. `--list-rules` names each rule
  and its source section. `--selftest` runs its tests.
