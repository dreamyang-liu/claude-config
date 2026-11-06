# claude-config

统一管理 Claude Code 的全局说明和自写 skill。`~/.claude` 中的对应位置是指向本仓库的符号链接。

## 内容

| 路径 | 内容 | 链接到 |
|---|---|---|
| `CLAUDE.md` | 全局说明：默认用中文回复（reasoning 可用英文），回复和所有写作都遵守 NASA 写作标准和 ASD-STE100 | `~/.claude/CLAUDE.md` |
| `skills/nasa-writing/` | NASA 写作标准 skill（4 种模式 + `nasa-lint.py`） | `~/.claude/skills/nasa-writing` |
| `skills/asd-ste100/` | ASD-STE100 skill，来自 [danyuchn/asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill)（MIT） | `~/.claude/skills/asd-ste100` |
| `skills/architecture-decisions/` | 何时以及如何记录 ADR（revert 测试、Nygard 格式、替代方案和回退成本） | `~/.claude/skills/architecture-decisions` |
| `skills/behavior-map/` | 用真实用户行为讨论需求和架构：行为列表、步骤分配到组件、交互式 HTML 行为图（`behavior-map.html` + `render.sh`） | `~/.claude/skills/behavior-map` |
| `skills/code-comments/` | 源码注释和 docstring 规则：接口注释讲抽象和契约，实现注释讲原因，NASA/STE 措辞 | `~/.claude/skills/code-comments` |
| `skills/code-style/` | Python 代码形状规则：纯函数、frozen dataclass、小函数小文件、薄编排类、无死代码（改自 SGLang） | `~/.claude/skills/code-style` |
| `skills/commit-and-review/` | 提交、开 PR 和评审的步骤：用户确认每次 commit/push/PR，单行提交信息，只暂存本次改动 | `~/.claude/skills/commit-and-review` |
| `skills/doc-writing/` | 文档正文规则：背景和论证用 NASA 风格，流程和状态用 STE，架构关系配 SVG 图 | `~/.claude/skills/doc-writing` |
| `skills/testing/` | 测试设计和评审规则：Google SE、NIST 组合测试、xUnit 模式、SGLang 准入规则；含 `covering_array.py` | `~/.claude/skills/testing` |
| `skills/paper-figures/` | SPROUT 论文图和主表行的重生成脚本（针对 `~/sprout-runs/qwen` 下的实验目录） | `~/.claude/skills/paper-figures` |
| `skills/trajectory-dataset/` | SPROUT 固定 4+3 轨迹打包到 Hugging Face 数据集，以及分支轮次分析脚本 | `~/.claude/skills/trajectory-dataset` |
| `install.sh` | 创建上述符号链接 | — |

`skills/architecture-decisions` 到 `skills/trajectory-dataset` 这 9 个 skill 来自 SPROUT 仓库的 `.claude/skills/`。前 7 个是通用的工程规则。`paper-figures` 和 `trajectory-dataset` 只对 SPROUT 的实验目录有用。

## 在新机器上安装

```bash
git clone <本仓库地址> ~/Projects/claude-config
~/Projects/claude-config/install.sh
```

`install.sh` 可以重复运行：

- 目标已经是符号链接时，替换它。
- 目标是实际文件或目录时，先移到 `~/.claude/backups/claude-config-<时间>/`，再创建链接。备份不在 `~/.claude/skills` 下，所以不会被当成 skill 加载。
- `skills/` 下新增的目录会自动链接。

## 修改

直接改本仓库中的文件，然后提交。因为 `~/.claude` 中是链接，修改立即生效。新开一个 Claude Code 会话即可读到新内容。

## 更新 asd-ste100

`skills/asd-ste100/` 用 git 的 subtree 合并方式导入，保留了上游历史。从上游拉取更新：

```bash
cd ~/Projects/claude-config
git fetch ste100-upstream
git merge -X subtree=skills/asd-ste100/ ste100-upstream/master
```

本地对 `skills/asd-ste100/` 的修改会和上游修改一起合并。有冲突时按普通合并冲突处理。

新克隆的仓库没有 `ste100-upstream` 远程。先添加：

```bash
git remote add ste100-upstream https://github.com/danyuchn/asd-ste100-skill.git
```

## 测试

```bash
python3 skills/nasa-writing/scripts/nasa-lint.py --selftest
python3 skills/asd-ste100/scripts/ste-lint.py --selftest
```
