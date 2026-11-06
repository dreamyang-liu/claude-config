# Combinatorial test design

Most failures occur only when a few parameters take particular values at the same time. A t-way
covering array contains every combination of values for every t parameters, in far fewer rows
than the full product. This file has these parts:

- the procedure
- the script
- a worked example on `Store.finish()`

Source: D. R. Kuhn, R. N. Kacker and Y. Lei, *Practical Combinatorial Testing*, NIST SP 800-142.

## The interaction rule

NIST studied failure reports from several kinds of software, from medical devices to
databases. These are the results:

- Most failures needed one or two parameters to occur.
- Fewer failures needed three or more parameters.
- No observed failure needed more than six parameters.

So a test set that covers every t-way combination, with t from 4 to 6, finds the same failures
as the full product for most software. A test set with t = 2 finds most of them.

## Procedure

1. **List the parameters.** For each one, write where the code reads it. Include these kinds:
   - the inputs of the call
   - the configuration, such as a profile field or an environment variable
   - the state before the call, such as a stored job state
2. **Partition each parameter.** Make one equivalence class for each path that the code takes.
   Take one value from each class. For each limit, add the values on both sides of it. For
   example, a timeout with a maximum of 3600 s gets the values 1 and 3600 for the valid classes.
   It gets 0 and 3601 for the invalid-value tests. Keep each parameter to 2 to 5 values. The
   number of rows grows at least as the product of the t largest domains.
3. **Take out the invalid values.** Test each invalid value in its own test, with all other
   parameters valid. If two invalid values are in one row, the first error hides the second.
4. **Write the constraints.** Put each combination that cannot occur, or that the code must
   reject, in `forbidden`. Each rejected combination also gets its own invalid-value test.
5. **Choose t:**
   - Use the full product when it has about 30 rows or fewer, and the tests are fast.
   - Otherwise use t = 2 at a minimum.
   - Make t at least the number of parameters in the widest condition of the code under test.
   - Use t = 3 to 4 for code with many interacting conditions, such as a state machine or a parser.
6. **Generate the rows.** Write the model JSON in `scratch/`, then run the script. Paste the rows
   into the test as a literal `parametrize` list. Write one comment line above the list that
   gives t and the script name. A literal list is deterministic, and a reviewer can read it.
7. **Give each row an oracle.** Use one of these:
   - an expected column in the table
   - a rule of one line that is simpler than the code under test
   - an invariant that holds for every row, such as "the call does not raise" or "the round
     trip gives the input"
   - a reference implementation, such as a fake that has a fidelity test
8. **Regenerate the rows when a parameter changes.** Replace the old rows. Do not edit the
   generated rows by hand.

## The script

`scripts/covering_array.py` uses only the standard library. Generation is IPOG (Lei et al.,
2007). It is deterministic: one model always gives the same rows.

The model has two keys:

```json
{"parameters": {"state": ["succeeded", "failed"], "retry": [false, true]},
 "forbidden": [{"retry": true, "state": "succeeded"}]}
```

- `parameters`: each name with its list of values. Values can be any JSON value. `true` and `1`
  are different values.
- `forbidden`: partial rows. A row is invalid when it matches each assignment of one entry.

Commands:

```bash
S=.claude/skills/testing/scripts/covering_array.py
python3 -I $S scratch/model.json --strength 3            # rows as JSON
python3 -I $S scratch/model.json --strength 3 --python   # a pytest.mark.parametrize decorator
python3 -I $S scratch/model.json --strength 3 --measure scratch/rows.json   # coverage of rows
```

Exit codes:

- 0: the rows were generated, or the measured rows cover all feasible combinations
- 1: the measured rows miss combinations. The script lists them.
- 2: the model or the rows are not valid

A combination is feasible when a valid full row can contain it. The script does not generate or
count infeasible combinations. `--measure` warns about each row that matches a forbidden entry.

The script was checked against a brute-force count on 13 models. The models included these
cases:

- constraints
- values that no valid row can take
- t larger than the number of parameters

Every generated
set covered every feasible combination. The sizes it gives are near the best known:

| Model | t | Rows | Full product |
|---|---|---|---|
| 4 parameters of 3 values | 2 | 10 | 81 |
| 10 parameters of 2 values | 2 | 9 | 1,024 |
| 10 parameters of 2 values | 3 | 20 | 1,024 |
| 13 parameters of 3 values | 2 | 21 | 1,594,323 |
| 5, 4, 3, 2 and 2 values | 2 | 20 | 240 |

## Worked example: `Store.finish()`

`finish()` in `src/sprout/runstore/store.py` ends an attempt. It sets the next state of the job.

**Parameters and classes**

| Parameter | Values | Code |
|---|---|---|
| `state` | `succeeded`, `failed`, `quarantined` | the outcome given to `finish()` |
| `retry` | `false`, `true` | the `retry` argument |
| `kind` | `rollout`, `grade`, `review` | the job kind |
| `recovery` | `false`, `true` | whether a verified continuation is given |
| `attempts_left` | `false`, `true` | `attempt_count < max_attempts` |
| `stop_requested` | `false`, `true` | `stop_requested_at` is set |

**Invalid-value tests.** Each of these raises `ValueError`, and each gets its own test:

- a `state` other than the three above
- `retry` with a `state` other than `failed`
- `retry` with a `failure_kind` other than `infrastructure`
- `retry` on a rollout without `recovery`

**Model**

```json
{"parameters": {
  "state": ["succeeded", "failed", "quarantined"], "retry": [false, true],
  "kind": ["rollout", "grade", "review"], "recovery": [false, true],
  "attempts_left": [false, true], "stop_requested": [false, true]},
 "forbidden": [{"retry": true, "state": "succeeded"}, {"retry": true, "state": "quarantined"},
               {"retry": true, "kind": "rollout", "recovery": false}]}
```

**Oracle.** The next state is `queued` if `retry and attempts_left and not stop_requested`.
Otherwise it is `state`. The rule is one line, and it is simpler than `finish()`.

**Choice of t.** The requeue condition joins three parameters, so t must be 3:

| t | Rows | Rows that requeue |
|---|---|---|
| 2 | 10 | 0 |
| 3 | 27 | 2 |
| full product | 144, before the constraints | — |

The 10 rows of the 2-way array cover every pair of values. They still contain no row in which
all three parameters of the requeue condition are true together. `--measure` on those 10 rows
at t = 3 reports 158 of 229 feasible combinations, 69.0%. The 27 rows of the 3-way array test
the requeue path. They need a PostgreSQL database for each row, so 27 rows instead of the full
product matters.

**Test sketch.** `claimed_job` and `result_for` are creation functions that the test module
defines. The rows come from the `--python` output.

```python
# 3-way covering array (covering_array.py) of the finish() parameters.
@pytest.mark.parametrize("state,retry,kind,recovery,attempts_left,stop_requested", [
    ("succeeded", False, "rollout", False, False, False),
    # [... the other 26 rows ...]
])
def test_finish_requeues_only_a_retried_failure_with_attempts_left_and_no_stop(
        store, state, retry, kind, recovery, attempts_left, stop_requested):
    job = claimed_job(store, kind=kind, attempts_left=attempts_left, stop_requested=stop_requested)

    store.finish(job["id"], job["lease_token"], result_for(retry), state=state, retry=retry,
                 recovery={"point": "p1"} if recovery else None)

    expected = "queued" if retry and attempts_left and not stop_requested else state
    assert store.get(job["id"])["state"] == expected
```
