# Language

- Write the reply to the user in Chinese. Use a different language only when the user asks for it.
- You can use English for your internal reasoning (thinking). This rule applies only to text that the user does not read as the reply.

# Writing Standards

Apply the two standards below to all text that you write. This includes replies to the user, documents, code comments, commit messages, PR descriptions, issues, prompts, tool descriptions, and error messages.

1. NASA writing standard: `~/.claude/skills/nasa-writing/SKILL.md`. Select the mode from the text type:
   - Reply, memo, email, or status update: Correspondence mode.
   - Step list, checklist, or runbook: Procedure mode.
   - Requirement, specification, or acceptance criteria: Requirement mode.
   - Technical report, design note, or analysis: Report mode.
2. ASD-STE100: `~/.claude/skills/asd-ste100/SKILL.md`. Select the mode from the text type:
   - Procedure, error message, tool description, prompt, or inter-agent instruction: Strict mode.
   - All other text, for example replies, READMEs, PR descriptions, and commit messages: STE-flavored mode.

For Chinese text, use the mapping in `~/.claude/skills/nasa-writing/references/chinese.md`. The STE100 structural rules apply to Chinese: short sentences, active voice, one topic for each sentence, and no semicolons. The STE100 word rules apply only to English.

Exception: do not apply these standards to creative text or marketing text.
