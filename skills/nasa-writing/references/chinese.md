# Applying the Rules to Chinese Text (中文)

NASA writing guidance covers English only. This file maps the rules to Chinese. **The mapping is this skill's adaptation, not a NASA standard.** Where a Chinese national standard covers the same point, this file names it. The skill does not reproduce Chinese standards.

## 1. Modes in Chinese

| Mode | Chinese text type | Example |
|---|---|---|
| Requirement | 需求、规格、验收条件、接口约定 | 系统应在 2 s 内返回结果。 |
| Procedure | 操作步骤、检查单、运维手册、安装说明、排障步骤 | 1. 关闭电源开关。 |
| Report | 技术报告、设计说明、分析、测试结果 | 测试在 3 次运行中失败 1 次。 |
| Correspondence | 问答回复、邮件、备忘录、状态汇报、通知 | 构建已修复。原因是缓存键变了。 |

A chat reply uses Correspondence mode. A step list inside the reply uses Procedure mode.

NAII 1450.3 Ch. 4 rules that transfer to Chinese: 先说结论（答案在解释之前）；一句一个主题；主动语态，写出动作者；用"我们/我/你"；用平实的词；能正面表达就正面表达，一句话里不要叠用多个否定；段落短，每段一个主题；缩写首次出现时给出全称。

English-only NAII rules that do **not** apply to Chinese: contractions; spelling out numbers ten or less (in Chinese, follow GB/T 15835-2011); spelling out "percent" (% is normal in Chinese text).

## 2. Requirement verbs

Chinese standards (GB/T 1.1-2020, aligned with ISO/IEC Directives Part 2) use one verb for each clause type. Map the NASA terms to them:

| NASA term | Meaning (NASA SEH App. C) | Chinese |
|---|---|---|
| shall | requirement | **应** (negative: **不应**) |
| should | goal | **宜** (negative: **不宜**) |
| will | fact or declaration of purpose | **将** (this skill's mapping, not from GB/T 1.1) |
| may (permission) | — | **可** (negative: **不必**) |
| can (capability) | — | **能** (negative: **不能**) |

- One requirement sentence holds one 应.
- Do not use 必须、一定要、需要 for a requirement. Use 应. (This is the Chinese counterpart of "must is not a NASA requirement term".)
- Do not turn 可能 (possibility, a hedge) into 应 or 将.

## 3. Structural rules that transfer directly

| Rule | Do | Don't |
|---|---|---|
| One thought per sentence | 关闭阀门。记录压力。 | 关闭阀门并记录压力，然后检查读数是否正常。 |
| Verb, not noun (SP-7084 "make verbs vigorous") | 分析日志。 | 对日志进行分析。 / 开展分析工作。 |
| Named actor (active voice) | 地面系统删除该文件。 | 文件被删除。(when the actor is known) |
| Noun after a demonstrative (SEH C.4) | 这个阀门泄漏。 / 该错误导致重启。 | 这说明有问题。 / 这会导致重启。 |
| Short modifier chains | 该阀门安装在燃料泵入口。它的压力超出限值。 | 上周更换的安装在燃料泵入口的压力超出限值的阀门的状态 (4 个"的") |
| One term for one thing | Always 节点 (not 节点 / 机器 / 主机 in turn) | Rotate synonyms for one object |
| Abbreviation defined at first use | 推力矢量控制器（TVC） | TVC used with no definition |
| Steps split at semicolons | 打开阀门。等待 5 s。 | 打开阀门；等待 5 s。 |

Chinese often drops the subject. In a procedure step, the imperative has no subject, and that is correct. In a requirement or a report sentence, write the subject.

## 4. Ambiguous and unverifiable words

These are the Chinese counterparts of the SEH App. C lists. `nasa-lint.py` checks them.

- **Ambiguous:** 等、等等、和/或、及/或、包括但不限于、酌情、视情况。
- **Unverifiable:** 适当、足够、充分、快速、迅速、友好、易用、便捷、灵活、鲁棒、稳健、尽量、尽可能、最大化、最小化、轻量、大幅、显著提升。

Replace each word with a value, a range, or an explicit list. If the source has no value, write TBD. Do not invent a number.

"等" at the end of a complete list is a style choice in Chinese. "等" at the end of an incomplete list is ambiguous. The linter flags only 等等 and the other listed words, not every 等.

## 5. Numbers and units

- Use Arabic numerals for measured values and counts (GB/T 15835-2011, 出版物上数字用法).
- Put a space between the number and the unit symbol: 5 kg, 2 s, 10 MHz (GB 3101-1993 and SI practice). Exception: %, °.
- Write the leading zero: 0.5, not .5.
- Give the tolerance when the source gives one: 9° ± 0.1°.

## 6. Safety labels in Chinese procedures

Use the common Chinese labels for the three NASA levels. Keep the English label in parentheses if the reader may see English source documents.

| English | Chinese | Use for |
|---|---|---|
| WARNING | 警告 | Hazard to people (FDF: "ensure crew safety") |
| CAUTION | 注意 | Hazard to equipment (FDF: "prevent hardware damage or malfunction"). For software: data loss, service loss |
| NOTE | 注 | Amplifying information only. No step, no hazard |

Put the label immediately before the step it applies to, as its own block. A 警告 or 注意 block names one hazard and its consequence. It may say 不要……. It contains no step.

## 7. Hedges

Keep every hedge at its original strength: 可能、或许、大概、初步判断、尚未确认. A shorter sentence that removes 可能 is a different claim. This rule wins over every length rule.
