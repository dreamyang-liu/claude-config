# Requirement Mode — NASA Systems Engineering Handbook

Source: *NASA Systems Engineering Handbook*, NASA/SP-2016-6105 Rev 2, Section 4.2 (Technical Requirements Definition) and Appendix C (How to Write a Good Requirement — Checklist). NASA publishes both as web pages:

- https://www.nasa.gov/reference/4-2-technical-requirements-definition/
- https://www.nasa.gov/reference/appendix-c-how-to-write-a-good-requirement/

Second source: NPR 1400.1I, *NASA Directives Procedural Requirements* (1 Nov 2024), P.2b and Sec. 3.5.1b, for the verb set and the banned caveat phrases. https://nodis3.gsfc.nasa.gov/displayDir.cfm?t=NPR&c=1400&s=1I

These are US government works. Short quotes below are exact. Everything else is a paraphrase. The handbook is guidance, not a mandatory standard. NPR 7123.1 (NASA Systems Engineering Processes and Requirements) is the binding document for NASA programs. A project's own requirements template and style rules override this file.

## 1. Requirement terms (App. C, C.1)

| Term | Meaning | Use it for |
|---|---|---|
| **shall** | a requirement | A binding, verifiable obligation. |
| **will** | "facts or declaration of purpose" | A statement that is true or intended, but not verified as a requirement. |
| **should** | "a goal" | A target that the design tries to meet. Nobody verifies it as pass/fail. |

The handbook defines only these three. **NPR 1400.1I** (*NASA Directives Procedural Requirements*, 1 Nov 2024, P.2b) defines the full set for NASA directives:

| Term | NPR 1400.1I P.2b |
|---|---|
| shall | "all mandatory actions (i.e., requirements) are denoted by statements containing the term 'shall.'" |
| may | "a discretionary privilege or permission" |
| can | "statements of possibility or capability" |
| should | "a good practice, and is recommended, but not required" |
| will | "expected outcome" |
| are/is | "descriptive material" |

**Sources disagree on two verbs. Declare one convention per document and keep it.**
- NASA-STD-3001 Vol. 2 Rev. E (App. F.2) uses **must** for a requirement "to be implemented and the associated implementation verified", and allows tailoring to "shall".
- The Shuttle Flight Data File standards (USA005466 Sec. 3.1) use "shall" for hard standards, **will** for soft standards, and "should" for guidelines. There, "will" is mandatory. In NPR 1400.1I and the SEH, "will" is not a requirement.

Default for this skill: SEH plus NPR 1400.1I. In that convention, replace "must" with "shall" if the statement is binding, unless the document already uses "must" throughout. Do not change "may" or "might" when it expresses uncertainty. That is a hedge, not a requirement term.

The *Federal Plain Language Guidelines* (2011, III.a.1.iv) say "'shall' is imprecise. It can indicate either an obligation or a prediction" and recommend "must". That guidance targets regulations and public documents. NASA directives (NPR 1400.1I) and NASA technical requirements keep "shall". Do not convert a NASA requirement from "shall" to "must".

## 2. Statement form (Sec. 4.2.1.2.3; App. C, C.2)

- Write each requirement as a complete sentence with **one "shall"**. The handbook: "complete sentences with a single 'shall' per statement".
- Product requirement form: "product ABC shall XYZ." Examples from App. C:
  - "The system shall operate at a power level of…"
  - "The software shall acquire data from the…"
  - "The structure shall withstand loads of…"
  - "The hardware shall have a mass of…"
- Personnel requirement form: "responsible party shall perform such and such." Use active voice and name the responsible party.
- Use the same name for the product and its lower-level parts every time.
- Give tolerances for each performance value: "(e.g., less than, greater than or equal to, plus or minus, 3 sigma root sum squares)".
- State **what** is needed, not **how** to provide it: "state the problem not the solution." If the statement describes an operation, move it to the Concept of Operations (ConOps).
- Worked decomposition from Sec. 4.2.1.2.2:
  - Function: "The Thrust Vector Controller (TVC) shall provide vehicle control about the pitch and yaw axes."
  - Derived performance requirement: "The TVC shall gimbal the engine a maximum of 9 degrees, ± 0.1 degree."

## 3. General goodness (App. C, C.3)

- Grammatically correct. No typos or punctuation errors.
- Follows the project template and style rules.
- Stated positively, not as "shall not", where a positive form exists.
- TBD values are minimized. For an open value, give a best estimate marked **TBR** (to be resolved), with the rationale, the action to resolve it, the responsible party, and the due date. Keep a list of all TBDs and TBRs with the requirements.
- Each requirement has a rationale and its assumptions. Confirm assumptions before the baseline.
- Each requirement sits in the correct section of the document.

## 4. Validation checklist (App. C, C.4) — condensed

| Attribute | Question to ask |
|---|---|
| Clarity | Unambiguous and concise? "only one thought per requirement statement"? "one subject and one predicate"? |
| Completeness | All gaps captured as TBD or TBR? Assumptions stated? All requirement types covered (functional, performance, interface, environment, facility, transportation, training, personnel, operability, safety, security, physical, design)? |
| Compliance | At the correct system level? Free of implementation, operations description, and personnel or task assignment? |
| Consistency | No conflict with other requirements or related systems? Terms match the glossary and stakeholder usage? |
| Traceability | Needed? Traced up and down? Uniquely numbered? |
| Correctness | Technically correct and feasible? |
| Functionality | Functions necessary and sufficient for the mission? |
| Performance | Values, margins, and tolerances realistic and defensible? |
| Interfaces | Internal and external interfaces defined, necessary, sufficient, and consistent? |
| Maintainability | Measurable and verifiable? |
| Reliability | Measurable? Covers error detection, handling, recovery, and survival after faults? |
| Verifiability | Can a test, demonstration, inspection, or analysis verify it, with clear success criteria? |
| Data usage | "Don't care" conditions truly irrelevant and stated? |

## 5. Term lists (App. C, C.4)

**Ambiguous terms (Clarity):** as appropriate, etc., and/or, but not limited to, and indefinite pronouns such as "this" and "these".

**Caveat, ambiguous, and vague terms (NPR 1400.1I Sec. 3.5.1b(2)):** "Exclude caveat phrases, ambiguous terms, and vague terms (e.g., 'as applicable,' 'as appropriate,' 'whenever possible,' 'as soon as possible,' 'in a timely manner,' 'etc.') within requirements statements."

**Unverifiable terms (Verifiability):** flexible, easy, sufficient, safe, ad hoc, adequate, accommodate, user-friendly, usable, when required, if required, appropriate, fast, portable, light-weight, small, large, maximize, minimize, robust, quickly, easily, clearly, other "-ly" words, other "-ize" words.

`scripts/nasa-lint.py --mode requirement` flags every listed term. It flags other "-ly" and "-ize" words as advisory, with a stop list for common words such as "only" and "analyze".

## 6. Rewrite procedure for one requirement

1. Find the subject. Make it the product or the responsible party.
2. Find each obligation. Give each obligation its own sentence with one "shall".
3. Replace each ambiguous or unverifiable term with a value, a range, or a list. If the source has no value, write **TBD** or a best estimate marked **TBR**. Do not invent a number.
4. Add the tolerance if the source gives one. If the source gives none, flag the gap. Do not invent a tolerance.
5. Move the "how" (design solution) and the "when/who operates" (ConOps) out of the requirement. Keep them as rationale or as notes.
6. Keep "will" and "should" if the source means fact or goal. Ask, or flag, if the intent is unclear.
7. Write the rationale on a separate line if the source gives one.

## 7. Before / after

| Before | Problem | After |
|---|---|---|
| The system shall be user-friendly and respond quickly. | Two thoughts. "user-friendly" and "quickly" are unverifiable. | The system shall display the result of an operator command within 2 s (TBR) of the command. *(Usability requirement: TBD — the source gives no measurable criterion.)* |
| The software shall log all faults and shall notify the operator. | Two "shall" in one sentence. | The software shall log each fault. The software shall notify the operator of each fault. |
| The heater must keep the battery warm, as appropriate. | "must" is not a NASA term. "warm" and "as appropriate" are unverifiable. | The heater shall maintain the battery temperature at or above TBD °C. |
| The structure shall not be heavy. | Negative and unverifiable. | The structure shall have a mass of less than or equal to TBD kg. |
| Telemetry shall be verified by the ground system. | Passive is acceptable here, because the actor is named. Check that "verified" has a pass/fail criterion. | The ground system shall reject each telemetry frame with a CRC error. *(Only if the source states the CRC criterion. Otherwise keep the original and flag "verified" as undefined.)* |
