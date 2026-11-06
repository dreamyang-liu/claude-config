# Comment examples

Each "Before" is quoted from this repository, except where it is marked as constructed. Each
"After" was checked against the code.

The examples quote the code of 2026-10-16. Since then, ADR-0006 removed the `quarantined` state,
`reconcile()` and the lease that each attempt renewed. Use the examples for the writing, not for
the facts: check each fact against the code and `docs/` of today.

## 1. Module docstring that contains its implementation

Source: `src/sprout_sandbox/podman.py`, before the pool moved to `src/sprout_sandbox/podman_pool.py`. The docstring had 100 lines. This is the start of it.

**Before**

```python
"""Sandboxes as rootless podman containers whose rootfs is a btrfs subvolume.

The microVM backend needs an AgentENV server, a patched Firecracker and
``/dev/kvm``. This one needs ``podman``, ``btrfs-progs`` and one directory on a
btrfs filesystem -- the *store*, made once as root by ``ops/btrfs_store.sh`` --
and runs everything else as the unprivileged user, on the same runtime binary,
driven by the same ``SandboxSession``; a branch is a second run started from a
snapshot id with the retained history. It is a client of two CLIs, ``podman``
and ``btrfs``: every operation below is one or two commands, and those are what
a person debugging a leftover container or subvolume reaches for.

**The image is extracted once; every sandbox is a snapshot of it.** podman keeps
an image as a stack of layers and snapshots a container with ``commit``, which
copies the whole writable layer, stacks a layer per generation of branches and
never compacts (the first version of this backend did that: 30 s per commit of
a 1.5 GB layer, a 500-layer ceiling and a squash policy to stay under it). A
btrfs snapshot is a metadata operation -- milliseconds, whatever the rootfs
holds -- and each one is an independent subvolume, so nothing stacks and
nothing needs squashing: ``Snapshot.rootfs_layers`` is ``None`` here. The pool
extracts an image's rootfs into a read-only *base* subvolume once (``podman
export`` piped through ``tar`` under ``podman unshare``, so file ownership maps
into the user namespace exactly as podman's own storage does), [...]
```

**The change test, sentence by sentence**

| Sentence | Result of the change test | Where it goes |
|---|---|---|
| needs `podman`, `btrfs-progs` and a store | stays true | the docstring |
| a snapshot takes milliseconds, and `Snapshot.rootfs_layers` is `None` | stays true. Callers rely on it. | the docstring, as a guarantee |
| the first version used `podman commit`, 30 s per commit | history | a `docs/` file |
| `podman export` piped through `tar` under `podman unshare` | false if the extraction changes | an implementation comment at the extraction code |
| each operation is one or two commands, for a person who debugs | maintainer information | an implementation comment, or a `docs/` file |

**After**

```python
"""Sandboxes as rootless podman containers whose rootfs is a btrfs subvolume.

Needs ``podman``, ``btrfs-progs`` and a btrfs *store* that ``ops/btrfs_store.sh``
makes once, as root. Everything else runs as the unprivileged user.

A sandbox starts from an image or a snapshot id in the same way. A snapshot takes
milliseconds and never stacks (``Snapshot.rootfs_layers`` is ``None``). Snapshots
are disk-only: ``disk_only=False`` raises ``NotImplementedError``.
Design and measurements: ``docs/<file>.md``.
"""
```

The "After" has 10 lines, half the 20-line limit that `gate/checks/comment_length.py` sets for a
module docstring. The rest of the docstring gets the same test. The mechanism moves to comments at the code
that it describes. The rationale and the measurements move to a `docs/` file, written with the
doc-writing skill.

## 2. Interface comment that describes another module, and has gone stale

Source: `ToolResult` in `src/sprout/harness_core/result.py`, now `src/sprout/worker/tools/result.py`. The package names in the example are the names of that time.

**Before**

```python
@dataclass
class ToolResult:
    """Result of one tool call.

    ``output`` and ``error`` are alternatives, not two views of one message:
    ``output`` is what the tool produced, ``error`` is the tool refusing to
    produce anything (bad arguments, no sandbox, a transport failure). A command
    that ran and exited non-zero has real output and no error -- ``success``
    already says it failed.

    Storing one message in both fields costs twice, because the agent loop
    renders a failure as ``f"Error: {error}\\n{output}"``: the model reads the
    same bytes twice and pays for both.
    """
    success: bool
    output: str
    error: Optional[str] = None
    #: What running a command produced, when the tool ran one and had something
    #: to report beyond its stdout (:class:`CommandOutcome`: ``exit_code``,
    #: ``stdout``, ``stderr``, ``timed_out``, byte counts, truncation flags).
    #: ``None`` for a plain success, a refusal, or a tool that runs no command.
    #: The agent runtime reads it to compose what the model sees
    #: (``agents/mini_swe/runtime.py``); ``ToolAccess`` reads it to tell a
    #: settled command from one whose outcome is unknown.
    outcome: Optional["CommandOutcome"] = None
```

**Problems**

- The first paragraph is a good interface comment. It gives the meaning of the fields.
- The second paragraph explains the rule with the implementation of another module. That
  implementation changed:
  - The string `f"Error: {error}\n{output}"` occurs nowhere else in the repository.
  - `harness_agents/mini_swe/runtime.py` now builds the observation from
    `outcome.stdout + outcome.stderr`.
- The `#:` comment names the readers of the field. One of the two paths no longer exists,
  because `agents/` moved to `harness_agents/`.
- The `#:` comment copies the field list of `CommandOutcome`. That list belongs to
  `CommandOutcome`, and the copy goes stale when `CommandOutcome` changes.

**After**

```python
@dataclass
class ToolResult:
    """Result of one tool call.

    ``output`` and ``error`` are alternatives, not two views of one message.
    ``output`` is what the tool produced. ``error`` means that the tool refused
    to produce anything, for example because of bad arguments, no sandbox or a
    transport failure. A command that ran and exited non-zero has real output
    and no error. ``success`` already says that it failed.
    """
    success: bool
    output: str
    error: Optional[str] = None
    #: What running a command produced (:class:`CommandOutcome`). ``None`` for a
    #: plain success, a refusal, or a tool that runs no command.
    outcome: Optional["CommandOutcome"] = None
```

## 3. Abstract class whose contract is only in the module docstring

Source: `src/sprout/harness_core/slot.py`, now `src/sprout/worker/agents/slot.py`. The package names in the example are the names of that time.

**Before**

```python
"""Agent slot contract.

A *slot* runs one agent against one task and streams normalized events into a
journal. Slots are black boxes to the orchestrator: the contract below is the
whole interface. The driver lives in harness_agents/.

Design constraints:
- ``run()`` is synchronous from the caller's perspective; async drivers own
  their own event loop internally.
- Everything a slot learns goes into the journal *as it happens* -- a killed
  run must still leave a usable trajectory [...]
- Tools are reached through the run's :class:`~sprout.harness_tools.access.ToolAccess`
  [...]; the slot decides how to offer them to its model and never reaches the
  sandbox any other way.
"""
[...]
class AgentSlot(ABC):
    """Contract every driver implements."""

    @abstractmethod
    def run(self, task: TaskSpec, journal: JournalWriter, tools: Any) -> SlotResult:
        """Execute the task through ``tools``, streaming events into ``journal``."""
```

**Problems**

- An implementer reads `AgentSlot`. Its docstring names a contract but does not give it.
- `run()` does not give the possible values of `status` in its result.

**After**

```python
"""The agent slot interface: ``AgentSlot``, ``TaskSpec`` and ``SlotResult``.

The drivers are in ``harness_agents/``.
"""
[...]
class AgentSlot(ABC):
    """Runs one agent on one task, and streams normalized events into a journal.

    The orchestrator sees a slot only through this class. Every implementation
    must keep these rules:

    - ``run()`` is synchronous for the caller. An async driver owns its own
      event loop.
    - The slot writes each event to the journal when it occurs. A killed run
      must still leave a usable trajectory.
    - The slot reaches the sandbox only through ``tools``, the run's
      ``ToolAccess``. The slot decides how to offer the tools to its model.
    """

    @abstractmethod
    def run(self, task: TaskSpec, journal: JournalWriter, tools: Any) -> SlotResult:
        """Run ``task`` through ``tools``, and return its result.

        ``SlotResult.status`` is ``completed``, ``error``, ``timeout`` or ``killed``.
        """
```

## 4. Good method docstring with STE wording fixes

Source: `Store.request_stop` in `src/sprout/runstore/store.py`.

**Before**

```python
def request_stop(self, job_id: str) -> dict:
    """Stop a job: a queued one is cancelled, a running one stops at its next heartbeat.

    The worker running it stops the attempt's process, reclaims what it
    held and finishes the job ``failed`` with ``stop_reason: "stopped"``,
    never to run again. A finished job is left as it is; asking twice is
    asking once.
    """
```

**Problems**

- The information hiding is good. The docstring gives behavior, not SQL.
- The return value is not given.
- The docstring does not cover a quarantined job, which the code also accepts.
- "asking twice is asking once" is a figure of speech. It does not say what stays the same.

**After**

```python
def request_stop(self, job_id: str) -> dict:
    """Ask a job to stop, and return the job as it is after the request.

    If the job is queued, its state changes to ``cancelled``. If it is running,
    the worker that runs it reads the request at its next heartbeat. The worker
    stops the attempt's process and reclaims what the attempt held. Then it
    finishes the job ``failed``, with ``stop_reason: "stopped"``. The job does
    not run again.

    If the job is quarantined, the call records the request, and ``finish()``
    does not requeue the job. The call does not change a finished job. A second
    call does not change the state or the stop time.
    """
```

## 5. Implementation comments and a column comment

**A "what" comment (constructed)**

```python
# Add one to the attempt count.
attempt_count += 1
```

The comment repeats the code. Remove it.

**A history comment (constructed)**

```python
# Switched to one network per sandbox because the shared bridge broke DNS.
```

The comment tells the history, not the reason that stays true. The facts come from the
`src/sprout_sandbox/podman.py` docstring.

```python
# One bridge per sandbox: on a shared one, a container that joins or leaves can move
# the gateway MAC, and the others lose traffic until their neighbour entries refresh.
```

**A good "why" comment**

Source: `src/sprout/runstore/worker.py`, now `src/sprout/worker/attempts.py`.

```python
# Queue time belongs to the group deadline too. Bound child
# startup/provisioning, not only the agent's model requests.
effective["timeout_s"] = remaining_timeout(rollout_contract, effective.get("timeout_s", 3600))
```

The comment gives a reason that the line does not show. Keep it as it is.

**A column comment with a semicolon**

Source: `src/sprout/runstore/schema.sql`.

```sql
-- Set by a stop request; the worker running the job reads it at each heartbeat.
```

```sql
-- A stop request sets this column. The worker that runs the job reads it at each heartbeat.
```
