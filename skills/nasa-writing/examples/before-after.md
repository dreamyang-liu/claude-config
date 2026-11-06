# Before / After Examples

These examples are original, written for this skill. They are not quotes from NASA documents, except where a line says "from SEH". Each example says which rules it applies and what it did **not** change.

<!-- nasa-lint-ignore-start -->

## Requirement mode

### R1 — Two obligations and vague terms

**Before:**
> The flight software must be robust and should recover quickly from faults, logging all errors, warnings, etc. as appropriate.

**Problems:**
- "must" is not a NASA requirement term. "should" makes part of it a goal (SEH C.1). The writer probably means one binding requirement, but the text mixes two strengths.
- Three thoughts in one sentence: robustness, recovery, logging (SEH C.4 Clarity).
- Unverifiable: robust, quickly. Ambiguous: etc., as appropriate (SEH C.4).

**After:**
> FSW-001: The flight software shall recover from a single processor reset within TBD s.
> FSW-002: The flight software shall log each fault event.
> FSW-003: The flight software shall log each warning event.

Open items: FSW-001 recovery time is TBD. "robust" in the source has no measurable criterion. Define the fault set (which faults) before FSW-001 is verifiable.

**Not done on purpose:** the rewrite does not choose a recovery time, and it does not keep "should". If the author meant "should" as a goal, keep FSW-001 as a goal: "The flight software should recover ... within 10 s." Ask the author.

### R2 — Implementation inside a requirement

**Before:**
> The ground system shall use a PostgreSQL database to store telemetry so that operators can query it.

**Problems:** the requirement states **how** (PostgreSQL), not **what** (SEH C.2). "so that operators can query it" describes an operation (ConOps).

**After:**
> GND-010: The ground system shall store each received telemetry frame for at least TBD days.
> GND-011: The ground system shall return the telemetry frames for an operator-specified time range within TBD s of the query.
> Rationale: Operators query stored telemetry during anomaly investigation. The project selected PostgreSQL in trade study TBD.

**Not done on purpose:** the database choice is kept in the rationale, not deleted. The SEH says to record why an implementation was chosen if a requirement names one.

### R3 — Already compliant (from SEH Sec. 4.2.1.2.2)

> The TVC shall gimbal the engine a maximum of 9 degrees, ± 0.1 degree.

No change. One subject, one "shall", a value with a tolerance.

## Correspondence mode (NAII 1450.3 Ch. 4)

### C1 — Status update

**Before:**
> It is worth noting that after a thorough investigation was conducted by the team, it was determined that the outage was most likely caused by the certificate rotation job, which has been fixed; this should prevent the issue going forward.

**Problems:**
- The answer (the cause) is buried in the middle (NAII 4.3).
- "It is worth noting that" and "it was determined that" delay the subject (NAII 4.5; SP-7084 2.2.1).
- "an investigation was conducted" hides the verb (NAII 4.12).
- One sentence holds the finding, the fix, and a prediction (NAII 4.8).

**After:**
> The certificate rotation job most likely caused the outage. The job is now fixed. This fix should prevent the outage from recurring. The team found the cause during its investigation.

**Not done on purpose:** "most likely" and "should prevent" stay. The source does not claim certainty, so the rewrite does not claim it. "is now fixed" keeps the current-state meaning of "has been fixed" without inventing who fixed it. "thorough" is dropped: it is a judgment, not a fact. If the reader needs the scope, state it ("The team reviewed 3 days of logs") — but only if the source gives it.

### C2 — Positive form and the "By whom?" test

**Before:**
> The new cluster won't be available until the security review has been completed, and access can't be granted unless the form isn't missing any fields.

**Problems:** contractions (NAII 4.4); four negatives, one of them a double negative (NAII 4.7); passive with no actor (NAII 4.11); two topics in one sentence.

**After:**
> The new cluster will be available after the security review is complete. Access requires an access form with all fields complete.

Open items: the source does not say who does the security review or who grants access. The rewrite does not invent an actor. It also does not turn the condition into a command ("Submit the form"), because the source states a condition, not an instruction.

### C3 — Chinese reply

**Before:**
> 经过我们对日志进行了详细的分析之后，发现这可能是由于配置文件被错误修改导致的，建议尽快进行修复等。

**Problems:** the answer is not first. 进行分析 and 进行修复 put the action in a noun. 这 has no noun. 被 has no actor. 等 ends an incomplete list. One sentence holds three thoughts.

**After:**
> 故障可能由配置文件的错误修改导致。我们详细分析了日志后得出这个结论。建议尽快修复该配置文件。

**Not done on purpose:** 可能 stays. The rewrite does not name who changed the file, because the source does not say. 尽快 stays: in a reply it states urgency, and the source gives no deadline. (In Requirement mode, 尽快 is unverifiable and needs a value.) 等 is dropped, because the source names no other action. If other actions exist, list them.

## Report mode (SP-7084, SP-2006-6114)

### P1 — Lead with the result

**Before:**
> We ran the benchmark on three machines using the default settings and the new allocator, and after collecting the results and averaging them we saw that the latency went down from 41 ms to 29 ms on average.

**After:**
> The new allocator reduced mean latency from 41 ms to 29 ms. We ran the benchmark on three machines with default settings and averaged the results.

The result comes first. The method follows. No number changed.

### P2 — Tense and figures

**Before:**
> A comparison of the throughput for the two configurations was shown in figure 3, and it was found that the data shows config B is 18% faster.

**Problems:** noun for the action ("A comparison ... was shown", SP-7084 2.2.2); past tense for what a figure shows (SP-7084 1.4.1); "it was found that" (SP-7084 2.2.1); "data" is plural (SP-7084 1.4.4).

**After:**
> Figure 3 compares the throughput of the two configurations. Configuration B is 18 percent faster than configuration A.

**Not done on purpose:** "18%" became "18 percent" only because this example is running text. In a table or graph, keep "%" (NAII 4.20; SP-6114 2.6.4).

## Procedure mode (TM-2016-219421, FDF standards, ASD-STE100)

### S1 — Runbook steps with a hazard

**Before:**
> 1. Stop the database and then delete the stale lock file, but be careful not to delete the wal directory since that would lose data.
> 2. Restart the service if needed and check the status.
> 3. The status should be checked as required.

**Problems:**
- Step 1 holds two actions and a hazard (FDF 7.1a, 14.0e).
- The hazard is inside a step, not in a CAUTION before the step (FDF 14.0a; TM-2016 2.5.11).
- Step 2 puts the condition after the action ("if needed"), and "if needed" gives no condition (FDF 17.1b).
- Steps 2 and 3 give no expected value ("check the status", "as required") (CR-177549 6.2.3).
- Step 3 is passive and uses "should" (TM-2016 2.5.1).

**After:**
> 1. Stop the database: `systemctl stop pg`.
>
> > **CAUTION**
> > Do not delete the `wal/` directory. The database will lose data.
>
> 2. Delete the stale lock file: `rm /var/run/pg/lock`.
> 3. Start the service: `systemctl start pg`.
> 4. Verify that the status is `active`: `systemctl is-active pg`.
> 5. IF the status is not `active`, THEN TBD.
>
> End of procedure.

Open items: the source does not give the lock-file path, the expected status, or the recovery action for a failed start. `/var/run/pg/lock`, `active`, and the commands are placeholders for this example only. In a real rewrite, keep the source's names, and write TBD where the source gives none.

**Not done on purpose:** "since that would lose data" became the consequence line of the CAUTION. The rewrite does not make the consequence stronger or more specific than the source.

### S2 — Checklist responses

**Before:**

| Item | Response |
|---|---|
| Disk space | checked |
| Replicas | set |
| Backup | as required |

**After:**

| Item | Response |
|---|---|
| Disk space free | more than 20 GB (TBR) |
| Replica count | 3 |
| Last backup | less than 24 h old (TBR) |

The response states the value that the reader must see (CR-177549 6.2.3). The values are TBR because the source gives none.

<!-- nasa-lint-ignore-end -->
