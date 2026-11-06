---
name: nasa-writing
description: "Writes, rewrites, or reviews text to NASA writing standards, in English or Chinese. Correspondence mode applies the NASA agency writing standard (NAII 1450.3 Ch. 4, formerly NPR 1450.10D Ch. 2) to replies, memos, emails, and status updates. Requirement mode applies the NASA Systems Engineering Handbook App. C and NPR 1400.1I (shall/will/should, one shall per sentence, banned vague terms). Procedure mode applies NASA procedure standards (TM-2016-219421, Flight Data File standards) and ASD-STE100 to steps, checklists, and WARNING/CAUTION/NOTE blocks. Report mode applies NASA SP-7084 and NASA/SP-2006-6114 to technical reports and design notes. Use when the user asks for NASA writing standard, NASA style, or 按 NASA 标准写/改写/审查; when writing or reviewing requirements, specs, procedures, runbooks, checklists, safety notices, memos, or technical reports; or when instructions say replies must follow the NASA writing standard. Not for creative or marketing copy."
version: 0.2.0
---

# NASA Writing Standard

NASA's agency writing standard is **NAII 1450.3, *Guidelines and Standards for NASA Letters and Memorandums*, Chapter 4 "Writing Standards"** (effective 1 Nov 2024, updated 24 Jun 2025). It implements NPR 1450.10E. It replaced Chapter 2 "NASA Writing Standards" of NPR 1450.10D, which NASA cancelled on 27 Sep 2024. The two texts are nearly the same. NAII 1450.3 covers correspondence. For technical documents, NASA uses other documents. This skill combines them into four modes:

| Mode | Text type | Primary source |
|---|---|---|
| **Correspondence** | chat replies, memos, emails, letters, status updates, announcements | NAII 1450.3 Ch. 4 |
| **Requirement** | requirements, specs, acceptance criteria, interface agreements, directives | NASA SEH (NASA/SP-2016-6105 Rev 2) Sec. 4.2 and App. C; NPR 1400.1I |
| **Procedure** | steps, checklists, runbooks, install and recovery instructions, safety notices | NASA/TM-2016-219421 *Designing Flightdeck Procedures*; Shuttle Flight Data File standards (USA005466); ASD-STE100 sentence rules |
| **Report** | technical reports, design notes, analyses, test results | NASA SP-7084 (grammar handbook); NASA/SP-2006-6114 (STI standards) |

The reader of NASA text cannot ask the writer a question: a flight controller at 3 a.m., a crew member in a suit, a reviewer who must sign a verification. An AI agent that reads a tool description, or a user who copies a command from a reply, is in the same position. The rules remove the places where such a reader can misread the text.

## When to Use

- The user asks for NASA writing standard, NASA style, or 按 NASA 标准.
- The text states obligations (shall, must, 应, 必须) or acceptance criteria.
- The text tells someone to do steps in sequence, or warns about a hazard.
- The text reports results, status, or analysis, and a wrong reading has a cost.
- The user's instructions (for example CLAUDE.md) say replies must follow the NASA writing standard. Then use Correspondence mode for the reply, Procedure mode for any step list in it, and keep the user's language.

Do not use it for creative, persuasive, or marketing text.

## Pick the Mode

1. The text states what a product or a person **shall** do → **Requirement**.
2. The text tells the reader to **do** steps in order → **Procedure**.
3. The text is a formal technical document (report, analysis, design note) → **Report**.
4. Otherwise (a reply, memo, email, or status update) → **Correspondence**.

A document can hold more than one mode. Apply each mode to its own part. Keep the mode choice internal unless the user asks for the analysis.

## Rules for All Modes

1. **Most important first.** Answers before explanations, conclusions before discussion, requests before justifications (NAII 4.3).
2. **One main topic per sentence** (NAII 4.8; SEH C.4 "one thought per requirement statement").
3. **Name the actor. Use active voice, who-does-what** (NAII 4.11). Passive voice only when the actor is unknown, unimportant, or obvious.
4. **The verb carries the action.** "consider", not "give consideration to" (NAII 4.12; SP-7084 2.2.2).
5. **One term for one thing.** Use the name that the reader sees on the screen, label, or panel (TM-2016-219421 2.5.3; NASA-STD-3001 Vol. 2 [V2 10006]).
6. **A noun after every demonstrative.** "This valve", not "This" (SEH C.4; SP-7084 1.3.4).
7. **Define each acronym at first use**, unless the reader knows it. Do not define an acronym that appears only once (NAII 4.14).
8. **Numbers carry the claim.** Give the value, the unit, and the tolerance or range if the source has them. Space between number and unit symbol: "35 mm" (SP-6114 5.5.3).
9. **Keep every hedge at its original strength.** "may have failed" stays "may have failed". A hedge is content. This rule wins over every brevity rule.
10. **Add no fact.** Do not supply a cause, a value, a tolerance, a date, or an actor that the source does not state. Mark the gap as TBD, or flag it.

## Correspondence Mode

Full rules and word lists: `references/correspondence.md`.

- Start with the key sentence. "Start fast, explain as necessary, then stop" (NAII 4.3).
- Use "we" for the team or organization, "I" for yourself, "you" for the reader (NAII 4.10).
- Average 20 words or less per sentence. Divide long sentences (NAII 4.8).
- Short paragraphs, one topic each. Use bullets for lists, but few levels (NAII 4.9).
- Plain, concrete words: "use", not "utilize"; "begin", not "commence" (NAII 4.13).
- Positive form when it is accurate: "It will be ready on Monday", not "It will not be ready until Monday". No more than one negative per sentence (NAII 4.7).
- No "It is ..." unless "it" refers to something earlier. Limit "there is/there are" (NAII 4.5).
- No contractions in formal writing. Spell out numbers ten or less, except with units, percentages, dates, and times (NAII 4.4, 4.13; GPO Style Manual).
- Neutral tone. No rubber-stamp closing sentences (NAII 4.6).

## Requirement Mode

Full rules, checklist, and examples: `references/requirements.md`.

- **shall** = requirement. **will** = fact, purpose, or expected outcome. **should** = goal or good practice. **may** = permission. **can** = capability. (SEH C.1; NPR 1400.1I P.2b.)
- Declare one verb convention per document and keep it. Sources differ: some NASA documents use "must" (NASA-STD-3001), and the Shuttle FDF standards use "will" for a soft standard.
- One "shall" per sentence. One subject, one predicate.
- Form: "[product] shall [verb] [object] [value and tolerance]" or "[responsible party] shall [action]".
- State **what** is needed, not **how**. Move design solutions to the rationale and operations to the ConOps.
- State it positively where a positive form exists, not "shall not".
- No ambiguous or caveat terms: as appropriate, as applicable, whenever possible, as soon as possible, in a timely manner, etc., and/or, but not limited to (SEH C.4; NPR 1400.1I).
- No unverifiable terms: flexible, easy, sufficient, safe, adequate, user-friendly, fast, small, large, maximize, minimize, robust, quickly, and the rest of the SEH C.4 list.
- An open value is **TBD**, or a best estimate marked **TBR** with rationale, owner, and due date. Never invent the value.

## Procedure Mode

Full rules, sources, and examples: `references/procedures.md`.

- One action per numbered step. Write the step as an imperative: verb, then object (TM-2016 2.5.1; FDF 7.1).
- Put the condition **before** the action: "IF the light is on, THEN go to step 4." Not "Go to step 4 if the light is on." (FDF 17.1; TM-2016 2.5.8.)
- Put each WARNING, CAUTION, or NOTE **immediately before** the step it applies to, as its own block, label in capitals.
  - WARNING: hazard to people. CAUTION: hazard to equipment. NOTE: amplifying information only. Define the terms once and use them consistently (FDF 14; TM-2016 2.5.11).
  - A WARNING or CAUTION names one hazard, its consequence, and any time limit. It may state a prohibition ("Do not ..."). It contains no procedure step. Put the action that avoids the hazard in the next step.
- Name controls, fields, commands, and files exactly as the reader sees them. Put commands in code formatting.
- Give numbers in Arabic numerals with units. Use ranges ("28 to 32 V"), not error bands ("30 ± 2 V") (TM-2016 2.5.4).
- A check step states the expected value, not "checked", "set", or "as required" (TM-2016 2.5; CR-177549).
- Cross-references are explicit: "Go to step 7." Mark the end of the procedure.
- ASD-STE100 sentence rules: at most 20 words per sentence, no semicolons, no phrasal verbs, simple tenses. For the full STE rules and the `ste-lint.py` linter, use the sibling **asd-ste100** skill (`../asd-ste100/SKILL.md`).

## Report Mode

Full rules and examples: `references/reports.md`.

- Lead with the result. The abstract is "informative rather than descriptive". The conclusions add no new material (SP-6114 1.3.2).
- Make the real action the verb and its actor the subject. Not "It is believed that", "There are" (SP-7084 2.2.1). "We" is acceptable.
- Passive voice is acceptable when the actor is unknown or unimportant, or the receiver needs the emphasis (SP-7084 1.4.3).
- Tense: past for what was done in this study. Present for what a figure or table shows, for explanations, and for conclusions (SP-7084 1.4.1).
- Cut wordy phrases, but stop when the sentence has one reading (SP-7084 2.4.1).
- Compare like with like. "whether", not "if", for alternatives. Keep parallel items parallel.
- Units per SP-6114 Sec. 5: "20 lb", "s" not "sec", SI first. State which unit system the work used.
- Semicolons are allowed in Report mode (SP-7084 3.15).

## Chinese Text

All rules apply to Chinese with the mapping in `references/chinese.md`: shall → 应, should → 宜, may → 可, can → 能. Use the verb, not 进行/开展 + noun. Avoid 被 when the actor is known. Put a noun after 这/该/其. Keep 可能 and other hedges. The English-only rules (contractions, spelling out numbers ten or less) do not apply.

## Process

1. Pick the mode for each part of the text.
2. Read the input once for meaning. Do not start to rewrite until you know what it must still say.
3. Check each sentence against the rules for its mode. For a mechanical first pass, run `python3 scripts/nasa-lint.py --mode <mode> FILE` (stdin when no file, `--json` for structured output, `--list-rules` for the rule table). The linter checks patterns only and never flags hedges.
4. Rewrite each sentence that breaks a rule. Keep every fact, condition, number, scope qualifier, and hedge. If a shorter form loses precision, keep the longer form and flag it.
5. Mark each missing value as TBD (Requirement mode) or flag it. Do not fill it.
6. If the input already complies, say so. Do not force changes.

## Output Format

**Rewrite (default):** output the rewritten text only. No preamble, no mode announcement, no change summary. Add one line `Kept as-is:` only when you kept a longer phrase on purpose, with the reason. Add one line `Open items:` only when the rewrite contains TBD or a flagged gap.

**Review (when the user asks to review, check, or audit):** output a table, worst problem first:

| # | Location | Rule | Problem | Fix |
|---|---|---|---|---|
| 1 | REQ-012 | One shall per sentence (SEH C.4) | Two obligations | Split into REQ-012a and REQ-012b |

Then one line with the mode and the count.

**Rule table (when the user asks "show the diff", "which rules", "explain the changes"):** `| Rule | Original | Rewrite |`, then one line on what you did not change and why.

**Writing from scratch (for example a reply under a CLAUDE.md rule):** apply the rules silently. Do not mention this skill.

## Boundaries

**Will:**
- Write, rewrite, and review text to the rules above, in English or Chinese.
- Keep every fact, number, condition, and hedge of the source.
- Mark open values as TBD or TBR and list them.

**Will not:**
- Claim compliance with a NASA program's document requirements. NPR 7123.1, NPR 1400.1, the project template, and center style guides override this skill.
- Invent a value, tolerance, cause, actor, or verification method. It marks the gap.
- Convert "shall" to "must" in a NASA requirement, or turn a hedge into a fact.
- Make empty content useful. A rewrite fixes form. If the text says nothing, say so.
- Shorten past clarity. The goal is one reading, not the fewest words.

## Additional Resources

- `references/correspondence.md` — NAII 1450.3 Ch. 4: the NASA writing standard, with its word lists. History from NPR 1450.10D.
- `references/requirements.md` — SEH Sec. 4.2 and App. C, NPR 1400.1I: terms, statement form, checklists, term lists, examples.
- `references/procedures.md` — steps, conditions, checklists, WARNING/CAUTION/NOTE, ASD-STE100 sentence rules.
- `references/reports.md` — SP-7084 grammar and sentence rules; SP-2006-6114 report structure, numbers, units, symbols.
- `references/chinese.md` — how each rule maps to Chinese.
- `examples/before-after.md` — worked rewrites for each mode.
- `scripts/nasa-lint.py` — stdlib-only linter. `--selftest` runs its tests.
