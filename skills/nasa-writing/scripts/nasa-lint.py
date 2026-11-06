#!/usr/bin/env python3
"""nasa-lint: deterministic surface checks for NASA-style technical writing.

Standard library only. The linter finds patterns that NASA writing guidance
names explicitly: NAII 1450.3 Ch. 4 (the NASA writing standard), the NASA
Systems Engineering Handbook App. C term lists, NPR 1400.1I, NASA SP-7084,
NASA/SP-2006-6114, and NASA/TM-2016-219421. It cannot check meaning, technical
correctness, verifiability, traceability, or whether a rewrite kept the facts
of the original. A clean run means only that the configured patterns did not
match.

Usage:
    nasa-lint.py [--mode requirement|procedure|report|correspondence] [--json]
                 [--baseline N] [--disable rule1,rule2] [--max-words N]
                 [FILE ...]          (stdin when no FILE)
    nasa-lint.py --list-rules
    nasa-lint.py --selftest

Exit status: 1 when hard findings exceed --baseline, 0 otherwise.
Advisory findings never change the exit status.

The linter never flags hedges (may, might, could, possibly). Modality is
content, not style.

Suppress a line with <!-- nasa-lint-ignore --> at its end. Suppress a block
with <!-- nasa-lint-ignore-start --> and <!-- nasa-lint-ignore-end -->.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass

MODES = ("requirement", "procedure", "report", "correspondence")
HARD, ADV, OFF = "hard", "advisory", None

SEH_C = "NASA SEH (SP-2016-6105 Rev 2) App. C"
SP7084 = "NASA SP-7084"
STI = "NASA/SP-2006-6114"
NAII = "NAII 1450.3 Ch. 4"
NPR1400 = "NPR 1400.1I 3.5.1b"
TM2016 = "NASA/TM-2016-219421"
FDF = "USA005466 (FDF standards)"
STE = "ASD-STE100"
SKILL = "skill heuristic"

# rule id -> (requirement, procedure, report, correspondence, source, message)
RULES = {
    "ambiguous-term": (HARD, HARD, ADV, ADV, SEH_C + " C.4 Clarity; " + NPR1400,
                       "Ambiguous or caveat term. State the exact list, condition, time, or value."),
    "unverifiable-term": (HARD, ADV, OFF, OFF, SEH_C + " C.4 Verifiability",
                          "Unverifiable term. Replace with a measurable value and tolerance."),
    "ly-ize-word": (ADV, OFF, OFF, OFF, SEH_C + " C.4 Verifiability",
                    "SEH lists other '-ly' and '-ize' words as unverifiable. Check this one."),
    "indefinite-pronoun": (HARD, ADV, ADV, ADV, SEH_C + " C.4 Clarity; " + SP7084 + " 1.3.4",
                           "Demonstrative with no noun. Name the thing ('This valve', not 'This')."),
    "multiple-shall": (HARD, OFF, OFF, OFF, "NASA SEH 4.2.1.2.3; " + SEH_C + " C.4",
                       "More than one 'shall' in one sentence. Write one requirement per sentence."),
    "negative-requirement": (ADV, OFF, OFF, OFF, SEH_C + " C.3",
                             "'shall not' requirement. State it positively if a positive form exists."),
    "requirement-must": (ADV, OFF, OFF, OFF, SEH_C + " C.1; NPR 1400.1I P.2b",
                         "'must' is not a requirement term in the SEH or NPR 1400.1I. Use 'shall', unless "
                         "the document's declared convention uses 'must' (as NASA-STD-3001 does)."),
    "requirement-weak-modal": (ADV, OFF, OFF, OFF, SEH_C + " C.1; NPR 1400.1I P.2b",
                               "No 'shall'. 'will' = expected outcome or purpose, 'should' = goal or good "
                               "practice. Use 'shall' only if this is binding."),
    "tbd-tbr": (ADV, HARD, ADV, ADV, SEH_C + " C.3",
                "Open value. Give a best estimate marked TBR with rationale, owner, and closure date."),
    "nominalization": (ADV, ADV, ADV, ADV, SP7084 + " 2.2.2; " + NAII + " 4.12",
                       "Action hidden in a noun. Use the verb ('analyze', not 'perform an analysis of')."),
    "expletive-opener": (ADV, ADV, ADV, ADV, SP7084 + " 2.2.1; " + NAII + " 4.5",
                         "Expletive opener ('It is ... that', 'It appears that', 'There are') delays the "
                         "real subject. Start with the actor or the thing."),
    "wordy-phrase": (ADV, ADV, ADV, ADV, SP7084 + " 2.4.1; " + NAII + " 4.5, 4.12, 4.13; Federal PLG",
                     "Wordy phrase."),
    "usage": (ADV, ADV, ADV, ADV, SP7084 + " 1.4.1, 1.4.4, 1.5.2, 1.8.2, 2.5, 3.4", ""),
    "passive-voice": (ADV, ADV, ADV, ADV, NAII + " 4.11; " + SEH_C + " C.2; " + SP7084 + " 1.4.3",
                      "Possible passive voice. Name the actor unless the actor is unknown, unimportant, "
                      "or obvious. Do not invent an actor."),
    "long-sentence": (ADV, HARD, ADV, ADV, STE + " (procedure, 20 words); " + SKILL + " (other modes)",
                      "Long sentence."),
    "average-sentence-length": (OFF, OFF, OFF, ADV, NAII + " 4.8",
                                "Average sentence length is over 20 words. Divide long sentences."),
    "semicolon": (ADV, HARD, OFF, OFF, STE + " Rule 8.1 (procedure); " + SEH_C + " C.4 one thought (requirement)",
                  "Semicolon. Split into separate sentences (one action or one requirement each)."),
    "contraction": (ADV, ADV, ADV, HARD, NAII + " 4.4",
                    "Contraction. 'Do not use contractions in formal writing': write 'did not', not 'didn't'."),
    "multiple-negatives": (ADV, ADV, ADV, ADV, NAII + " 4.7",
                           "Several negatives in one sentence. Express it positively if that is accurate."),
    "gendered-term": (ADV, ADV, ADV, ADV, NAII + " 4.13", "Gender-specific term."),
    "small-number": (OFF, OFF, OFF, ADV, NAII + " 4.13; GPO Style Manual",
                     "Spell out numbers ten or less in a sentence ('three files'). Keep figures for "
                     "units, time, money, percentages, and references."),
    "percent-sign": (OFF, OFF, OFF, ADV, NAII + " 4.20",
                     "Spell out 'percent' in text. Use % only in tables and graphs."),
    "step-not-imperative": (OFF, ADV, OFF, OFF, TM2016 + " 2.5.1; " + FDF + " 7.1h",
                            "Step does not start with an action verb or a condition. Start with the verb."),
    "step-modal": (OFF, ADV, OFF, OFF, TM2016 + " 2.5.1",
                   "Step uses 'should/must/need to'. A step is a command: use the imperative."),
    "step-multi-action": (OFF, ADV, OFF, OFF, FDF + " 7.1a; " + TM2016 + " 2.5.6",
                          "Step may hold more than one action. Write one action per line."),
    "condition-after-action": (OFF, ADV, OFF, OFF, FDF + " 17.1b; " + TM2016 + " 2.5.8",
                               "Condition after the action. Put it first: 'IF ..., THEN ...'."),
    "vague-response": (OFF, ADV, OFF, OFF, TM2016 + " 2.5; NASA CR-177549 6.2.3",
                       "Vague check or response. State the expected value or state, not 'as required', "
                       "'checked', or 'set'."),
    "step-plus-minus": (OFF, ADV, OFF, OFF, TM2016 + " 2.5.4",
                        "Error band in a step. Give a range ('28 to 32 V'), not '30 ± 2 V'."),
    "safety-label": (OFF, ADV, ADV, ADV, FDF + " 14; " + TM2016 + " 2.5.5",
                     "Write the safety label in capitals as its own block: WARNING, CAUTION, or NOTE."),
    "sentence-starts-with-number": (OFF, ADV, ADV, ADV, "GPO Style Manual; " + STI + " 4.7 (symbols)",
                                    "Sentence starts with a numeral or symbol. Spell it out or recast."),
    "unit-spacing": (ADV, ADV, ADV, ADV, STI + " 5.5.3",
                     "No space between the number and the unit symbol. Write '35 mm', not '35mm'."),
    "unit-form": (ADV, ADV, ADV, ADV, STI + " 5.4.3, 5.5.2, 5.5.3",
                  "Nonstandard unit form. Use lb (not lbs), s (not sec), h (not hr), um (not micron), "
                  "meter/liter (not metre/litre)."),
    "leading-zero": (ADV, ADV, ADV, ADV, "NIST SP 811 (cited by " + STI + " 5.3)",
                     "Decimal with no leading zero in running text. Write '0.5', not '.5'."),
    "modifier-chain": (ADV, ADV, ADV, ADV, SKILL + " (Chinese)",
                       "Four or more 的 in one clause. Split the modifier chain into clauses."),
}
MODE_INDEX = {m: i for i, m in enumerate(MODES)}

DEFAULT_MAX_WORDS = {"requirement": 30, "procedure": 20, "report": 30, "correspondence": 30}

# --------------------------------------------------------------------------- terms

AMBIGUOUS_EN = [r"as appropriate", r"etc\.?", r"and\s*/\s*or", r"but not limited to",
                # NPR 1400.1I 3.5.1b(2) caveat phrases
                r"as applicable", r"whenever possible", r"as soon as possible", r"in a timely manner"]
AMBIGUOUS_ZH = ["等等", "和/或", "及/或", "和或", "包括但不限于", "酌情", "视情况而定", "视情况"]

UNVERIFIABLE_EN = [
    r"flexib(?:le|ly|ility)", r"eas(?:y|ier|iest|ily)", r"sufficient(?:ly)?", r"safe(?:ly)?",
    r"ad hoc", r"adequate(?:ly)?", r"accommodat(?:e|es|ed|ing)", r"user[- ]friendly", r"usable",
    r"when required", r"if required", r"appropriate(?:ly)?", r"fast(?:er|est)?", r"portable",
    r"light[- ]?weight", r"small(?:er|est)?", r"large(?:r|st)?",
    r"maximi[sz](?:e|es|ed|ing)", r"minimi[sz](?:e|es|ed|ing)", r"robust(?:ly|ness)?",
    r"quick(?:ly)?", r"clearly",
]
UNVERIFIABLE_ZH = ["适当", "足够", "充分", "快速", "迅速", "友好", "易用", "便捷", "灵活",
                   "鲁棒", "稳健", "尽量", "尽可能", "最大化", "最小化", "轻量", "大幅", "显著提升"]

# '-ly' / '-ize' words that are not vague qualifiers
LY_IZE_OK = {
    "only", "early", "apply", "supply", "reply", "daily", "weekly", "monthly", "yearly", "hourly",
    "family", "assembly", "anomaly", "rely", "comply", "fly", "july", "italy", "ally", "imply",
    "multiply", "underly", "poly", "size", "resize", "prize", "seize", "capsize", "downsize",
    "analyze", "initialize", "serialize", "deserialize", "normalize", "synchronize", "authorize",
    "recognize", "organize", "summarize", "itemize", "characterize", "localize", "finalize",
    "sanitize", "tokenize", "visualize", "categorize", "prioritize", "customize",
    "likely", "unlikely", "reply", "friendly",
}

# NASA SP-7084 sec. 2.4.1 wordiness samples (tautology, dilute verbs, hiccups, pointless,
# false elegance). Phrases are matched literally.
WORDY_SP7084 = {
    "close proximity": "proximity / near",
    "in close proximity to": "near",
    "in the range of": "from ... to",
    "are found to be in agreement": "agree",
    "is found to be in agreement": "agrees",
    "were found to be in agreement": "agreed",
    "analyses were made": "(we) analyzed",
    "make adjustments to": "adjust",
    "give consideration to": "consider",
    "take measurements of": "measure",
    "off of": "off",
    "inside of": "inside",
    "in between": "between",
    "go on with": "continue",
    "it is interesting to note that": "(delete)",
    "it might be stated that": "(delete)",
    "in the case when": "when",
    "a majority of": "most (unless 'over 50 %' is meant)",
    "due to the fact that": "because",
    "with the exception of": "except",
    "very unique": "unique",
    "quite impossible": "impossible",
    "more dominant": "dominant",
}
# NAII 1450.3 Ch. 4 (NASA writing standard) sec. 4.5, 4.12, 4.13
WORDY_NAII = {
    "a number of": "some",
    "at the present time": "now, at present",
    "due to the fact of": "because",
    "for a period of": "for",
    "for the period of": "for",
    "for the purpose of": "for, to",
    "in an effort to": "to",
    "in order to": "to",
    "in the amount of": "for",
    "in the near future": "soon",
    "on a quarterly basis": "quarterly",
    "aforementioned": "the, that, those",
    "heretofore": "until now",
    "herewith is": "here is",
    "is applicable to": "applies to",
    "make payment": "pay",
    "give recognition to": "recognize",
    "make preparations for": "prepare for",
    "make use of": "use",
    "is indicative of": "shows, indicates",
    "undertake an analysis": "analyze",
    "commence": "begin",
    "commenced": "began",
    "terminate": "end",
    "terminated": "ended",
    "utilize": "use",
    "utilizes": "uses",
    "utilized": "used",
    "utilization": "use",
    "substantial part": "large part",
    "because of the fact that": "because",
    "call your attention to the fact that": "remind you",
    "in many instances": "often",
    "in the nature of": "like",
    "the question as to whether": "whether",
    "at this point in time": "now",
    # redundant pairs (4.13): pick one word
    "any and all": "any / all",
    "authorize and direct": "direct",
    "cease and desist": "stop",
    "each and every": "each / every",
    "full and complete": "complete",
    "order and direct": "direct",
    "means and includes": "means / includes",
    "necessary and desirable": "necessary / desirable",
}
# Federal Plain Language Guidelines (2011) III.b.2.ii, entries not already above
WORDY_PLAIN = {
    "a sufficient number of": "enough",
    "is able to": "can",
    "on a monthly basis": "monthly",
    "on the ground that": "because",
    "due and payable": "due",
    "begin and commence": "start",
}
WORDY = {k: (v, "SP-7084 2.4.1") for k, v in WORDY_SP7084.items()}
WORDY.update({k: (v, "NAII 1450.3 4.5/4.12/4.13") for k, v in WORDY_NAII.items()})
WORDY.update({k: (v, "Federal PLG III.b.2.ii") for k, v in WORDY_PLAIN.items()})

GENDERED = {
    "crewman": "crewmember", "crewmen": "crewmembers", "draftsman": "drafter",
    "draftsmen": "drafters", "fireman": "firefighter", "firemen": "firefighters",
    "foreman": "supervisor", "foremen": "supervisors",
    "enlisted men and women": "enlisted personnel",
}
GENDERED_RE = re.compile(r"\b(?:" + "|".join(sorted(map(re.escape, GENDERED), key=len, reverse=True))
                         + r")\b", re.I)
CONTRACTION = re.compile(
    r"\b(?:[A-Za-z]+n['’]t|(?:i|you|we|they|he|she|it|that|there|here|what|who|where|let)['’](?:s|re|ve|ll|d|m)|"
    r"[A-Za-z]+['’](?:re|ve|ll))\b", re.I)
NEGATIVE = re.compile(r"\b(?:not|no|never|none|nothing|neither|nor|unless|without|cannot|nobody|nowhere)\b|"
                      r"n['’]t\b|\bfail(?:s|ed|ing)?\s+to\b", re.I)
NOT_ONLY = re.compile(r"\bnot\s+only\b|\bno\.\s*\d", re.I)
PERCENT_SIGN = re.compile(r"\d\s?%")
SMALL_NUMBER = re.compile(r"(?<![\w.,/:#$€£¥+\-−–])(?:10|[0-9])(?![\w%°×'’/\-–:])")
NUMBER_11_UP = re.compile(r"(?<![\w.])(?:1[1-9]|[2-9]\d|\d{3,})(?:\.\d+)?(?!\w)")
REF_WORDS = {
    "figure", "figures", "fig.", "figs.", "table", "tables", "step", "steps", "section", "sections", "sec.",
    "chapter", "ch.", "appendix", "page", "pages", "p.", "pp.", "item", "items", "line", "lines", "version",
    "v", "rev", "rev.", "no.", "number", "phase", "level", "stage", "option", "case", "run", "test", "round",
    "grade", "class", "type", "vol.", "volume", "part", "rule", "row", "column", "port", "node", "issue",
    "release", "priority", "tier", "layer", "rank", "eq.", "equation", "equations", "ref.", "reference",
    "refs.", "and", "or", "to", "of", "at", "on", "by", "is", "=", "mode", "slot", "index", "id", "pr", "gpu",
    "cpu", "core", "cores", "attempt", "patch", "build", "sprint", "week", "day", "q", "h", "ssp", "npr",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "jan.", "feb.", "mar.", "apr.", "aug.", "sept.", "oct.", "nov.", "dec.",
}
UNIT_WORDS = re.compile(
    r"\s*(?:%|percent|°|(?:" + "|".join([
        "kg", "g", "mg", "km", "m", "cm", "mm", "nm", "s", "ms", "us", "ns", "min", "h", "hz", "khz", "mhz",
        "ghz", "n", "kn", "pa", "kpa", "mpa", "w", "kw", "j", "v", "kv", "mv", "a", "ma", "k", "l", "ml",
        "b", "kb", "mb", "gb", "tb", "kib", "mib", "gib", "tib", "lb", "lbf", "ft", "in", "psi", "rpm",
        "x", "bit", "bits", "byte", "bytes", "second", "seconds", "minute", "minutes", "hour", "hours",
        "day", "days", "week", "weeks", "month", "months", "year", "years", "percent", "dollars", "cents",
        "degrees", "degree", "deg", "meters", "meter", "kilometers", "feet", "inches", "pounds", "kilograms",
        "volts", "amps", "watts", "a.m.", "p.m.", "am", "pm", "o'clock",
    ]) + r")(?![\w]))", re.I)
COND_INSIDE = re.compile(r"(?<!\beven )\b(?:if|when|unless)\b", re.I)
COND_AFTER_OK = re.compile(r"\b(?:check|verify|see|determine|confirm|ask|test|find out|whether|record|note|"
                           r"report|tell|show|decide|know|learn)\s+(?:\w+\s+)?$", re.I)
VAGUE_RESPONSE = re.compile(r"\bas (?:required|needed|necessary)\b|[—–:-]\s*(?:checked|set|ok|done)\s*\.?$",
                            re.I)
PLUS_MINUS = re.compile(r"±|\+/-|\+-(?=\s*\d)")
IT_NATURAL = re.compile(r"^it\s+is\s+(?:time\s+to|(?:your|my|our|their|his|her)\s+job\s+to)\b", re.I)

IRREGULAR = ("given|taken|made|done|found|seen|known|shown|written|built|sent|set|run|read|kept|held|"
             "left|put|begun|chosen|broken|driven|drawn|grown|thrown|flown|frozen|hidden|lost|met|"
             "paid|said|sold|told|brought|bought|caught|taught|won|worn|torn|understood|bound|spun|split")

PASSIVE_EN = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(?:\w+ed|" + IRREGULAR + r")\b", re.I)
PASSIVE_ZH = re.compile(r"被[一-鿿]")

NOMINAL_EN = [
    re.compile(r"\b(?:perform|performs|performed|performing|conduct|conducts|conducted|conducting|"
               r"carry out|carries out|carried out|carrying out|make|makes|made|making|"
               r"provide|provides|provided|providing|accomplish|accomplishes|accomplished|"
               r"effect|effects|effected|undertake|undertakes|undertook)\s+(?:an?|the)\s+(?:\w+\s+)?"
               r"\w+(?:tion|sion|ment|ance|ence|ysis|isis|ure|al)\b(?=\s+(?:of|on|for|to|in)\b)", re.I),
    re.compile(r"\b\w+(?:tion|sion|ment|ysis|ance|ence)s?\s+(?:was|were|is|are|has been|have been|"
               r"will be|shall be)\s+(?:performed|conducted|made|carried out|accomplished|done|"
               r"undertaken|effected)\b", re.I),
]
NOMINAL_ZH = re.compile(r"(?:进行|开展|做出|作出|加以|予以)(?:了|过)?[一-鿿]{2}")

DEMONSTRATIVE_EN = re.compile(
    r"^(?:this|these|that|those)\s+(?:is|are|was|were|will|can|could|may|might|should|shall|must|"
    r"has|have|had|does|do|did|means?|shows?|showed|indicates?|indicated|suggests?|suggested|"
    r"results?|resulted|causes?|caused|allows?|allowed|ensures?|ensured|requires?|required|makes?|"
    r"made|leads?|led|gives?|gave|provides?|provided|helps?|helped|seems?|seemed|happens?|happened|"
    r"occurs?|occurred|implies|implied|enables?|enabled|prevents?|prevented|reduces?|reduced|"
    r"increases?|increased|improves?|improved)\b", re.I)
DEMONSTRATIVE_ZH = re.compile(
    r"^(?:这|这些|此|该|其)(?:是|就是|说明|表明|意味着|会|将|可以|可能|能|使|让|导致|需要|要求|就|也|才|样)")

EXPLETIVE_EN = re.compile(
    r"^it\s+(?:is|was|has been|will be|should be|can be|might be|may be)\s+(?:\w+\s+){0,3}?(?:that|to)\b|"
    r"^it\s+(?:appears|seems|appeared|seemed)\s+that\b|^there\s+(?:is|are|was|were)\b", re.I)

# (pattern, message) pairs for SP-7084 usage points that a regex can see
USAGE = [
    (re.compile(r"\bdata\s+(?:is|was|has|shows)\b", re.I),
     "'data' is plural in NASA Langley style: 'data are', 'data show' (SP-7084 1.4.4)."),
    (re.compile(r"\bdifferent\s+than\b", re.I), "Use 'different from', or the verb 'differ' (SP-7084 2.5)."),
    (re.compile(r"\b(?:determine|ascertain|decide|check|see)\s+if\b", re.I),
     "Use 'whether' for alternatives (SP-7084 1.8.2)."),
    (re.compile(r"\b(?:\w+er|more\s+\w+|less\s+\w+)\s+compared\s+(?:with|to)\b", re.I),
     "After a comparative, use 'than', not 'compared with' (SP-7084 2.5)."),
    (re.compile(r"\b(?:was|were)\s+(?:shown|presented|given|plotted|compared|listed)\s+in\s+"
                r"(?:figures?|tables?|fig\.|figs\.)", re.I),
     "Use present tense for what a figure or table shows: 'are shown in figure 3' (SP-7084 1.4.1)."),
    (re.compile(r"\b(?:are|is|include|includes|included|such as|consist of|consists of)\s*:", re.I),
     "No colon between a verb or 'such as' and its object (SP-7084 3.4)."),
    (re.compile(r"\b(?!(?:only|early|family|daily|weekly|monthly|yearly|friendly|likely|holy|ugly|"
                r"curly|oily|silly|jolly|bully|belly|fly|poly|rely|apply|supply|reply|multiply)-)"
                r"[A-Za-z]{2,}ly-[A-Za-z]+\b", re.I),
     "Do not hyphenate an '-ly' adverb to the word it modifies (SP-7084 1.5.2)."),
]

SHALL = re.compile(r"\bshall\b", re.I)
SHALL_NOT = re.compile(r"\bshall\s+not\b", re.I)
MUST = re.compile(r"\bmust\b", re.I)
WEAK_MODAL = re.compile(r"\b(?:should|will)\b", re.I)
TBD = re.compile(r"\bTB[DRS]\b")

STEP_BAD_START = re.compile(
    r"^(?:the|a|an|it|this|these|there|we|i|please|now|next|also|finally|first|second|third|"
    r"lastly|here|so|basically|just)\b", re.I)
STEP_MODAL = re.compile(r"^(?:you\s+)?(?:should|must|need to|needs to|have to|has to|will need to|"
                        r"may want to|might want to|can)\b", re.I)
STEP_THEN = re.compile(r"\bthen\b", re.I)
STEP_COND = re.compile(r"^(?:if|when|whenever|unless|before|after|while|once|until)\b", re.I)
STEP_AND_VERB = re.compile(
    r"\band\s+(?:then\s+)?(?:verify|check|press|push|pull|set|open|close|remove|install|turn|select|"
    r"enter|type|wait|record|connect|disconnect|run|start|stop|restart|apply|tighten|loosen|"
    r"insert|move|rotate|click|copy|delete|save|configure|attach|detach|lock|unlock|confirm|"
    r"monitor|report|notify|repeat|go)\b", re.I)
ZH_STEP_MULTI = re.compile(r"(?:然后|接着|再|并且|随后)")

SAFETY_LABEL = re.compile(r"^(?:\*\*|__)?(warning|caution|note|danger)(?:\*\*|__)?\s*[:：](?:\*\*|__)?", re.I)

UNIT_SYMBOLS = (r"(?:kg|g|mg|km|m|cm|mm|µm|um|nm|s|ms|µs|us|ns|min|h|Hz|kHz|MHz|GHz|N|kN|Pa|kPa|"
                r"MPa|GPa|W|kW|MW|J|kJ|V|kV|mV|A|mA|K|L|mL|B|KB|kB|MB|GB|TB|KiB|MiB|GiB|TiB|"
                r"bps|kbps|Mbps|Gbps|lb|lbf|ft|in|psi|rpm)")
UNIT_NOSPACE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?" + UNIT_SYMBOLS + r"(?![\w/])")
# case-sensitive: "Sec. 5" (section) and "SP-6114 Sec" are not units
UNIT_FORM = re.compile(r"(?<=\d)\s?(?:lbs|secs?|hrs?)\b|(?<=\d)\s?(?:in|ft|lb)\.(?=\s+[a-z])|"
                       r"\b[Mm]icrons?\b|\b(?:[Mm]etre|[Ll]itre|kilometre|millimetre|centimetre)s?\b")
LEADING_ZERO = re.compile(r"(?<![\w.\d])\.\d+")
STARTS_NUMERAL = re.compile(r"^\d")
SEMICOLON = re.compile(r"[;；]")
DE_CLAUSE = re.compile(r"[^，,；;。：:！？!?、]+")

HAN = re.compile(r"[一-鿿]")
LATIN = re.compile(r"[A-Za-z]")
WORD_CHAR = re.compile(r"[^\W_]")


def _term_regex(en, zh):
    parts = []
    if en:
        parts.append(r"(?<![\w-])(?:" + "|".join(en) + r")(?![\w-])")
    if zh:
        parts.append("|".join(re.escape(z) for z in zh))
    return re.compile("|".join(parts), re.I)


AMBIGUOUS = _term_regex(AMBIGUOUS_EN, AMBIGUOUS_ZH)
UNVERIFIABLE = _term_regex(UNVERIFIABLE_EN, UNVERIFIABLE_ZH)
WORDY_RE = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(k) for k in sorted(WORDY, key=len, reverse=True))
                      + r")(?![\w-])", re.I)
LY_IZE = re.compile(r"\b[A-Za-z]{3,}(?:ly|ize|izes|ized|izing)\b")

# --------------------------------------------------------------------------- markdown

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])\s+(?:\[[ xX]\]\s+)?")
TABLE_ROW = re.compile(r"^\s*\|")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
QUOTE = re.compile(r"^\s{0,3}(?:>\s?)+")
ALERT = re.compile(r"^\[!(\w+)\]\s*$")
INLINE_CODE = re.compile(r"(`+)(.+?)\1")
URL = re.compile(r"https?://\S+|www\.\S+")
LINK_TARGET = re.compile(r"\]\([^)\s]*(?:\s+\"[^\"]*\")?\)")
HTML_COMMENT = re.compile(r"<!--.*?-->")
IGNORE_LINE = "<!-- nasa-lint-ignore -->"
IGNORE_START = "<!-- nasa-lint-ignore-start -->"
IGNORE_END = "<!-- nasa-lint-ignore-end -->"

ABBREVIATIONS = {"e.g.", "i.e.", "vs.", "cf.", "fig.", "figs.", "eq.", "eqs.", "ref.", "refs.", "no.",
                 "nos.", "approx.", "dr.", "mr.", "mrs.", "ms.", "sec.", "ch.", "vol.", "p.", "pp.",
                 "al.", "st.", "jr.", "sr.", "inc.", "co.", "ltd.", "u.s.", "max.", "min.", "avg."}
SENT_END = re.compile(r"[.!?]+[\"'”’)\]*_]*(?=\s|$)|[。！？]+[\"'”’)\]]*")


@dataclass
class Finding:
    file: str
    line: int
    col: int
    rule: str
    severity: str
    message: str
    excerpt: str


class Unit:
    """A prose block: paragraph, list item, table cell, or alert body."""

    def __init__(self, kind, ordered=False):
        self.kind = kind
        self.ordered = ordered
        self.chars = []
        self.pos = []

    def add(self, text, line_no, col0):
        if self.chars:
            self.chars.append(" ")
            self.pos.append(self.pos[-1])
        for i, ch in enumerate(text):
            self.chars.append(ch)
            self.pos.append((line_no, col0 + i + 1))

    @property
    def text(self):
        return "".join(self.chars)


def _mask(line):
    """Replace code spans, URLs, link targets, and comments so they match no rule.

    A code span becomes one placeholder word of equal length, so columns stay
    true and the span still counts as one word.
    """
    def word(m):
        n = len(m.group(0))
        return "x" + "_" * (n - 1) if n > 1 else "x"

    line = HTML_COMMENT.sub(lambda m: " " * len(m.group(0)), line)
    line = INLINE_CODE.sub(word, line)
    line = LINK_TARGET.sub(lambda m: "]" + " " * (len(m.group(0)) - 1), line)
    line = URL.sub(word, line)
    return line


def _units(text):
    lines = text.splitlines()
    i0 = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() in ("---", "..."):
                i0 = j + 1
                break
    units, cur = [], None
    fence = None
    ignoring = False

    def flush():
        nonlocal cur
        if cur is not None and cur.text.strip():
            units.append(cur)
        cur = None

    for idx in range(i0, len(lines)):
        raw = lines[idx]
        n = idx + 1
        if IGNORE_START in raw:
            flush()
            ignoring = True
            continue
        if IGNORE_END in raw:
            ignoring = False
            continue
        if ignoring or IGNORE_LINE in raw:
            flush()
            continue
        f = FENCE.match(raw)
        if fence:
            if f and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence) and not raw[f.end():].strip():
                fence = None
            continue
        if f:
            flush()
            fence = f.group(1)
            continue
        q = QUOTE.match(raw)
        offset = q.end() if q else 0
        body = _mask(raw[offset:])
        stripped = body.strip()
        if not stripped:
            flush()
            continue
        if HEADING.match(body) or ALERT.match(stripped) or stripped.startswith("<"):
            flush()
            continue
        if TABLE_ROW.match(body):
            flush()
            if TABLE_SEP.match(body):
                continue
            col = offset + body.index("|") + 1
            for cell in body.strip().strip("|").split("|"):
                start = body.find(cell, col - offset - 1)
                c = Unit("cell")
                lead = len(cell) - len(cell.lstrip())
                c.add(cell.strip(), n, offset + start + lead)
                if cell.strip():
                    units.append(c)
                col = offset + start + len(cell) + 1
            continue
        li = LIST_ITEM.match(body)
        if li:
            flush()
            cur = Unit("item", ordered=li.group(2)[0].isdigit())
            cur.add(body[li.end():].rstrip(), n, offset + li.end())
            continue
        lead = len(body) - len(body.lstrip())
        if cur is None:
            cur = Unit("para")
        cur.add(stripped, n, offset + lead)
    flush()
    return units


def _sentences(unit):
    """Yield (start, end) spans of sentences inside UNIT.text."""
    text = unit.text
    start = 0
    for m in SENT_END.finditer(text):
        end = m.end()
        if m.group(0)[0] in ".":
            token_start = text.rfind(" ", 0, m.start()) + 1
            orig = text[token_start:m.start() + 1].lstrip("(\"'*_")
            token = orig.lower()
            # "J." is an initial; "2 s." ends a sentence with a unit
            if token in ABBREVIATIONS or re.fullmatch(r"(?:[a-z]\.){2,}", token) or \
                    re.fullmatch(r"[A-Z]\.", orig):
                continue
        if text[start:end].strip():
            yield start, end
        start = end
    if text[start:].strip():
        yield start, len(text)


def _strip_lead(s):
    m = re.match(r"^[\s*_\"'“‘(\[]+", s)
    return (s[m.end():], m.end()) if m else (s, 0)


def lint(text, filename="<stdin>", mode="report", disabled=(), max_words=None):
    max_words = max_words or DEFAULT_MAX_WORDS[mode]
    findings = []
    stats = [0, 0]  # English sentences, words

    def sev(rule_id):
        if rule_id in disabled:
            return None
        return RULES[rule_id][MODE_INDEX[mode]]

    for unit in _units(text):
        utext = unit.text
        is_step = mode == "procedure" and unit.kind == "item" and unit.ordered

        def emit(rule_id, abs_start, abs_end, extra=""):
            s = sev(rule_id)
            if not s:
                return
            line, col = unit.pos[min(abs_start, len(unit.pos) - 1)]
            excerpt = utext[abs_start:abs_end].strip()
            if len(excerpt) > 80:
                excerpt = excerpt[:77] + "..."
            msg = " ".join(x for x in (RULES[rule_id][5], extra) if x)
            findings.append(Finding(filename, line, col, rule_id, s, msg, excerpt))

        # unit-level checks
        lab = SAFETY_LABEL.match(_strip_lead(utext)[0])
        if lab and lab.group(1) != lab.group(1).upper():
            emit("safety-label", 0, len(lab.group(0)))

        sents = list(_sentences(unit))
        for si, (a, b) in enumerate(sents):
            raw = utext[a:b]
            lead_ws = len(raw) - len(raw.lstrip())
            s, lead = _strip_lead(raw.lstrip())
            base = a + lead_ws + lead
            # drop a leading safety label so 'NOTE: This is...' is read from 'This'
            lm = SAFETY_LABEL.match(s)
            if lm:
                s, base = s[lm.end():].lstrip(), base + lm.end() + (len(s[lm.end():]) - len(s[lm.end():].lstrip()))
            if not s.strip():
                continue
            zh = len(HAN.findall(s)) > len(LATIN.findall(s))

            for m in AMBIGUOUS.finditer(s):
                emit("ambiguous-term", base + m.start(), base + m.end())
            for m in UNVERIFIABLE.finditer(s):
                emit("unverifiable-term", base + m.start(), base + m.end())
            if sev("ly-ize-word"):
                for m in LY_IZE.finditer(s):
                    w = m.group(0).lower()
                    if w not in LY_IZE_OK and not UNVERIFIABLE.fullmatch(m.group(0)):
                        emit("ly-ize-word", base + m.start(), base + m.end())
            m = DEMONSTRATIVE_EN.match(s) or DEMONSTRATIVE_ZH.match(s)
            if m:
                emit("indefinite-pronoun", base, base + m.end())
            m = EXPLETIVE_EN.match(s)
            if m and not IT_NATURAL.match(s):
                emit("expletive-opener", base, base + m.end())
            for m in GENDERED_RE.finditer(s):
                emit("gendered-term", base + m.start(), base + m.end(),
                     "Use '%s' (NAII 4.13)." % GENDERED[m.group(0).lower()])
            for m in WORDY_RE.finditer(s):
                repl, src = WORDY[re.sub(r"\s+", " ", m.group(0).lower())]
                emit("wordy-phrase", base + m.start(), base + m.end(), "Use '%s' (%s)." % (repl, src))
            for rx, msg in USAGE:
                for m in rx.finditer(s):
                    emit("usage", base + m.start(), base + m.end(), msg)
            for rx in NOMINAL_EN:
                for m in rx.finditer(s):
                    emit("nominalization", base + m.start(), base + m.end())
            for m in NOMINAL_ZH.finditer(s):
                emit("nominalization", base + m.start(), base + m.end())
            for m in PASSIVE_EN.finditer(s):
                emit("passive-voice", base + m.start(), base + m.end())
            for m in PASSIVE_ZH.finditer(s):
                emit("passive-voice", base + m.start(), base + m.end())
            for m in TBD.finditer(s):
                emit("tbd-tbr", base + m.start(), base + m.end())
            for m in SEMICOLON.finditer(s):
                emit("semicolon", base + m.start(), base + m.end())
            for m in UNIT_NOSPACE.finditer(s):
                emit("unit-spacing", base + m.start(), base + m.end())
            for m in UNIT_FORM.finditer(s):
                emit("unit-form", base + m.start(), base + m.end())
            if unit.kind != "cell":  # SP-2006-6114 3.2.5.1 omits leading zeros in uniform table columns
                for m in LEADING_ZERO.finditer(s):
                    emit("leading-zero", base + m.start(), base + m.end())
            if STARTS_NUMERAL.match(s) and unit.kind != "cell":
                emit("sentence-starts-with-number", base, base + min(len(s), 12))
            if zh:
                for m in DE_CLAUSE.finditer(s):
                    if m.group(0).count("的") >= 4:
                        emit("modifier-chain", base + m.start(), base + m.end())
            else:
                words = sum(1 for t in s.split() if WORD_CHAR.search(t))
                if unit.kind not in ("cell",):
                    stats[0] += 1
                    stats[1] += words
                if words > max_words and unit.kind != "cell":
                    emit("long-sentence", base, base + len(s),
                         "%d words; limit %d for %s mode." % (words, max_words, mode))
                for m in CONTRACTION.finditer(s):
                    emit("contraction", base + m.start(), base + m.end())
                negs = [m for m in NEGATIVE.finditer(s)
                        if not NOT_ONLY.match(s, m.start())]
                if len(negs) >= 2:
                    emit("multiple-negatives", base + negs[0].start(), base + negs[-1].end(),
                         "Found %d." % len(negs))
                if unit.kind != "cell":
                    for m in PERCENT_SIGN.finditer(s):
                        emit("percent-sign", base + m.start(), base + m.end())
                if sev("small-number") and unit.kind not in ("cell", "heading") and not NUMBER_11_UP.search(s):
                    for m in SMALL_NUMBER.finditer(s):
                        rest = s[m.end():]
                        if re.match(r"[.,]\d", rest) or UNIT_WORDS.match(rest):
                            continue
                        prev = s[:m.start()].split()
                        if prev and prev[-1].lower().strip("([\"'") in REF_WORDS:
                            continue
                        if re.match(r"\s*(?:to|-|–|through|and|or)\s*\d", rest):
                            continue
                        emit("small-number", base + m.start(), base + m.end())

            # requirement mode
            shalls = SHALL.findall(s)
            if len(shalls) > 1:
                emit("multiple-shall", base, base + len(s), "Found %d." % len(shalls))
            for m in SHALL_NOT.finditer(s):
                emit("negative-requirement", base + m.start(), base + m.end())
            for m in MUST.finditer(s):
                emit("requirement-must", base + m.start(), base + m.end())
            if not shalls:
                m = WEAK_MODAL.search(s)
                if m:
                    emit("requirement-weak-modal", base + m.start(), base + m.end())

            # procedure steps: first sentence of a numbered item is the step
            if is_step and si == 0:
                if STEP_MODAL.match(s):
                    emit("step-modal", base, base + STEP_MODAL.match(s).end())
                elif STEP_BAD_START.match(s):
                    emit("step-not-imperative", base, base + STEP_BAD_START.match(s).end())
            if is_step:
                if not STEP_COND.match(s):
                    for c in COND_INSIDE.finditer(s):
                        if c.start() > 0 and not COND_AFTER_OK.search(s[:c.start()]):
                            emit("condition-after-action", base + c.start(), base + c.end())
                            break
                for m in VAGUE_RESPONSE.finditer(s):
                    emit("vague-response", base + m.start(), base + m.end())
                for m in PLUS_MINUS.finditer(s):
                    emit("step-plus-minus", base + m.start(), base + m.end())
                m = STEP_AND_VERB.search(s)
                t = STEP_THEN.search(s)
                if m:
                    emit("step-multi-action", base + m.start(), base + m.end())
                elif t and not STEP_COND.match(s):
                    emit("step-multi-action", base + t.start(), base + t.end())
                elif zh:
                    z = ZH_STEP_MULTI.search(s)
                    if z:
                        emit("step-multi-action", base + z.start(), base + z.end())

    if stats[0] and sev("average-sentence-length") and stats[1] / stats[0] > 20:
        findings.append(Finding(filename, 1, 1, "average-sentence-length", sev("average-sentence-length"),
                                RULES["average-sentence-length"][5],
                                "%.1f words over %d sentences" % (stats[1] / stats[0], stats[0])))
    findings.sort(key=lambda f: (f.file, f.line, f.col, f.rule))
    return findings


def report(findings, as_json, baseline, mode):
    hard = sum(1 for f in findings if f.severity == HARD)
    adv = len(findings) - hard
    if as_json:
        print(json.dumps({"mode": mode, "hard": hard, "advisory": adv, "baseline": baseline,
                          "findings": [asdict(f) for f in findings]}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print('%s:%d:%d: %s %s: %s  "%s"' % (f.file, f.line, f.col, f.severity, f.rule,
                                                f.message, f.excerpt))
        print("mode=%s: %d hard, %d advisory (baseline %d)" % (mode, hard, adv, baseline))
    return 1 if hard > baseline else 0


def list_rules():
    print("%-28s %-11s %-11s %-11s %-14s %s" % ("rule", "requirement", "procedure", "report",
                                              "correspondence", "source"))
    for rid, (r, p, t, c, src, _) in RULES.items():
        print("%-28s %-11s %-11s %-11s %-14s %s" % (rid, r or "-", p or "-", t or "-", c or "-", src))


def selftest():
    cases = [
        # (mode, text, rules that must appear, rules that must not appear)
        ("report", "The request may have failed. The cause could be an outdated client.",
         set(), {"passive-voice", "requirement-weak-modal", "unverifiable-term"}),
        ("requirement", "The TVC shall gimbal the engine a maximum of 9 degrees, ± 0.1 degree.",
         set(), {"multiple-shall", "unverifiable-term", "ambiguous-term", "requirement-weak-modal"}),
        ("requirement", "The system shall log errors and shall notify the operator.",
         {"multiple-shall"}, set()),
        ("requirement", "R1: The FSW shall reboot within 5 s.\nR2: The FSW shall log each reboot.", set(),
         {"multiple-shall"}),
        ("report", "J. Smith wrote the report.", set(), {"sentence-starts-with-number"}),
        ("requirement", "The system shall be user-friendly and fast, as appropriate.",
         {"unverifiable-term", "ambiguous-term"}, set()),
        ("requirement", "The system shall not exceed 40 kg.", {"negative-requirement"}, set()),
        ("requirement", "The software must restart in under 5 s.", {"requirement-must"}, set()),
        ("requirement", "The rover will carry a camera.", {"requirement-weak-modal"}, set()),
        ("requirement", "This shall be verified by test.", {"indefinite-pronoun", "passive-voice"}, set()),
        ("requirement", "The pump shall deliver TBD L/min.", {"tbd-tbr"}, set()),
        ("requirement", "The controller shall synchronize clocks.", set(), {"ly-ize-word"}),
        ("requirement", "The display shall be optimized.", {"ly-ize-word"}, set()),
        ("report", "It is important to note that the valve leaked.", {"expletive-opener"}, set()),
        ("report", "We performed an analysis of the data in order to find the leak.",
         {"nominalization", "wordy-phrase"}, set()),
        ("report", "An analysis was performed on the log.", {"nominalization"}, set()),
        ("report", "The mass is 5kg and the gain is .5 at 10 Hz.", {"unit-spacing", "leading-zero"}, set()),
        ("report", "12 runs failed.", {"sentence-starts-with-number"}, set()),
        ("report", "There are three flow regions in these photographs.", {"expletive-opener"}, set()),
        ("report", "It appears that the flow is complex.", {"expletive-opener"}, set()),
        ("report", "The data shows a peak. Results were shown in figure 21.", {"usage"}, set()),
        ("report", "We want to determine if A is different than B.", {"usage"}, set()),
        ("report", "Make adjustments to the gain due to the fact that it drifts.", {"wordy-phrase"}, set()),
        ("report", "A newly-built model and an early-stage test.", {"usage"}, set()),
        ("report", "An early-stage test.", set(), {"usage"}),
        ("report", "Lift tends to increase with angle of attack.", set(), {"wordy-phrase", "usage"}),
        ("report", "It weighs 20 lbs and runs for 5 sec at 67°C.", {"unit-form"}, {"unit-spacing"}),
        ("report", "See Sec. 4.2 for the 2 h test. Per SP-6114 Sec. 5, use s.", set(), {"unit-form"}),
        ("report", "| gain |\n|---|\n| .5 |", set(), {"leading-zero"}),
        ("report", "Data for runs 1; 2 are listed.", set(), {"semicolon"}),
        ("procedure", "1. Open the valve; wait 5 s.", {"semicolon"}, set()),
        ("procedure", "1. You should open the valve.", {"step-modal"}, set()),
        ("procedure", "1. The operator opens the valve.", {"step-not-imperative"}, set()),
        ("procedure", "1. Open the valve and record the pressure.", {"step-multi-action"}, set()),
        ("procedure", "1. If the light is on, then go to step 4.", set(), {"step-multi-action"}),
        ("procedure", "1. Set the switch to ON.\n2. Wait 10 s.", set(),
         {"step-not-imperative", "step-multi-action", "step-modal"}),
        ("procedure", "Warning: High voltage.", {"safety-label"}, set()),
        ("procedure", "WARNING: High voltage.", set(), {"safety-label"}),
        ("report", "Use `etc.` in code.\n```\nTBD etc.\n```", set(), {"ambiguous-term", "tbd-tbr"}),
        ("report", "See https://example.com/a;b for details.", set(), {"semicolon"}),
        ("report", "Values e.g. 3 and 4 work. This shows a leak.", {"indefinite-pronoun"}, set()),
        ("report", "我们对日志进行分析。这说明阀门泄漏。", {"nominalization", "indefinite-pronoun"}, set()),
        ("requirement", "系统应具有友好的界面和/或快速响应。", {"unverifiable-term", "ambiguous-term"}, set()),
        ("report", "文件被删除了。", {"passive-voice"}, set()),
        ("report", "这是我的的的的问题。", {"modifier-chain"}, set()),
        ("procedure", "1. 打开阀门，然后记录压力。", {"step-multi-action"}, set()),
        ("report", "Line one etc. <!-- nasa-lint-ignore -->", set(), {"ambiguous-term"}),
        ("procedure", "1. Check the gauge and the light.", set(), {"step-multi-action"}),
        # correspondence mode (NAII 1450.3 Ch. 4)
        ("correspondence", "We didn't receive it, and it's late.", {"contraction"}, set()),
        ("correspondence", "NASA's report is late.", set(), {"contraction"}),
        ("correspondence", "A project will not be approved unless all requirements are met.",
         {"multiple-negatives"}, set()),
        ("correspondence", "Not only the pump but also the valve failed.", set(), {"multiple-negatives"}),
        ("correspondence", "We found 3 errors in 2 files.", {"small-number"}, set()),
        ("correspondence", "The job ran for 3 hours on 2 GB of data. See figure 4 and step 2.", set(),
         {"small-number"}),
        ("correspondence", "We found 3 errors in 25 files.", set(), {"small-number"}),
        ("correspondence", "Version 2.5 fixed 4.2 percent of cases.", set(), {"small-number"}),
        ("correspondence", "Usage rose 70% last week.", {"percent-sign"}, set()),
        ("correspondence", "We will commence work in order to utilize the data.", {"wordy-phrase"}, set()),
        ("correspondence", "It is time to decide.", set(), {"expletive-opener"}),
        ("correspondence", "It is my understanding that the program pays.", {"expletive-opener"}, set()),
        ("correspondence", "The foreman told each crewman.", {"gendered-term"}, set()),
        ("correspondence", "Reply as soon as possible.", {"ambiguous-term"}, set()),
        ("requirement", "The system shall report faults whenever possible.", {"ambiguous-term"}, set()),
        ("correspondence", " ".join(["word"] * 25) + ". " + " ".join(["word"] * 25) + ".",
         {"average-sentence-length"}, set()),
        ("correspondence", "Short one. Another short one.", set(), {"average-sentence-length"}),
        ("report", "We didn't see it.", {"contraction"}, set()),
        # procedure additions (TM-2016-219421, FDF)
        ("procedure", "1. Go to step 9 if the service does not start.", {"condition-after-action"}, set()),
        ("procedure", "1. IF the service does not start, THEN go to step 9.", set(), {"condition-after-action"}),
        ("procedure", "1. Check if the light is on.", set(), {"condition-after-action"}),
        ("procedure", "1. Set the heater as required.", {"vague-response"}, set()),
        ("procedure", "1. Fuel pump — checked", {"vague-response"}, set()),
        ("procedure", "1. Set the voltage to 30 ± 2 V.", {"step-plus-minus"}, set()),
        ("procedure", "1. Set the voltage to 28 to 32 V.", set(), {"step-plus-minus", "small-number"}),
    ]
    failed = 0
    for mode, text, must, must_not in cases:
        got = {f.rule for f in lint(text, mode=mode)}
        miss, extra = must - got, must_not & got
        if miss or extra:
            failed += 1
            print("FAIL [%s] %r\n  missing=%s unexpected=%s got=%s" % (mode, text, sorted(miss),
                                                                     sorted(extra), sorted(got)))
    print("selftest: %d/%d passed" % (len(cases) - failed, len(cases)))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic checks for NASA-style technical writing.")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--mode", choices=MODES, default="report")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--baseline", type=int, default=0, help="tolerate N hard findings")
    ap.add_argument("--disable", default="", help="comma-separated rule ids to silence")
    ap.add_argument("--max-words", type=int, default=None, help="override the sentence-length limit")
    ap.add_argument("--list-rules", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.list_rules:
        list_rules()
        return 0
    disabled = {d.strip() for d in args.disable.split(",") if d.strip()}
    unknown = disabled - set(RULES)
    if unknown:
        ap.error("unknown rule id(s): %s" % ", ".join(sorted(unknown)))
    findings = []
    if args.files:
        for path in args.files:
            with open(path, encoding="utf-8") as fh:
                findings += lint(fh.read(), path, args.mode, disabled, args.max_words)
    else:
        findings = lint(sys.stdin.read(), "<stdin>", args.mode, disabled, args.max_words)
    return report(findings, args.json, args.baseline, args.mode)


if __name__ == "__main__":
    sys.exit(main())
