# Before-and-after examples

Each "Before" is quoted from this repository, except where it is marked as constructed. Each
"After" keeps every fact of the "Before" and was checked against the code where it names one.

The examples quote the code of 2026-10-16. Since then, ADR-0006 removed the `quarantined` state,
`reconcile()` and the lease that each attempt renewed. Use the examples for the writing, not for
the facts: check each fact against the code and `docs/` of today.

## 1. Design rationale (NASA)

Source: `docs/SNAPSHOT_COST.md`.

**Before**

> A full snapshot stores the memory the guest has touched, page cache included (three in a row
> after the 1 GiB took 9.5 s each), which is why per-turn checkpoints are disk-only: measured on
> one long attempt, 37 MB per episode disk-only versus 2.2–4.7 GB with memory.

**Problems**

- The point ("per-turn checkpoints are disk-only") is in the middle of the sentence.
- One sentence holds the reason and the evidence. It also has a parenthesis and a colon.

**After**

> Per-turn checkpoints are disk-only, because memory snapshots are too slow and too large. A full
> snapshot stores all memory the guest has touched, including the page cache. After the guest
> wrote 1 GiB, three full snapshots in a row took 9.5 s each. On one long attempt, disk-only
> checkpoints used 37 MB per episode. With memory, they used 2.2–4.7 GB per episode.

The first sentence gives the decision and the reason. The other sentences give the evidence,
one measurement each.

## 2. Dense boundary paragraph with inline lists (STE with lists)

Source: the "Owned sandboxes" bullet in `docs/RUNSTORE.md`. The "After" was checked against
these files:

- `src/sprout/runstore/specs.py`
- `src/sprout/runstore/worker.py`
- `src/sprout_sandbox/podman.py`

**Before**

> **Owned sandboxes: podman by default, or microVMs.** A rollout needs a `sandbox_image`; its
> profile's `backend` decides where it runs, as for `harness run`: `podman` when it names none
> (rootless containers whose rootfs is a subvolume of a btrfs `store`, `ops/setup_podman.sh`;
> the worker and its attempt children run the podman `SPROUT_PODMAN_BIN` names, inherited from
> the services' `podman` check, or a profile's `podman.podman_bin`, so restart the worker after
> switching podmans), `microvm` when it says so (AgentENV). Any other backend is refused,
> because after every attempt the worker establishes that each sandbox the attempt claimed is
> gone: for podman no container, network or rootfs subvolume left (a leaked one is removed the
> way `harness reap` removes it), for a microVM AgentENV answering 404; an attempt for which
> that cannot be established is quarantined. The worker owns run ID, journal and `cwd`;
> requests may not set `session`, `journal_path`, `run_id`, `cwd`, `keep_sandbox` or
> native-restoration `extra` keys.

**Problems**

- Inline enumerations hide the items. The reader cannot scan these sets:
  - the request fields that a rollout cannot set
  - the podman leftovers that the worker looks for
  - the sources of the podman binary
- A parenthesis holds a second topic, with its own semicolon and its own instruction.
- The passive voice ("is refused", "is removed", "is quarantined") hides the actors.
- One bullet holds four topics:
  - backend selection
  - podman selection
  - the cleanup check
  - the request fields that the worker owns
- Two facts are unclear in the "Before". The code gives them:
  - The field checks apply only to rollout requests.
  - The profile's `podman_bin` comes before `SPROUT_PODMAN_BIN`.

**After**

The "After" has four topics, so it has four paragraphs. In the document, it becomes a subsection.

> **Owned sandboxes: podman by default, or microVMs.** A rollout request must give a
> `sandbox_image`. The `backend` in its profile selects where the rollout runs, the same way as
> for `harness run`:
>
> - `podman`, when the profile names no backend. The sandbox is a rootless container. Its rootfs
>   is a subvolume of the btrfs `store` that `ops/setup_podman.sh` makes.
> - `microvm`, when the profile names it. The sandbox is an AgentENV microVM.
>
> The worker refuses every other backend, because it can confirm cleanup only on these two.
> Before a rollout or grade attempt starts, the worker reads the backend from the effective spec.
> If the backend is not `podman` or `microvm`, the worker raises an error. The attempt does not
> start.
>
> After each attempt, the worker checks that each sandbox the attempt claimed is gone:
>
> - On `podman`, the worker looks for these leftovers:
>   - the container
>   - the network
>   - the rootfs subvolume
>
>   If a leftover remains, the worker removes it the same way `harness reap` does. Then the
>   worker looks again.
> - On `microvm`, AgentENV must return 404 for the sandbox.
>
> If the worker cannot confirm that a sandbox is gone, it quarantines the attempt.
>
> The worker and its attempt children use the same podman binary. The worker takes it from the
> first of these sources that is set:
>
> 1. `podman.podman_bin` in the profile's `backend`
> 2. the `SPROUT_PODMAN_BIN` environment variable. When the services start the worker, the
>    services' `podman` check sets this variable.
> 3. the podman that `ops/setup_podman.sh` installed, if it is executable
> 4. `podman` on `PATH`
>
> After you change the podman, restart the worker.
>
> The worker sets some fields of each rollout itself. When a client submits a rollout request,
> the Run Store rejects it if it sets one of these fields:
>
> - `session`
> - `journal_path`
> - `run_id`
> - `cwd`, to a value other than `.`
> - `keep_sandbox`, to true
> - one of these native-restoration keys in `extra`:
>   - `native_prefix`
>   - `native_home`
>   - `checkpoint_identity`

## 3. Procedure with its reason (mixed)

Source: `docs/RUNSTORE.md`.

**Before**

> Pre-pull the task images before parallel launches (`ops/prepull_images.py`): on podman this
> extracts each image's base into the store once instead of inside the first attempts; on a
> microVM it builds the template, and concurrent builds of one template race.

**Problems**

- One sentence holds the instruction and both backend-specific reasons.
- "this" and "it" have no clear noun.

**After**

> Pre-pull the task images before you start parallel attempts:
>
> 1. Run `ops/prepull_images.py`.
> 2. Start the attempts after the script finishes.
>
> On podman, the script extracts the base of each image into the store one time. Without it, each
> of the first attempts extracts the base itself. On a microVM, the script builds the template.
> If several attempts build the same template at the same time, the builds race.

The steps are STE. The paragraph after them is the NASA "why": it starts with what the script
does, then gives the consequence of skipping it.

## 4. State transitions (STE table)

Source: constructed "Before". The "After" was written from the job methods in
`src/sprout/runstore/store.py` and the `expire()` call in `src/sprout/runstore/manager.py`.

**Before (constructed)**

> Jobs are retried on failure where possible and quarantined if something goes wrong; stopped
> jobs are cancelled.

**Problems**

- The text names no actor and no resulting state.
- The conditions are vague: "where possible" and "something goes wrong".
- "stopped jobs are cancelled" is true only for queued jobs.

**After**

> A job moves through these states. The phase is in parentheses.
>
> | From | Trigger and condition | Actor | To |
> |---|---|---|---|
> | `queued` | `ready_at` has passed and `attempt_count` is less than `max_attempts`. | worker, `claim()` | `running` (`claimed`) |
> | `queued` | A cancel request or a stop request arrives. | `cancel_queued()`, `request_stop()` | `cancelled` |
> | `running` | The lease expires before the next heartbeat. | manager, `expire()` | `quarantined` (`lease_expired`) |
> | `running` | The attempt ends without a retry. | worker, `finish()` | `succeeded`, `failed` or `quarantined` |
> | `running` | The attempt ends with a retry for an infrastructure failure, and the conditions below are true. | worker, `finish(retry=True)` | `queued` (`retry_wait`) |
> | `quarantined` | The manager has a free slot, and the attempt payload is readable. | worker, `reconcile()` calls `adopt_quarantined()` | `running` (`reconciling`) |
>
> - `claim()` does these actions in one transaction:
>   - creates a new attempt
>   - adds 1 to `attempt_count`
>   - sets a lease of `lease_s` seconds
> - `finish()` puts a job back in `queued` only if `attempt_count` is less than `max_attempts`
>   and nobody requested a stop. Otherwise the job goes to the state that `finish()` received.
> - A retried job waits 30 s × `attempt_count`. `finish()` sets `ready_at` to that time.
> - A rollout retry needs a verified continuation. Without one, `finish()` raises `ValueError`.
> - `request_stop()` does not change the state of a running or quarantined job. It sets
>   `stop_requested_at`. The worker reads it at the next heartbeat.

The table cells keep their short enumerations inline, because a list cannot render in a cell.

## 5. Chinese description (STE structure rules)

Source: constructed "Before". The "After" uses the same code as example 4, plus
`reconcile()` in `src/sprout/runstore/worker.py`.

**Before (constructed)**

> 租约过期后会被隔离，之后进行对账处理。

**Problems**

- 没有主语。读者不知道谁隔离、谁对账。
- "进行对账处理"用名词代替动作。
- 没有写出结果状态。

**After**

> 如果 job 的租约在下一次心跳前过期，manager 调用 `expire()`。`expire()` 把 job 的状态改为
> `quarantined`，phase 改为 `lease_expired`。manager 有空闲槽位时，manager 调用 worker 的
> `reconcile()`。如果 attempt 的 payload 可读，`reconcile()` 调用 `adopt_quarantined()` 接管
> 这个 job。job 的状态变为 `running`，phase 变为 `reconciling`。

写出主语和条件以后，原文缺的两个条件就显出来了：manager 要有空闲槽位，payload 要可读。
