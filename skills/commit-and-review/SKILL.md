---
name: commit-and-review
description: Steps and rules for committing, opening a pull request and reviewing in this repository. The user confirms each commit, push and PR. Each commit passes the pre-commit hook (gate/run.sh) and never uses --no-verify. A commit message is one short subject line with no body and no trailer. Only the files of the change are staged. Each change goes to a topic branch and a PR against main, with a description of what, why, tests and deviations. A review checks the diff against the code-style, code-comments, testing and doc-writing skills, then runs the code-review skill for bugs. Use it whenever you are about to commit, push, open or update a PR, or review a diff or a PR.
---

# Commit and review

Each change reaches `main` through a pull request. Each commit in the PR passes the pre-commit
hook first. The user approves each step that leaves the machine or changes history: the commit,
the push and the PR.

## Before a commit

Do these steps in order:

1. **Check the hook.** `git config core.hooksPath` must name the `gate/hooks` directory of this
   checkout, as `gate/hooks` or as its absolute path. If it does not, tell
   the user. Enable it with `git config core.hooksPath gate/hooks` after the user agrees.
2. **Check the branch.** If the current branch is `main`, make a topic branch first:
   `git switch -c <topic>`. Give it a short kebab-case name that states the change.
3. **Stage only the files of the change.** Read `git status --short` first. The working tree often
   holds unrelated work, for example from another session. Stage each file by its path:
   `git add <path>...`. Do not use `git add -A`, `git add .` or `git commit -a`.
4. **Check the size.** If the change has more than 10 files, split it into smaller commits
   (`CLAUDE.md`).
5. **Review the staged diff.** Read `git diff --staged`, and review it as
   [Reviewing a diff](#reviewing-a-diff) says.
6. **Run the tests of the changed area**, as the testing skill says. Keep the counts.
7. **Run the pre-commit hook:** `gate/hooks/pre-commit`. It runs `gate/run.sh`. Each gate must
   print `pass`. If a gate fails, fix the cause. Do not skip the gate.
8. **Run the linters on the changed Python files first:**
   `.venv/bin/ruff check <files>` and `.venv/bin/ruff format --check <files>`. The hook runs them
   too, in `gate/checks/lint.py`, with gofmt, go vet, staticcheck and shellcheck. Running them
   first shows the findings before the hook refuses the commit.
9. **Ask the user.** Show these items:
   - the branch
   - the staged files
   - the commit subject
   - the result of the hook and of the tests

   Commit only after the user says yes. The user can approve the commit, the push and the PR
   together or one at a time.

## The commit

- Write one subject line of 72 characters or fewer, in the imperative, like the subjects in
  `git log --oneline`. Do not write a body. Do not add a `Co-Authored-By` line or another trailer.
- The author is `Mengyang Liu <nikolaliu@icloud.com>`, from the global git config. Check
  `git config user.email` before the first commit in a session.
- Commit with `git commit -m "<subject>"`. The hook runs the gate again.
- Never use `--no-verify`. If the hook fails, the commit does not exist. Fix the cause, stage the
  fix, and commit again.
- Do not amend, rebase or force-push a commit that is on the remote, unless the user asks.

## The pull request

1. **Push the branch:** `git push -u origin <topic>`. The git credential helper in `~/.gitconfig`
   calls `/usr/bin/gh auth git-credential`. If `gh` is missing, the push fails. Then stop and
   tell the user to install `gh`.
2. **Open the PR** against `main`:

   ```bash
   gh pr create --base main --head <topic> --title "<subject>" --body "$(cat <<'EOF'
   ...
   EOF
   )"
   ```

   For a PR with one commit, the title is the commit subject.
3. **Write the description** in English, with these sections:
   - **What:** the change, in one to three sentences.
   - **Why:** the reason for the change, the alternatives that you tried, and each measurement
     that moved. This is the home of "why the change was made" (see the code-comments skill).
   - **Tests:** each command that you ran and the counts that it printed, the result of the
     hook, and each skipped `slow` test with the reason.
   - **Deviations:** each rule of the code-style, code-comments or testing skill that the change
     does not follow, and why.

   Do not add an attribution line, such as "Generated with Claude Code", or a trailer.
4. **Review the PR yourself** with the code-review skill. Fix each finding in a new commit on the
   same branch. Each new commit follows [Before a commit](#before-a-commit) again.
5. **Do not merge the PR.** The user merges it.

## Reviewing a diff

Use these steps for your own staged diff, for your own PR, and for a PR from someone else:

1. **Scope.** The diff contains the stated change and nothing else. Look for unrelated files,
   debug output, files from `scratch/`, secrets, host paths and large binaries.
2. **Tests.** Each changed behavior has a test that the testing skill admits. A bug fix has a
   test that failed on the old code.
3. **Code.** Apply the checklist of the code-style skill.
4. **Comments.** Apply the checklist of the code-comments skill.
5. **Docs.** A change in behavior updates the README or `docs/*.md`, as the doc-writing skill
   says. A new runtime tool appears in the `runtime/README.md` section "Runtime toolset
   support" (`CLAUDE.md`).
6. **Decisions.** If the diff makes a decision that one revert cannot undo, such as a schema, a
   wire format or a deleted dataset, the PR contains its ADR (see the architecture-decisions
   skill). If the diff contradicts an accepted ADR, it contains the ADR that supersedes it.
7. **Bugs.** Run the code-review skill on the branch or the PR.

Report each finding with `path:line`, the most severe first. Say which findings block the merge.
Name each deviation from a skill explicitly. On a PR from someone else, do not push to their
branch. Post comments only after the user agrees.

## Checklist

- [ ] The change is on a topic branch, not on `main`.
- [ ] Only the files of the change are staged, and there are 10 or fewer.
- [ ] The tests of the area pass, and the counts are recorded.
- [ ] `gate/hooks/pre-commit` passes. No commit used `--no-verify`.
- [ ] Ruff reports nothing in the changed lines.
- [ ] The user approved the commit, the push and the PR.
- [ ] Each commit message is one subject line, with no body and no trailer.
- [ ] The PR description has What, Why, Tests and Deviations, and no attribution line.
- [ ] The code-review skill ran on the PR, and its findings are fixed or answered.
