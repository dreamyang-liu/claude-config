# Report Mode — NASA SP-7084 and NASA/SP-2006-6114

Sources:

- **SP-7084**: Mary K. McCaskill, *Grammar, Punctuation, and Capitalization: A Handbook for Technical Writers and Editors*, NASA SP-7084, NASA Langley Research Center, 1990. https://ntrs.nasa.gov/citations/19900017394
- **SP-6114**: *NASA Scientific and Technical Information Standards*, NASA/SP-2006-6114, October 2006. A companion to SP-7084. https://ntrs.nasa.gov/citations/20060049392

Both are US government works. Section and page numbers below are the printed numbers. Short quotes are exact. The rest is paraphrase.

Both documents describe themselves as recommendations. SP-6114: it "recommends general standards" and tells the writer to "Adjust them as necessary to fit your specific disciplines or 'house' style." SP-7084 presents Langley's editorial preferences and says rules "sometimes should be broken". A center or project style guide overrides this file.

SP-7084 states its own basis: "Punctuation is placed in text to make meaning clear and to make reading easier" (Sec. 3.1). It prefers "open style": punctuate to prevent misreading, and be consistent. It also warns that cutting words "may destroy the emphasis, the pace, and perhaps the meaning" (Sec. 2.4.1). Stop shortening when the sentence has one reading.

## A. Grammar and sentence rules (SP-7084)

Section numbers are SP-7084 sections. "Lint" names the `nasa-lint.py` rule that checks the point, if one exists.

### A1. Subjects and verbs

| Rule | Before | After | Sec. | Lint |
|---|---|---|---|---|
| Make the real action the verb and its actor the subject. Expletives "serve only to mark time until the true grammatical subject appears." | It is obvious that a blackbody laser is feasible. | Obviously a blackbody laser is feasible. | 2.2.1 | expletive-opener |
| "It is believed" hides who believes. Name the believer. | It is believed that the seal failed. | We believe that the seal failed. | 2.2.1 | expletive-opener |
| A verb gets weaker from active, to passive, to verbal, to a noun made from the verb. Use the strongest form that fits. | A comparison of lift coefficients for the two configurations is presented in table II. | Lift coefficients for the two configurations are compared in table II. | 2.2.2 | nominalization |
| Change "linking verb + adjective" to a verb. | The results are dependent on the mesh. | The results depend on the mesh. | 2.2.2 | — |
| Do not put a long modifier between subject and verb. | Pressures that were sensed at discrete locations such as ... are also given. | Pressures are also given for discrete locations such as ... | 2.2.3 | — |

### A2. Voice

SP-7084 Sec. 1.4.3: authorities "overwhelmingly prefer active voice". Too much passive "weakens style and obscures responsibility". But the preference "is not a condemnation of passive voice". Passive is correct when:

1. the actor is unimportant, unknown, or not to be named;
2. the receiver of the action needs the emphasis;
3. the active form is abrupt;
4. the passage needs variety;
5. a weak imperative is necessary.

Items 1 and 2 "justify much of the passive voice in technical documents." "We" is acceptable, especially for the authors' opinion (Sec. 1.3.2). "Figures 2 and 3 show ..." is acceptable (Sec. 1.4.3).

Example: "The reduction in discharge coefficient is probably caused by an increase in back pressure." → "An increase in back pressure probably causes the reduction in discharge coefficient." The hedge "probably" stays.

`passive-voice` is advisory only. Do not convert every passive. Convert it when the actor is known and the reader needs the actor.

### A3. Tense (Sec. 1.4.1)

Change tense only when the time of the action changes.

| Content | Tense |
|---|---|
| Earlier research; this study's apparatus, procedure, and what the specimens did | past |
| What a figure or table shows; explanations of results; permanent facilities | present ("Typical fracture profiles are shown in figure 21. These profiles show that fracture mode changed ...") |
| Concluding section | past, except the conclusions themselves, which are present |
| Abstract | usually present |

A subordinate verb after a past main verb is past, unless it states a general truth: "Previous studies had indicated that alumina is a suitable fiber." Lint: `usage` flags "were shown in figure".

### A4. Pronouns and demonstratives (Sec. 1.3.1, 1.3.4)

- Each pronoun needs a clear noun antecedent of the same number.
- Do not let "this", "these", or "which" refer to a whole idea. Name the antecedent: "... could take advantage of this" → "... could take advantage of voltage regulation".
- Name the specific thing. Do not add a stock word ("this result", "this effect") after every demonstrative.
- Lint: `indefinite-pronoun`.

### A5. That and which (Sec. 1.3.3)

- Nonrestrictive clause: "which", with commas.
- Restrictive clause: "that", no commas, is preferred. "which" is permitted.
- Use "which" after a preposition ("in which").
- Do not omit "that": "The model they analyzed" → "The model that they analyzed".

### A6. Agreement (Sec. 1.4.4)

- "data", "phenomena", "criteria" are plural (Langley preference; authorities differ). "equipment", "hardware" are singular. Lint: `usage`.
- A phrase between subject and verb does not change the number: "Damping ratio as well as frequency agrees".
- Repeat the auxiliary when the number changes: "its surface was polished, and nickel rods were welded".
- Avoid "and/or". Lint: `ambiguous-term`.

### A7. Modifiers (Sec. 1.5.2, 1.6, 1.9.3)

- Before you hyphenate a long modifier string, try prepositional phrases: "Separated-flow wing heating-rate values increase" → "Separated-flow heating rates on the wing increase".
- Hyphenate a number-unit modifier: "0.3-meter tunnel". Do not let it modify the quantity it measures: "15000-ft altitude" → "altitude of 15000 ft".
- Do not hyphenate an "-ly" adverb: "newly built", not "newly-built". Lint: `usage`.
- Put "only", "almost", "nearly", "also", "merely" next to the word they modify: "It is only necessary to apply equations (6) to (12)" → "It is necessary to apply only equations (6) to (12)".
- A squinting modifier can attach to either side. Move it: "..., during that test, the temperature measurements were inconsistent" → "... were inconsistent during that test".
- A split infinitive is acceptable when it prevents ambiguity.
- A dangling participle is "truly dangling and thus much more offensive": "Encouraged by these results, a new research effort was begun." → "Encouraged by these results, we began a new research effort."

### A8. Conjunctions and comparisons (Sec. 1.8, 2.5)

- Join only equal elements. Keep correlatives parallel: "provides both radiometer control functions and formats the data" → "both controls the radiometer and formats the data".
- "as", "since", "while" can mean time or cause. Make the meaning clear. "while" for "although" is accepted only if it does not suggest "at the same time".
- "whether", not "if", for alternatives: "to determine whether". "where" only for place. Lint: `usage`.
- Name both things compared, and compare like with like: "The errors in this prediction are greater than in table III." → "... greater than those in table III."
- After a comparative, "than", not "compared with". "different from", not "different than". Lint: `usage`.

### A9. Parallelism and lists (Sec. 2.3)

- Write equal ideas in the same grammatical form. Use the same voice in coordinate clauses.
- In a list: the lead-in reads into each item, all items have the same construction, and shared words go in the lead-in.
- Itemization is "the most emphatic way" to present parallel points (Sec. 2.6).

### A10. Wordiness (Sec. 2.4.1, 2.4.2)

The full SP-7084 sample list is in `scripts/nasa-lint.py` (`WORDY_SP7084`). Categories and examples:

| Category | Before | After |
|---|---|---|
| Tautology | close proximity; 20 sec in duration; in the range of 1 to 10 | proximity; 20 s; from 1 to 10 |
| Dilute verb | are found to be in agreement; give consideration to; take measurements of | agree; consider; measure |
| Hiccup | off of; inside of; in between | off; inside; between |
| Roundabout | There are three distinct flow characteristics in these photographs. | These photographs show three distinct flow characteristics. |
| Roundabout | It was shown in reference 1 that ... | Reference 1 showed that ... |
| Pointless | It is interesting to note that ...; In the case when ... | (delete); When ... |
| False elegance | a majority of; due to the fact that; with the exception of | most; because; except |
| Intensifier | very unique; quite impossible; more dominant | unique; impossible; dominant |

Shorten in this order: sentence to clause, clause to phrase, phrase to word (Sec. 2.4.2). Do not join short sentences into a long, confusing one.

**Hedges.** SP-7084 Sec. 2.4.1 lists "Lift tends to increase with angle of attack" → "Lift increases with angle of attack" as a cut of an unneeded hedge. Sec. 2.2.2 says hedges such as "may", "seem to", "appear to", "tend to" "imply indecision". That is advice **to the author, who knows the evidence**. A rewriter does not know whether the data support the stronger claim. So this skill:

- keeps every hedge in a rewrite;
- in a review, may ask the author: "Does the evidence support removing 'tends to'?";
- never removes a hedge without the author's confirmation.

### A11. Titles (Sec. 2.4.3)

A title is correct, complete, comprehensible, and concise. Delete "An Investigation of", "An Analysis of", and needless articles. Replace vague words (method, system, use). Example: "Alleviation of Trailing Vortexes by Use of Flight Spoilers" → "Alleviating Trailing Vortexes by Deflecting Flight Spoilers".

### A12. Punctuation (SP-7084 Ch. 3)

| Mark | SP-7084 stance |
|---|---|
| Semicolon (3.15) | Allowed. Required between independent clauses with no conjunction, and before a conjunctive adverb (however, thus). (In Procedure mode this skill bans it, per ASD-STE100.) |
| Serial comma (3.5) | "We prefer a comma before the conjunction in a series." |
| Colon (3.4) | Normally after a complete sentence. Never between a verb or preposition and its object, and never after "such as", "that is", "for example". Lint: `usage`. |
| Em dash (3.6) | Sparingly. Used regularly, it "becomes a sloppy substitute for conventional punctuation". |
| Slash (3.16) | A slash compound is unclear. Use a hyphen, "and", or "or", unless the term is standard (V/STOL). |
| Abbreviation periods (3.11) | No periods after unit symbols (except "in.") or acronyms. Keep the period where the abbreviation could read as a word (fig., no.). |
| e.g., i.e. | No explicit rule. SP-7084 uses them only inside parentheses and writes "for example" and "that is" in running text. |
| Large numbers | Thin space, not comma, for 5 or more digits: 88 000. (Langley style. Follow the reader's convention in other text.) |

Langley text style writes "figure 1" and "table II" in lowercase in running text (Ch. 4). Follow the project style if it differs.

## B. Report structure (SP-6114 Sec. 1.3.2)

Usual order of parts: title page, front matter (contents, lists of figures, tables, symbols), **Introduction**, **Symbols**, main text, **concluding section**, appendixes, references.

| Part | Rule |
|---|---|
| Abstract | "Informative rather than descriptive." State the objectives, the method, the results, and the conclusions. At most 200 words. (Sec. 1.3.2.3.5) Not "This report describes...". Say what the report found. |
| Introduction | Define the subject, its significance, the purpose, the objectives, and the scope. Background is optional. (Sec. 1.3.2.3.1) |
| Main text | Typical parts: procedure or apparatus, tests, results, discussion. (Sec. 1.3.2.3.3) |
| Concluding section | Self-contained, because many readers read it first. "No material that has not already been presented in another section of the report should be presented in this section." (Sec. 1.3.2.3.4) |
| Appendixes | Give each a title. Cite each in the text. Letter them A, B, C in order of first mention. (Sec. 1.3.2.4.1) |
| Disclaimers | Do not add a disclaimer that calls attention to unedited material or denies technical responsibility. (Sec. 1.1.9) |

**For agent output (this skill's transfer):** a design note or an analysis has the same shape at small scale. Put the result first (the "abstract"). Give method and evidence next. End with conclusions and open items that add no new facts. Chat replies and status updates use Correspondence mode (`correspondence.md`), which has the same "most important first" rule (NAII 4.3).

## C. Objectivity (SP-6114)

- Table titles state facts only. Put comparisons and judgments in the text. "COMPARISON OF SOLUTIONS..." is an example of an inappropriate table title. (Sec. 3.2.1)
- Do not advertise, endorse, or criticize commercial products. Use generic names. If a trade name is necessary, name the owner at first use. (Sec. 1.1.8.5)
- Use a figure only when it helps the reader understand the text. (Sec. 2.3)
- Do not present unpublished work as published. Do not present the work of another person as your own. Cite every source that you used. (Sec. 1.1.8.3)

## D. Numbers and units (SP-6114 Sec. 5)

| Rule | Do | Don't | Source |
|---|---|---|---|
| Space between number and unit symbol | 35 mm | 35mm | Sec. 5.5.3 |
| No plural, no period on unit symbols | 20 lb, 5 s | 20 lbs, 5 sec., 5 secs | Sec. 5.5.3 |
| Do not mix forms for one unit | s everywhere | s in one place, sec in another | Sec. 5.5.1 |
| Spell out a unit that has no number | "given in pascals" | "given in Pa" | Sec. 5.5.1 |
| One solidus at most | (J/mol)/K | J/mol/K | Sec. 5.5.3 |
| One prefix per compound unit, no stacked prefixes | km/s, ns | m/ms, mµs | Sec. 5.3.2 |
| Choose a prefix that gives a value from 0.1 to 1000 | 12 kPa | 12 000 Pa, 0.012 MPa | Sec. 5.3.2 |
| SI first, customary in parentheses (unless the work was done in customary units) | 0.3 m (1 ft) | 1 ft (0.3 m) for metric work | Sec. 5.2 |
| State which unit system the work used | "Measurements and calculations were made in U.S. Customary Units." | No statement | Sec. 1.1.12, 5.2 |
| Hyphenate a number-unit modifier | a 0.3-m (1-ft) model | a 0.3 m model, a 0.3-m-(1-ft) long model | Sec. 5.2.1 |
| Convert deprecated units to SI | µm, Pa·s | micron, poise, dyne, erg, gauss | Sec. 5.4.3 |
| Spelling | meter, liter | metre, litre | Sec. 5.5.2 |
| Sign closed up to the number | ±3, −5 | ± 3, − 5 | Sec. 4.2.4.2 |
| Leading zero in running text | 0.5 | .5 | NIST SP 811. SP-6114 omits leading zeros only in uniform table columns and figure scales. |

## E. Symbols, abbreviations, and equations (SP-6114 Sec. 4)

- Define each nonstandard symbol. Avoid one symbol for two quantities. Watch look-alike characters: 0/O, l/1, ×/x/χ. (Sec. 4.2)
- Use letter symbols, not abbreviations or code variable names, in equations. (Sec. 4.2.1, 4.2.3)
- "A symbol cannot begin a sentence." Begin with a word: "Then *A* is...", or give the definition: "The stretching parameter *A* is...". (Sec. 4.7)
- A math section cannot be only a list of equations. "Text must guide the reader." (Sec. 4.7)
- Do not introduce an equation with a dangling participle. Not "By substituting equations (1) and (2) in equation (3), the term becomes...". Write "..., we obtain" or "... yields". (Sec. 4.7)
- Do not write ambiguous slashed fractions: a/b/c, 1/2 x, cos x/y. (Sec. 4.4.4)
- Define each acronym at first use: "Technical Publication (TP)". SP-6114 has no explicit rule for running text, but it follows this practice in its own text. This skill applies it as a rule. Write the spelled-out form in lowercase unless it is a proper name (SP-7084 Ch. 4).

## F. Figures and tables (SP-6114 Sec. 2, 3)

- Cite every figure and table in the text. Number them in order of first mention. Each citation names a figure or table that exists. (Sec. 2.3.1, 2.6.1)
- Text and figure agree on values, trends, labels, terms, and units. (Sec. 2.3.1)
- Do not show data with color alone. Add symbols, or name the colors in the key. (Sec. 1.1.5.1.2)
- Axis and column labels: word, symbol, unit, separated by commas: "Pressure, *p*, Pa". (Sec. 2.6.5.1.3)
- Put a power-of-ten factor on the scale or in the field, not in the label. "Pressure × 10⁻⁵, mmHg" is ambiguous. (Sec. 2.6.5.1.2, 3.2.3)

## G. References (SP-6114 Sec. 1.1.8.3, 6.5)

- Cite every work you used, in the text and in the reference list.
- Mark unpublished material in the text: "unpublished", "personal communication", with the name and affiliation of the person.
- Give the access date for a URL. Do not end a sentence with a bare URL.
