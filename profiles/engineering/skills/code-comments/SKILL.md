---
name: code-comments
description: Rules for comments and docstrings in source code, which covers module, class, function and method docstrings, `#:` attribute comments, inline comments, and comments in SQL and shell files. Interface comments on modules, abstract classes and public methods follow information hiding (Parnas, Ousterhout). They describe the abstraction and the contract that a caller relies on, not the implementation. Implementation comments explain why. Wording follows NASA (point first) and ASD-STE100 (explicit actor, condition and result, one term per concept). It also covers what is worth a comment (the recovery test, boundary constraints, the origin of magic numbers, workarounds with a removal condition), TODO tags, where other explanations go, and how far a comment cleanup may go. Use it whenever you write or edit a comment or a docstring. For README and docs/*.md, use doc-writing instead. For a mechanical first pass, run scripts/comment-lint.py.
---

# Code comments

A comment tells the reader what the code cannot tell them. An interface comment tells a caller
what they can rely on. An implementation comment tells a maintainer why the code is the way it is.

The recovery test, the tags, the homes of other explanations and the cleanup limits are adapted
from the SGLang comment-style rule (`.claude/rules/comment-style.md` in
https://github.com/sgl-project/sglang).

## Two kinds of comments

| Kind | Where | Reader | Content |
|---|---|---|---|
| Interface | module docstring, class docstring, docstring of a public function or method, `#:` on a public attribute, comment on a schema column | a caller, or an implementer of an abstract class | the abstraction and the contract |
| Implementation | `#` inside a body, comment on a private helper | a maintainer | why the code is this way |

Decide the kind before you write. Do not mix the two kinds in one comment.

## Interface comments: information hiding

This section is based on two sources:

- D. L. Parnas, "On the Criteria To Be Used in Decomposing Systems into Modules",
  Communications of the ACM, 1972
- J. Ousterhout, *A Philosophy of Software Design*, the chapters on comments

Each module hides a design decision that can change. This decision is the module's secret. An
interface comment describes what stays true when the secret changes. It does not describe the
secret.

1. **Start with what the unit is or does for the caller.** Write it in one sentence that stands
   alone, because tools often show only the first line. For a function that returns a value, a
   noun phrase that names the value is enough: "The backend a job's effective spec runs on."
2. **Give the contract.** Write only the parts that apply:
   - the inputs and their constraints, such as units and ranges
   - the return value, including the empty or `None` case
   - each error that it raises, with its condition
   - the side effects, such as files it writes or processes it starts
   - the preconditions and the invariants that the caller must keep
   - the guarantees about threads, blocking and order
3. **Leave out the implementation:**
   - the algorithm and the data structures
   - the private helpers and the private fields
   - which other modules read the unit, and how they use it
   - the history, such as earlier versions and fixed bugs
4. **Apply the change test to each sentence.** Ask: "If the implementation changes and the
   behavior does not, does this sentence become false?" If it does, the sentence describes the
   implementation. Move it into the body as an implementation comment, or to `docs/`.
5. **Write a necessary detail as a guarantee.** Sometimes a caller must know a fact about the
   implementation to use the interface correctly. Then write the fact as what the caller can
   rely on, not as the mechanism: "Subscribers are notified after the line is durable."
6. **Report a leak.** If you cannot describe the interface without the implementation, the
   abstraction leaks. Tell the user. Do not hide the leak with a longer comment.

Apply these rules at each level:

- **Module docstring:** give the responsibility of the module. Then give the boundary between
  what callers can rely on and what is private. Use one to five sentences. Put the design
  rationale, the measurements and the history in `docs/*.md` with the doc-writing skill. Name
  that file in the docstring.
- **Abstract class or protocol:** put the contract on the class, because an implementer reads
  the class. A module docstring alone is not enough. For each abstract method, write these:
  - what an implementation must do
  - what it can assume
  - what it must not do
- **Public method:** give its own contract. Do not repeat the class docstring.

Write the contract in sentences. Do not write `Args:`, `Returns:` or `Raises:` blocks. The
signature and the type hints already give the names and the types.

## Implementation comments

1. **Explain why, not what.** If a comment says what the next line does, remove the comment.
   If the code is unclear without it, rename the code first.
2. **Apply the recovery test.** Ask: "If I delete this comment, what does it cost a reader to
   find the fact again?" A fact that lives in another file or another process costs the most.
   A fact that the next line shows costs nothing. Write the comment only when the cost is real.
3. **Write a comment for each of these:**
   - a constraint that crosses a boundary, such as a field order, a wire format or a call order
     that the Go runtime, a PostgreSQL schema, `podman` or another process also depends on
   - a unit or a layout that the name cannot carry, such as tokens or bytes, or seconds or
     milliseconds. Put the unit in the name first. Comment only when an existing interface fixes
     the name.
   - the origin of a magic number: a limit of a tool or a service, a measurement, or an arbitrary
     choice. Say when a value is arbitrary. Then the next maintainer knows that it is safe to
     change.
   - a workaround. Give a reference that the reader can check, such as an upstream issue. Give
     the condition that lets someone remove the workaround.
   - a contract that is a decision, not a mechanism, such as the meaning of a sentinel value, an
     intentional omission from a list, or an order that looks accidental
   - an invariant that the next lines depend on
   - a choice that looks wrong but is intentional
4. **Do not write these:**
   - `# Step 1:` numbering over straight-line code. If the flow needs numbers, extract helper
     functions with clear names.
   - the names of the callers. `grep` finds them.
   - a hedge, such as "this should probably be revisited". Find the fact and state it, or write
     a `TODO` with an owner.
5. **Put the comment directly above the code that it explains**, not at the top of the function.
   Comments collected at the top of a function become stale first.
6. **Do not write history.** Do not write "removed X", "fixed the bug" or "new version". Git
   keeps the history. Do not refer to the task, the conversation or the review. If a past
   failure is still a constraint, write the constraint, not the story:

   ```python
   # Bad:  We used to release the lease first, but then two workers claimed the job.
   # Good: Release the lease after the commit. An earlier release lets a second worker claim it.
   ```
7. **Do not leave commented-out code.** Remove it.

## Tags

- Write planned work as `TODO(<owner>)` or `TODO(<issue URL>)`. Do not write a `TODO` without
  an owner or an issue, because nobody ever does it.
- Do not write `FIXME`, `XXX` or `HACK`. Write a `TODO` with an owner, or state the fact.
- Do not start a comment with `NOTE:`. State the fact.

## Where other explanations go

Each explanation has one home. A second copy in a comment drifts from the first.

| Explanation | Home |
|---|---|
| what the code did before | `git log` |
| why the change was made, what else was tried, which measurement moved | the commit message or the PR |
| design rationale and measurements | `docs/*.md`, named in the module docstring |
| the meaning of a CLI flag | its `argparse` `help` text |
| the intent of a test | the test name and its docstring (see the testing skill) |
| superseded code | `git show` |

Do not write review attribution, such as "as suggested in review". Do not use commit hashes or
PR numbers as a changelog. An upstream issue URL on a workaround is different, because it is the
condition for removal. Keep it.

## Wording

These rules come from STE and NASA, as in the doc-writing skill:

- Put the point in the first sentence.
- Name each actor other than the function itself: "The worker reads it at each heartbeat."
- Write each condition with its result: "Raises `Fenced` if the lease expired."
- Use one term for one concept. Spell names from the code exactly. Mark them up the way the
  file already does.
- Do not join two facts with a semicolon. Write two sentences.
- Keep sentences to 25 words or fewer.
- Do not use vague words, such as "handles" or "robust". Write what the code does.
- Do not use Markdown structure, such as headings or tables, in an inline comment.

## Scope and maintenance

- Match the comment density of the surrounding code.
- Keep these limits. `gate/checks/comment_length.py` checks all three:
  - a file docstring: 20 lines or fewer. In Go and shell, the comment block that opens the file.
  - a function or class docstring: 5 lines or fewer. In Go and shell, the block directly above
    the declaration.
  - any other run of whole-line comments, `#:` included: 2 lines or fewer.

  If a comment needs more, the content belongs in `docs/`.
- When you change code, update its comments in the same edit. A wrong comment is worse than no
  comment.
- Apply these rules to the comments that you write or change. Rewrite other comments only when
  the user asks. Then follow [Cleaning up comments](#cleaning-up-comments).
- If the code contradicts a comment that you read, tell the user.
- Write comments in English, like the code, and in ASCII. Do not use Unicode arrows, dashes,
  math symbols or CJK characters.

## Cleaning up comments

Writing a comment and deleting one are different decisions. When you write a comment, you have
the context that made it necessary. When you delete another author's one-line comment, you
usually do not. The line can be the last record of a fact from another file. In a large
deletion diff, no reviewer sees that the fact is gone.

So, in a diff that only cleans up comments, use these limits:

- Do not remove or rewrite a one-line comment only because the code says the same thing.
  Rewrite it only when it is wrong, stale or commented-out code.
- You can remove or shorten these:
  - a multi-line comment that restates the code
  - an `Args:` or `Returns:` block
  - a multi-line comment that tells history, the reason for a change, or an abandoned approach
  - commented-out code, of any length
- If a block has one fact that a reader cannot find in the code, keep that sentence. Remove the
  rest.

## Checklist

For a mechanical first pass, run `python3 scripts/comment-lint.py <files or dirs>` (`--json` for
structured output, `--list-rules` for the rule table). The script reads the comments and
docstrings in `.py`, `.sh` and `.sql` files. It checks the measurable rules only: tags, ASCII,
the length limits, `Args:` blocks, history and caller phrases, vague words, semicolons, sentence
length, step numbering, Markdown and commented-out code. It checks patterns only. It cannot check
whether a comment explains why, passes the change test or the recovery test, or agrees with the
code. Then go through the checklist.

- [ ] Each comment is an interface comment or an implementation comment, not both.
- [ ] Each interface comment passes the change test.
- [ ] Each interface comment gives the parts of the contract that apply.
- [ ] Each abstract class carries the contract for its implementers.
- [ ] Each implementation comment explains why, and passes the recovery test.
- [ ] Each workaround names a reference and the condition for its removal.
- [ ] No comment contains history, task references or commented-out code.
- [ ] Each `TODO` has an owner or an issue. No `FIXME`, `XXX`, `HACK` or `NOTE:` remains.
- [ ] No docstring has an `Args:`, `Returns:` or `Raises:` block.
- [ ] Each comment is in ASCII.
- [ ] Each first sentence stands alone.
- [ ] No file docstring is over 20 lines, no function or class docstring over 5, and no other
      run of line comments over 2.
- [ ] No semicolon joins two facts. No vague word remains.
- [ ] Each comment agrees with the code after your change.

## Examples

`references/examples.md` has rewrites of comments from this repository:

1. a module docstring that contains its implementation (the podman pool, now
   `sprout_sandbox/podman_pool.py`)
2. an interface comment that describes another module and has gone stale (`ToolResult`, now in
   `worker/tools/result.py`)
3. an abstract class whose contract is only in the module docstring (`AgentSlot`, now in
   `worker/agents/slot.py`)
4. a good method docstring with STE wording fixes (`Store.request_stop`)
5. implementation comments and a column comment

Read it before your first rewrite in a session.

## Files

- `references/examples.md`: the rewrites listed under [Examples](#examples).
- `scripts/comment-lint.py`: the mechanical first pass. `python3 scripts/comment-lint.py --selftest`
  runs its tests.
