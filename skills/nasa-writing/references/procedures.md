# Procedure Mode — NASA Procedure and Checklist Standards

## Sources

| Short name | Document | Where |
|---|---|---|
| **TM-2016** | Barshi, Mauro, Degani, Loukopoulou, *Designing Flightdeck Procedures*, NASA/TM-2016-219421, Oct 2016, Sec. 2.5 | https://ntrs.nasa.gov/citations/20160013263 |
| **FDF** | *Space Shuttle Flight Data File (FDF) Standards and Specifications*, USA005466 Rev. C CPN-1, 28 Jun 2006 (Annex C of the JSC Crew Procedures Management Plan) | Public copy on archive.org only: https://archive.org/details/fdfstandards |
| **CR-177549** | Degani and Wiener, *Human Factors of Flight-Deck Checklists: The Normal Checklist*, NASA CR-177549, 1990 | https://ntrs.nasa.gov/citations/19910017830 |
| **CR-177642** | Degani and Wiener, *On the Design of Flight-Deck Procedures*, NASA CR-177642, 1994 | https://ntrs.nasa.gov/citations/19940029437 |
| **STD-3001** | NASA-STD-3001 Vol. 2 Rev. E, 2025 | https://ntrs.nasa.gov/citations/20250004555 |
| **HIDH** | *Human Integration Design Handbook*, NASA/SP-2010-3407/REV1, 2014 | nasa.gov |
| **NAII** | NAII 1450.3 Ch. 4 (see `correspondence.md`) | nodis3.gsfc.nasa.gov |
| **STE** | ASD-STE100 Issue 9 sentence rules, as summarized in [danyuchn/asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill) (MIT) | — |

The ISS procedure standard (SSP 50253, *Operations Data File Standards*) exists but has no public copy. FDF Sec. 1.2 says that SSP 50253 takes precedence for ISS procedures. This file does not use SSP 50253.

CR-177549 says of its own guidance: "These considerations are not specifications." Treat all of this file as practice for a reader who executes steps, not as a compliance standard.

**This skill's transfer:** a runbook, an install guide, a recovery procedure, or a step list inside a chat reply is a procedure. The reader executes it, often under time pressure, and cannot ask the writer.

## 1. Steps

| Rule | Do | Don't | Source |
|---|---|---|---|
| Write each step as an imperative | Open valve 3. | The operator opens valve 3. / You should open valve 3. | TM-2016 2.5.1; NAII 4.4 |
| Verb first, then object | Insert the film into the camera. | The film is inserted into the camera. | FDF 7.1h |
| Positive commands, active verbs, short sentences | Close the hatch. | Do not leave the hatch open. | TM-2016 2.5.1 |
| One action per line | 1. Stop the service. 2. Delete the lock file. | 1. Stop the service and delete the lock file. | FDF 7.1a; TM-2016 2.5.6 |
| Number the steps with a simple scheme | 1, 2, 3 (2a, 2b for sub-steps if needed) | 1.2.3.4.1 | TM-2016 2.5.2, 2.5.6 |
| One action can apply to several items of the same kind | Set APU CNTLR PWR (three) to ON. | Three separate steps for identical switches | FDF 7.2 |

Exception to "one action per line": an action plus its expected result is one step: "Restart the service. The status changes to `active`."

## 2. Conditions and branches

- "Any conditional statement must always be given before the action(s) to which it applies." Do not put the condition in parentheses after the action (FDF 17.1b).
- "Conditions should always precede actions" (TM-2016 2.5.8). Use IF, WHEN, THEN, AND, OR with one fixed meaning each. Avoid AND combined with OR in one condition.
- Indent the steps that depend on a condition under it (FDF 17.1).
- Make each cross-reference explicit: "Go to step 7." / "GO TO [procedure] Step [#]" (TM-2016 2.5.6).
- Use "go-in, stay-in": once the reader enters a branch, keep them in it until it ends (TM-2016 2.5.9).
- Mark the end of the procedure (TM-2016 2.5.9).

| Do | Don't |
|---|---|
| 4. IF the service does not start, THEN go to step 9. | 4. Go to step 9 (if the service does not start). |
| 5. WHEN the light goes off, release the button. | 5. Release the button once the light goes off. |

## 3. WARNING, CAUTION, NOTE

### Definitions

| Label | FDF definition (Sec. 14) | TM-2016 2.5.11 |
|---|---|---|
| **WARNING** | "Warnings will provide information or instructions necessary to ensure crew safety." | "sometimes used to refer to hazards to people" |
| **CAUTION** | "Cautions will provide information or instructions necessary to prevent hardware damage or malfunction." | "cautions are used for hazards to equipment" |
| **NOTE** | "Notes will provide amplifying information of a general nature." | — |

TM-2016: "Often 'warning' and 'caution' are used as synonyms." "The meaning of these words should be defined and used consistently." This skill uses the FDF definitions. **For software (this skill's mapping):** use CAUTION for loss of data, loss of service, and damage to a system. Use WARNING only for harm to people.

Do not confuse these with alarm classes. STD-3001 defines a "Warning" alert as an event "that requires immediate action" and a "Caution" alert as an event "that needs attention but not immediate action". Those definitions are for displays and alarms, not for procedure text.

### Content

- "Each warning or caution should identify: a single hazard, the consequences of the hazard, and any critical time constraints. Actions should not appear in warnings or cautions." (TM-2016 2.5.11)
- "Use negative imperative active voice." Example: "CAUTION: Do not attempt manual restart if automatic start fails. Starter may be damaged." (TM-2016 2.5.11). A prohibition is allowed. A procedure step is not.
- "Procedural steps will not be placed within notes, cautions, or warnings." (FDF 14.0e). A warning or caution has no step number.
- "If actions are required to correct or avoid a hazard, the actions will immediately follow the boxed information." (FDF 14.0f)
- Keep them short. "If the crew cannot affect the situation, do not address it." (FDF 14.0g)
- "Cautions and warnings will not be used to tell the crew what will happen if they do not follow procedures." (FDF 14.0h)
- Use them in addition to steps, not instead of steps, and use them sparingly. "Overuse of warnings will decrease their effectiveness." (TM-2016 2.5.11)

### Placement and form

- "Notes, cautions, and warnings will be placed immediately before the operation they are clarifying." (FDF 14.0a)
- Put them on the same page as, and before, the steps they apply to. Keep them graphically separate from the steps. (TM-2016 2.5.11)
- The label is a capitalized word: WARNING, CAUTION, NOTE (FDF 14; TM-2016 2.5.5 and 2.5.7 reserve capitals for these and for IF, THEN, NOT). In Markdown, use a separate block, for example a blockquote or a GitHub alert (`> [!WARNING]`).
- HIDH 10.11.4 is about physical hazard **labels**, not procedures. A label must "clearly identify the hazard, and the action to avoid that hazard (e.g. Caution: Hot Surface. Do Not Touch Without Gloves)". That is why a label may contain an action and a procedure caution may not.

### Example

> **CAUTION**
> Do not delete the `wal/` directory while the database runs. The database will lose all transactions since the last checkpoint.

3. Stop the database: `systemctl stop pg`.
4. Verify that the status is `inactive`: `systemctl is-active pg`.

## 4. Names, abbreviations, numbers

- "Match flightdeck nomenclature." (TM-2016 2.5.3) For software: write the exact button text, menu path, field name, command, and file path. Put them in code formatting.
- "Operational nomenclature shall be standardized throughout a system." (STD-3001 [V2 10006]) "Labels and procedures referring to the labeled items should be consistent." (HIDH 10.11.2)
- Do not use one word as both a noun and a verb (TM-2016 2.5.3; also STE).
- Use only abbreviations that are defined and common in the field (TM-2016 2.5.3; HIDH 10.11.2.2).
- Use Arabic numerals and "Include units of measurement" (TM-2016 2.5.4).
- "Do not specify numbers in greater precision than is necessary, or than can be read from instruments." (TM-2016 2.5.4)
- Use ranges, not error bands: "10-20 KIAS" rather than "15 ± 5 KIAS". The reader should not calculate (TM-2016 2.5.4). Lint: `step-plus-minus`.
- Use capitals "very sparingly and only for meaningful emphasis" (TM-2016 2.5.5).

## 5. Checklists and verification steps

- Two methods (CR-177549 3.1.4): **challenge-verification-response** (the reader does the work, then the checklist confirms it) and **do-list** (call, do, respond). Say which one the checklist uses.
- "Checklist responses should portray the desired status or the value of the item being considered (not just 'checked' or 'set')." (CR-177549 6.2.3) TM-2016: "The generic responses of 'set,' 'checked,' or 'as required' may not be very informative". Lint: `vague-response`.
- Challenge text matches the label. Response text gives the state or value: `Fuel pump — ON`, `Disk free — more than 20 GB`.
- FDF verification format: √OBJECT − STATE. If the item is wrong and the reader can correct it, correct it. Otherwise stop and contact the responsible team, unless the procedure gives an IF branch (FDF 12.0).
- Order: most critical items first. Then by location or by flow. Put the completion call last (CR-177549 guidelines 6, 8, 10).
- Split a long checklist into task checklists (CR-177549 guideline 7). "A checklist should be as long as it needs to be, and as short as possible." (TM-2016)
- A procedure "should lead to a totally predictable outcome." (CR-177642 #15) State the logic behind the procedure somewhere the reader can find it (CR-177642 #20).

FDF crew checklists use a telegraphic style: no articles, "and" replaced by a comma (FDF 7.1b–c). ASD-STE100 forbids dropped words. **This skill keeps articles in runbooks and chat replies**, and uses the telegraphic `ITEM — STATE` form only in a checklist table.

## 6. Sentence rules (ASD-STE100, via the asd-ste100 skill)

Apply these to every sentence inside a step, a WARNING, a CAUTION, or a NOTE. The sibling skill `../asd-ste100/` has the full rules and a linter: `python3 ../asd-ste100/scripts/ste-lint.py FILE`.

| Rule | Do | Don't |
|---|---|---|
| Sentence length | at most 20 words in a step | long compound sentences |
| No semicolons (STE 8.1) | two sentences | Open the valve; wait 5 s. |
| No phrasal verbs (STE 9.3) | Remove the panel. Start the job. | Take off the panel. Spin up the job. |
| Simple tenses | The pump stops. | The pump will have stopped. |
| No dropped words | Files that are not backed up will be lost. | Files not backed up lost. |
| Noun clusters of 3 words or fewer | the inlet valve of the fuel pump | fuel pump inlet valve assembly |
| Keep modality | The step may take 10 min. | The step takes 10 min. |

## 7. Rewrite procedure for a step list

1. Find each action. Give each action its own numbered step.
2. Move each condition to the front of its step, with IF or WHEN.
3. Move each hazard statement out of the steps into a WARNING or CAUTION block immediately before the first step that it applies to. Move the avoiding action into a step after the block.
4. Replace each vague response ("check the status", "set as required") with the expected value.
5. Replace each name with the exact name that the reader sees.
6. Add "Go to step N" for each branch. Mark the end.
7. Do not add a step, a hazard, a value, or an expected result that the source does not state. Flag the gap instead.
