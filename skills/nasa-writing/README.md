# NASA Writing Standard Skill

一个 Claude Code skill：按 NASA 公开的写作规范来写、改写或审查文本，支持英文和中文。结构仿照 [danyuchn/asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill)。

## 依据的 NASA 文件

NASA 机构层面的写作标准是 **NAII 1450.3《Guidelines and Standards for NASA Letters and Memorandums》第 4 章 "Writing Standards"**（2024-11-01 生效，2025-06-24 更新）。它取代了 NPR 1450.10D 第 2 章 "NASA Writing Standards"。NPR 1450.10D 已于 2024-09-27 废止，两者内容基本相同。

NAII 1450.3 只管公文和信函。需求、程序和技术报告由其他 NASA 文件规定。本 skill 把这些文件组合成四种模式：

| 模式 | 文本类型 | 主要依据 |
|---|---|---|
| Correspondence（公文） | 问答回复、邮件、备忘录、状态汇报 | NAII 1450.3 第 4 章 |
| Requirement（需求） | 需求、规格、验收条件、接口约定 | NASA Systems Engineering Handbook 第 4.2 节和附录 C；NPR 1400.1I |
| Procedure（程序） | 操作步骤、检查单、运维手册、WARNING/CAUTION/NOTE | NASA/TM-2016-219421；航天飞机 Flight Data File 标准（USA005466）；NASA CR-177549；句子规则用 ASD-STE100 |
| Report（报告） | 技术报告、设计说明、分析、测试结果 | NASA SP-7084（语法手册）；NASA/SP-2006-6114（STI 标准） |

这些 NASA 文件是美国政府作品。本 skill 只做转述和短引用，并给出章节号。USA005466 只有 archive.org 上的公开副本，不在 NASA 服务器上。ISS 程序标准 SSP 50253 没有公开副本，本 skill 没有使用它。

## 文件结构

```
~/.claude/skills/nasa-writing/
├── SKILL.md                    # 主说明（Claude 读取）
├── README.md                   # 本文件
├── references/
│   ├── correspondence.md       # NAII 1450.3 第 4 章：NASA 写作标准及其词表
│   ├── requirements.md         # SEH 4.2 + 附录 C、NPR 1400.1I：shall/will/should、检查单、词表
│   ├── procedures.md           # 步骤、条件、检查单、WARNING/CAUTION/NOTE、STE100 句子规则
│   ├── reports.md              # SP-7084 语法与句子规则、SP-2006-6114 报告结构/数字/单位
│   └── chinese.md              # 各条规则在中文中的对应写法
├── examples/
│   └── before-after.md         # 四种模式的改写示例
└── scripts/
    └── nasa-lint.py            # 只用标准库的检查脚本
```

## 用法

在对话中直接说：

```
按 NASA 标准改写这段需求
用 NASA writing standard 审查这份 runbook
把这段状态汇报改成 NASA 公文风格
```

默认只输出改写后的文本。要看规则说明，加一句"列出改了哪些规则"或"show the diff"。

## 检查脚本

```bash
python3 ~/.claude/skills/nasa-writing/scripts/nasa-lint.py --mode correspondence reply.md
python3 ~/.claude/skills/nasa-writing/scripts/nasa-lint.py --mode requirement spec.md
python3 ~/.claude/skills/nasa-writing/scripts/nasa-lint.py --mode procedure runbook.md --json
python3 ~/.claude/skills/nasa-writing/scripts/nasa-lint.py --list-rules
python3 ~/.claude/skills/nasa-writing/scripts/nasa-lint.py --selftest
```

- 不加文件名时从标准输入读取。默认模式是 `report`。
- `hard` 级别的问题数超过 `--baseline`（默认 0）时，退出码为 1。`advisory` 不影响退出码。
- `--disable rule1,rule2` 关闭指定规则。`--max-words N` 修改单句长度上限。
- 行尾加 `<!-- nasa-lint-ignore -->` 跳过该行。用 `<!-- nasa-lint-ignore-start -->` 和 `<!-- nasa-lint-ignore-end -->` 跳过一段。
- 脚本只检查文字模式。它不检查含义、技术正确性、可验证性或可追溯性。它从不标记 "may / might / could / 可能" 这类保留语气。
- skill 自己的说明文件会报出很多 advisory，因为规则表里引用了被禁止的写法作为示例。

## 限制

- 本 skill 不保证符合某个 NASA 项目的文档要求。NPR 7123.1、NPR 1400.1、项目模板和各中心的风格指南优先。
- 中文规则是本 skill 的改编，不是 NASA 标准。
- 本 skill 只修正文本的形式。内容空洞的文本改写后仍然空洞。
