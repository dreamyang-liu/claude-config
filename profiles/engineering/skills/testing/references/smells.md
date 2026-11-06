# Test smells

A test smell is a symptom. Find its cause in the table, then apply the fix. The names come
from G. Meszaros, *xUnit Test Patterns* (2007). Use them in a review, so that the author can
look them up.

## Code smells: you see them when you read the test

| Smell | Symptom | Causes | Fix |
|---|---|---|---|
| Obscure Test | The reader cannot see how the test shows the behavior. | Eager Test: it checks several behaviors. Mystery Guest: it reads data that the reader cannot see. General Fixture: the fixture is larger than the test needs. Irrelevant Information: values that do not matter are in the body. | One behavior for each test. Put the values that matter in the body. Put the others in a creation function with defaults. |
| Conditional Test Logic | The test has `if`, a loop or `try`. | Several cases in one test, or a check that depends on the result. | Use `parametrize`, or one test for each case. Use `pytest.raises`. |
| Hard-to-Test Code | The unit is hard to set up or to observe. | Fixed dependencies, logic inside I/O or threads. | Inject the dependency. Move the logic into a function of plain values (Humble Object). |
| Test Code Duplication | The same setup is in many tests. | No creation functions or custom assertions. | Add a creation function or an `assert_...` helper. Keep each value that matters visible. |
| Test Logic in Production | Production code has branches or hooks for tests. | The unit cannot be tested from outside. | Inject the dependency. Remove the hook. |

## Behavior smells: you see them when the tests run

| Smell | Symptom | Causes | Fix |
|---|---|---|---|
| Assertion Roulette | A failure does not say which check failed, or why. | Many assertions without messages. An Eager Test. | One behavior for each test. Compare whole expected values. Add a message where the values do not explain the failure. |
| Erratic Test | The test passes sometimes and fails sometimes. | Interacting Tests: order or shared state. Test Run War: parallel tests share a resource. Resource Leakage. Resource Optimism: it assumes that a resource exists. Nondeterminism: time, randomness, threads. | Fresh fixture. Restore global state. Use `tmp_path` and unique names. Inject the clock. Fix the seeds. Wait for events with a deadline. |
| Fragile Test | The test fails after a change that did not change the behavior. | Interface Sensitivity: it uses internals. Behavior Sensitivity: it checks more than its behavior. Data Sensitivity: it uses shared data. Context Sensitivity: it depends on the environment. Overspecified Software: it checks calls that do not matter. | Use the public API. Check state. Use a minimal fixture. Control the environment in the test. |
| Frequent Debugging | You need a debugger to find the cause of a failure. | The test is too large. The messages are poor. | Write smaller tests that localize the defect. |
| Manual Intervention | A person must prepare the test or read its output. | Setup or checks that are not automated. | Automate the setup. Make the test check itself. |
| Slow Tests | The suite is too slow to run before each commit. | A slow dependency, a General Fixture, `sleep`, or too many large tests. | Use a fake. Use a minimal fixture. Wait for the event. Move cases to small tests. Use a covering array instead of a full product. |

## Project smells: you see them in the history

| Smell | Symptom | Fix |
|---|---|---|
| Buggy Tests | Tests pass when the code is wrong. | Make each new test fail once before you accept it. |
| Developers Not Writing Tests | Changes arrive without tests. | Write the test in the same change. A behavior without a test is not protected. |
| High Test Maintenance Cost | Many tests change with each refactoring. | Find the Fragile Tests and fix their causes. |
| Production Bugs | Defects reach a run. | Add the test that was missing for each defect. Check the size mix: more small tests, fewer large ones. |

## Example from this repository

`tests/runstore/test_swerebench_messages.py` has a Context Sensitivity. When `FORCE_COLOR=3` is
set, 5 of its 18 tests fail. Without it, all 18 pass. The tests depend on a variable that they do
not control. The fix is for the test, or its fixture, to set the variable itself.
