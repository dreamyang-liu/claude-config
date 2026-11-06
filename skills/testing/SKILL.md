---
name: testing
description: Rules for designing, writing, reviewing and running tests in this repository (pytest under tests/, go test under runtime/). Based on Software Engineering at Google (test behaviors through public APIs, test sizes and scopes, unchanging tests, DAMP, real implementations before fakes before mocks), Practical Combinatorial Testing (NIST SP 800-142, equivalence classes and boundaries, t-way covering arrays with constraints, oracles), xUnit Test Patterns (four-phase test, fresh minimal fixtures, the test double taxonomy, test smells), and on the SGLang test admission rule (each case names the change that turns it red: bug regression, derived property or bookkeeping, plus the deletion test). Includes scripts/covering_array.py, which generates and measures t-way covering arrays. Use it whenever you add, change, review or debug a test, choose test cases or test doubles, or run the suite.
---

# Testing

A test protects one behavior. It goes through the public interface, and it fails only when that
behavior breaks. Each rule below serves that goal.

The rules come from four sources:

- T. Winters, T. Manshreck and H. Wright, *Software Engineering at Google* (O'Reilly, 2020),
  chapters 11–14: testing overview, unit testing, test doubles, larger testing
- D. R. Kuhn, R. N. Kacker and Y. Lei, *Practical Combinatorial Testing*, NIST Special
  Publication 800-142 (2010)
- G. Meszaros, *xUnit Test Patterns: Refactoring Test Code* (Addison-Wesley, 2007)
- the SGLang unit test admission rule, `.claude/rules/unit-test-admission.md` in
  https://github.com/sgl-project/sglang

## Workflow

When you add or change behavior, do these steps:

1. List the behaviors that changed. A behavior is "given this state and this input, the unit
   gives this result". Do not list methods. Each behavior that a caller relies on needs a test.
   For each test, name the change to the code that would turn it red. If you cannot name one,
   do not write the test. See [Admitting a test](#admitting-a-test).
2. For a bug fix, write the test first. Run it on the old code and see it fail.
3. Choose the size of each test. Use the smallest size that can show the behavior.
4. Design the cases. Partition the inputs. If parameters interact, use a covering array.
5. Choose the dependencies: the real implementation first, then a fake, then a stub. Use a mock
   or a spy only when the interaction itself is the behavior.
6. Write each test in four phases, with a name that states the behavior.
7. Make each new test fail one time. Break the code or the expected value. Run the test, and
   read the failure message. Then undo the break.
8. Run the tests as [Running tests](#running-tests) says.

## What to test

- **Test behaviors, not methods.** One method can have many behaviors. One behavior can use
  many methods. Name and write each test for one behavior.
- **Test through the public API.** Call the unit the way its callers call it. Do not call
  private helpers, and do not read private fields. A test that does breaks on each refactoring.
- **Test state, not interactions.** Check the result or the state after the call. Check calls
  to a dependency only when the call is the behavior, for example the exact command line that
  the code sends to `podman`.
- **Write unchanging tests.** After a change, existing tests change only for one reason:

  | Change | Existing tests |
  |---|---|
  | Pure refactoring | do not change |
  | New feature | do not change. Add new tests. |
  | Bug fix | do not change. Add the test that was missing. |
  | Behavior change | change, for the behaviors that changed only |

  If a refactoring makes you edit a test, the test depends on the implementation. Fix the test.
- **Use coverage to find gaps, not as a goal.** A line that runs under a test is not a tested
  behavior. Look for behaviors that no test checks.

## Admitting a test

Each test case must answer one question: "Which future change to the code turns this case red?"
If the only answer is "a change to the test itself", delete the case.

A new case must be one of these kinds:

1. **Bug regression.** It guards a bug that happened, for example in a run, in CI or in an issue.
   - Run it on the code before the fix, and see it fail. Then run it on the fix, and see it pass.
   - Its docstring gives, in one or two lines, the black-box behavior that must not come back.
     Put the root cause and the reproduction in the commit message or the issue.
   - For a concurrency bug, force the exact interleaving that caused the bug, for example with a
     `threading.Event` or with `await asyncio.sleep(0)`, which yields to the event loop and does
     not wait. Do not use a stress loop. A loop that cannot hit the bug on the old code guards
     nothing.
2. **Derived property.** It pins a result that took reasoning to get, such as boundary or offset
   arithmetic, an invariant, or a protocol rule: idempotency, a round trip, FIFO order. It
   catches a rewrite that looks equivalent but breaks the result.
3. **Critical-path bookkeeping.** It guards a convention that breaks when someone forgets to
   update a second place, such as a registry that must be complete, the lifecycle of a field, or
   the compatibility of a stored or wire format. Several enumerating assertions are correct here.
   The failure that it guards is "someone extended X and did not update Y".

These cases are not admissible:

- a happy-path tautology that asserts what the implementation obviously does
- a mirror test that restates the logic of the implementation as assertions
- a stress test that cannot reproduce the failure that it claims to guard

Some cases look like tautologies but guard a real failure. Apply the deletion test to them. Ask:
"If I delete this case, can a regression pass all the remaining tests?" If it can, keep the case.
Two kinds of case often pass the deletion test:

- **A literal from an external source**, such as a field name of the OpenAI API, a `podman` flag
  or the log format of a benchmark. Without the case, nothing catches a wrong copy of the spec.
- **A completeness or negative-branch contract**, such as "each job state has a handler", "a
  non-matching ID does not stop the job" or "the default applies when the input is absent". The
  failure that it guards is a predicate that becomes always true, or a new X without a new Y.

Delete a case that only echoes one isolated output of the implementation, when a change to that
output breaks nothing else.

One strong case is better than several weak ones. Each added case must guard a different
failure. For each case, ask: "Which bug escapes if I delete it?" If there is no answer, delete
the case.

Put a new case in an existing file of the same area. Make a new file only when the case needs a
different fixture, dependency or size.

If you cannot trace a failure of the test to the diff of one commit, for example because it
depends on a model endpoint, the test does not belong in the default suite. Mark it `slow`.

## Test sizes

Size is the set of resources that a test can use. Scope is the amount of code that it checks.
Most tests must be small and narrow.

| Size | Can use | In this repository | How it runs |
|---|---|---|---|
| Small | one process, no network, no sleep, no subprocess, files under `tmp_path` | most tests | default suite |
| Medium | subprocesses and localhost on one machine | the fake `podman`, `btrfs` and `findmnt` executables, the runtime binary on a local port, an isolated PostgreSQL at `SPROUT_RUNSTORE_TEST_DSN` | default suite. Skip when the resource is absent. |
| Large | real infrastructure | rootless podman with a btrfs store, AgentENV, model endpoints | `@pytest.mark.slow`, plus a `skipif` with a reason |

*Software Engineering at Google* forbids disk access in small tests. This repository allows
`tmp_path`, because each test gets its own local directory there.

Each skip must say what is missing and how to get it. Use the `live_podman_store` fixture of
`tests/support/live.py`, as `tests/sprout_sandbox/test_podman_live.py` does. A large test must
skip, not fail, when its infrastructure is absent or busy.

## Choosing cases

Choose cases by these steps. `references/combinatorial.md` gives the details and a worked example.

1. **List the parameters.** Include each of these:
   - the inputs of the call
   - the configuration, such as the backend
   - the state before the call, such as a stored job state
2. **Partition each parameter into equivalence classes.** All values in one class must make the
   code take the same path. Take one value from each class. Add the boundary values on each side
   of each limit.
3. **Test each invalid value in its own test.** Keep the other parameters valid. Two invalid
   values in one test hide each other.
4. **Write the constraints.** A constraint removes a combination from the table of valid cases.
   Two kinds of combination need one: a combination that cannot occur, and a combination that
   the code must reject. Test each rejected combination in its own invalid-value test.
5. **Choose the strength t.** NIST data show that most failures need one or two parameters to
   occur, and that none of the observed failures needed more than six:
   - Use the full product when it has about 30 rows or fewer, and the tests are fast.
   - Otherwise use t = 2 at a minimum.
   - Make t at least the number of parameters in the widest condition of the code under test.
     A condition `a and b and c` needs t = 3.
   - Use t = 3 to 4 for code with many interacting conditions, such as a state machine or a parser.
6. **Generate the rows** with `scripts/covering_array.py`. Write the model JSON in `scratch/`.
   Paste the rows into the test as a literal `parametrize` list.
7. **Give each row an oracle.** Put the expected result in a column of the table. If a rule gives
   the result, the rule must be simpler than the code under test, and it must fit in one line.
   Do not compute the expected result with the code under test.

## Test doubles

These are the kinds of test double, from *xUnit Test Patterns*:

| Double | What it does |
|---|---|
| Dummy | fills a parameter. The test never uses it. |
| Stub | gives fixed answers to the calls of the unit |
| Spy | a stub that also records the calls, for the test to check after the exercise phase |
| Mock | checks the calls during the exercise phase, against expectations set before it |
| Fake | a working, simplified implementation, such as an in-memory store |

Choose the dependency in this order:

1. **The real implementation**, when the test stays fast, and gives the same result on each run.
2. **A fake**, when the real one is not fast or not deterministic, for example because it needs
   infrastructure. A fake needs a fidelity test that runs the same code against the real
   dependency, marked `slow`. In this repository, the fake executables of `tests/support/tools.py`
   record argv and answer like the real podman, btrfs and findmnt. `tests/support/test_fakes.py`
   runs the same code against the real tools.
3. **A stub**, for one answer that the test controls, such as an error from a dependency.
4. **A spy**, only when the interaction is the behavior. Check only the calls that matter.

Do not use `unittest.mock`. This repository has no mocks. It uses fakes and spies instead.
Use `monkeypatch` for environment variables, and to replace a dependency at the
point where the code receives it. Do not use it to replace a private function of the unit.

If you cannot test a unit without a double for one of its own parts, the design is hard to
test. Inject the dependency, or move the logic into a function that takes plain values. Do not
add test-only branches to production code.

## Writing a test

- **Use the four phases:** setup, exercise, verify, teardown. Separate them with blank lines.
  Put teardown in a `yield` fixture or use `tmp_path`, so that it runs when the test fails.
- **Check one behavior.** Several assertions are correct when together they check one behavior.
  If a test checks two behaviors, split it.
- **Name the test after the behavior, as a sentence.** Write
  `test_the_adapter_refuses_any_slot_but_mini`, not `test_adapter` or `test_podman_defaults`.
- **Prefer DAMP to DRY.** Put each value that matters for the behavior in the test body. Hide
  each value that does not matter in a creation function with defaults. The reader must not need
  another file to understand the test.
- **Use a fresh, minimal fixture.** Each test builds the state that it needs, and no more. Share
  a fixture only when it is immutable and costly to build. The `run_store` fixture of
  `tests/support/runstore.py` makes a new schema for each test and drops it after the test.
- **Put no logic in the test.** Do not put control flow, such as a loop or an `if`, in a test
  body. Use `parametrize` for cases, and `pytest.raises(..., match=...)` for errors.
- **Assert exact values.** Compare with the full expected value, not with a part of it. Put a
  repeated check in a helper `assert_...` function. Add an assertion message when the compared
  values do not explain the failure.
- **Make the test deterministic:**
  - Do not use `sleep` to wait for an event. Wait for the event, with a deadline.
  - Fix each random seed. Inject the clock.
  - Restore the global state that the test changes. The autouse fixture of
    `tests/support/process.py` restores the umask and the environment after each test.
  - Do not depend on the order of the tests.
- **Name no host paths.** Fixtures and expected values use placeholders under `/path/to/`.
  `gate/checks/no_host_paths.py` rejects a tracked file that names a home directory.

A test that sometimes fails is a defect. Find the cause. Do not add a retry to make it pass.

## Running tests

- Run the tests of the area that you changed first:
  `.venv/bin/python -m pytest tests/<area>/test_<name>.py -q`
- Set `SPROUT_RUNSTORE_TEST_DSN="dbname=sprout_runstore_test"` for the tests that need the Run Store
  database. Without it, they skip.
- Keep the exit code. `pytest | tail` returns the exit code of `tail`. Use `set -o pipefail`, or
  write the output to a file and read the file.
- Before you run the full suite or any `slow` test, check that no experiment uses the btrfs
  store. The live fixtures remove every container and snapshot that appears during a test. This
  command prints `idle` or the reason that the store is busy:

  ```bash
  PYTHONPATH=src:. .venv/bin/python -c "from tests.support.live import live_store, podman_store_in_use; print(podman_store_in_use(live_store()) or 'idle')"
  ```

  If the store is busy, run only `-m "not slow"`. Do not use a bare `podman ps`: `/usr/bin/podman`
  is not the podman that the store uses.
- Go: `cd runtime && go test ./...`. CI also runs `go vet ./...` and `gate/run.sh`.
- Report the result exactly. Give these:
  - the counts that pytest prints
  - each failure, with its output
  - each skipped test that matters

## Reviewing a test

Check each test against these questions:

- [ ] Can you name the change to the code that turns it red? Does it guard a failure that no
      other test guards?
- [ ] Does it check one behavior, named in its name?
- [ ] Does it go through the public API, and check state rather than interactions?
- [ ] Would it stay unchanged under a pure refactoring?
- [ ] Is each value that matters visible in the test body?
- [ ] Is it free of control flow and of `sleep`?
- [ ] Is it deterministic and independent of other tests?
- [ ] Does each double have the lowest power that the test needs?
- [ ] Did it fail once, with a clear message, when the behavior was broken?
- [ ] For a parametrized test: are the classes and the boundaries correct? Is t correct?

`references/smells.md` lists the test smells from *xUnit Test Patterns*, with their causes and
fixes. Use it to name a problem in a review.
