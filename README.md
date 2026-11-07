# claude-config

统一管理 Claude Code 的全局说明和自写 skill。配置分两层：

- **通用层**：每个会话都加载。装到 `~/.claude`。
- **profile 层**：按项目类型加载。装到各项目的 `.claude/skills/`，并在项目的 `CLAUDE.md` 里引入 profile 的规则。

skill 以符号链接装入，CLAUDE.md 以 `@import` 行引入。命令行工具 `ccfg` 负责安装、切换、卸载和检查。

## 通用层

| 路径 | 内容 | 链接到 |
|---|---|---|
| `CLAUDE.md` | 全局说明：默认用中文回复（reasoning 可用英文），回复和所有写作都遵守 NASA 写作标准和 ASD-STE100，commit 不加 Claude co-author | `~/.claude/CLAUDE.md` |
| `skills/nasa-writing/` | NASA 写作标准 skill（4 种模式 + `nasa-lint.py`） | `~/.claude/skills/nasa-writing` |
| `skills/asd-ste100/` | ASD-STE100 skill，来自 [danyuchn/asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill)（MIT） | `~/.claude/skills/asd-ste100` |

## profile 层

每个 profile 是 `profiles/<名字>/` 目录，包含：

- `CLAUDE.md`：这类项目的补充规则。安装时以 `@` 引入行的形式加到项目的 `CLAUDE.md` 末尾。
- `skills/`：这类项目才需要的 skill。安装时逐个链接到项目的 `.claude/skills/`。

| profile | 适用项目 | skill |
|---|---|---|
| `research` | 论文、实验、文献笔记 | `research-figures` |
| `engineering` | 软件项目 | `architecture-decisions`、`behavior-map`、`code-comments`、`code-style`、`commit-and-review`、`doc-writing`、`testing` |
| `writing` | 文章、文档、翻译 | （暂无） |

engineering 的 7 个 skill 来自 SPROUT 仓库的 `.claude/skills/`。`research-figures` 来自 `~/.codex/skills/`，是复制不是链接，两处各自独立；本仓库的副本已翻成英文。

| skill | 内容 | 检查脚本 |
|---|---|---|
| `research-figures` | 论文 intro/teaser、方法 workflow、结果图、系统架构和 GitHub 总览图的绘制与迭代；`references/sprout.md` 是 SPROUT 的术语和样例 | `svg-check.py`：viewBox、字体、字号范围、配色、位图嵌入；`--summary` 输出每张图的汇总 |
| `architecture-decisions` | 何时以及如何记录 ADR（revert 测试、Nygard 格式、替代方案和回退成本） | `adr-lint.py`：文件名、编号、状态和日期行、章节、supersede 双向链接、索引；`--git` 检查 accepted ADR 是否被改 |
| `behavior-map` | 用真实用户行为讨论需求和架构：行为列表、步骤分配到组件、交互式 HTML 行为图（`behavior-map.html` + `render.sh`） | `render.sh`：渲染 PNG 并输出 trace 检查报告 |
| `code-comments` | 源码注释和 docstring 规则：接口注释讲抽象和契约，实现注释讲原因，NASA/STE 措辞 | `comment-lint.py`：`Args:` 块、TODO owner、禁用标签、非 ASCII、注释长度、历史叙述、注释掉的代码；支持 Python、shell、SQL |
| `code-style` | Python 代码形状规则：纯函数、frozen dataclass、小函数小文件、薄编排类、无死代码（改自 SGLang） | `style-lint.py`：文件和函数长度、包大小、非 frozen dataclass、mixin、字面量 `getattr`/`hasattr`、位置参数、大类 `__init__` |
| `commit-and-review` | 提交、开 PR 和评审的步骤：用户确认每次 commit/push/PR，单行提交信息，只暂存本次改动 | `commit-lint.py`：commit message、`--commits` 范围、`--staged` 暂存区、`--pr-body`/`--pr` 描述；可作 `commit-msg` hook |
| `doc-writing` | 文档正文规则：背景和论证用 NASA 风格，流程和状态用 STE，架构关系配 SVG 图 | `doc-lint.py`：文档长度、行内罗列、列表引导句、嵌套深度、模糊词、must/shall 混用、Mermaid、SVG 元数据；自动调用 `ste-lint.py` 和 `nasa-lint.py` |
| `testing` | 测试设计和评审规则：Google SE、NIST 组合测试、xUnit 模式、SGLang 准入规则 | `covering_array.py` 生成 t-way 覆盖数组；`test-lint.py`：测试里的控制流、`sleep`、mock、缺 assert、skip 无 reason、私有属性、host 路径 |

所有 `*-lint.py` 和 `svg-check.py` 遵守同一套约定：

- 只用标准库，Python 3.9 以上可运行。
- 参数：文件或目录、`--json`、`--baseline N`、`--disable id1,id2`、`--list-rules`、`--selftest`。
- hard 发现超过 baseline 时退出码为 1。advisory 发现不改变退出码。
- 不检查 may、might、could 这类情态词。情态是内容，不是风格。
- 每条规则对应 SKILL.md 里的一句话。脚本只检查能机械判断的部分。

一个 skill 只放一份真目录。几个 profile 共用一个 skill 时，在其他 profile 的 `skills/` 下放相对符号链接指向它，例如 `ln -s ../../engineering/skills/testing profiles/research/skills/testing`。相对链接可以提交到 git。

## ccfg：安装和管理工具

`ccfg` 是本仓库的命令行工具（Go，源码在 `cmd/ccfg/` 和 `internal/ccfg/`）。它把 skill 链接到一个作用域的 skills 目录，并在该作用域的 `CLAUDE.md` 里维护一段 `@import` 块：

```markdown
<!-- ccfg:begin -->
@~/Projects/claude-config/CLAUDE.md
@~/Projects/claude-config/profiles/engineering/CLAUDE.md
<!-- ccfg:end -->
```

块外的文字是你自己的，`ccfg` 不改动。所有状态都从文件系统推导：链接指向哪里、块里有哪些行。没有状态文件。

### 作用域

| 作用域 | 选项 | CLAUDE.md | skills 目录 |
|---|---|---|---|
| 全局 | `-g` / `--global` | `~/.claude/CLAUDE.md` | `~/.claude/skills/` |
| 项目 | `-p DIR` / `--project DIR`，默认当前目录 | `DIR/CLAUDE.md` | `DIR/.claude/skills/` |

`common` 是通用层对应的 profile（仓库根目录的 `CLAUDE.md` 和 `skills/`）。全局作用域装 `common`，项目作用域装项目类型的 profile。

### 命令

| 命令 | 作用 |
|---|---|
| `ccfg setup` | 交互式配置：仓库位置、全局 `common`、一个项目的 profile 和额外 skill、`.gitignore`、把 `ccfg` 链接到 PATH。最后显示计划，确认后才改动。`--accessible` 用纯文本提示。 |
| `ccfg status` | 每个作用域装了哪些 profile 和 skill。无 `-g`/`-p` 时同时显示全局和当前项目。 |
| `ccfg list` | 仓库提供的 profile 和 skill，带描述。`-v` 显示完整描述。 |
| `ccfg install <名字>...` | 安装 profile 或单个 skill。无参数时交互选择。`--force` 把占位的真实文件移到备份目录。 |
| `ccfg uninstall <名字>...` | 卸载。另一个已装 profile 还在用的 skill 会保留。`--all` 清掉该作用域里指向本仓库的一切。 |
| `ccfg switch <profile>` | 让该 profile 成为作用域里唯一的 profile。`common` 不受影响。无参数时交互选择。 |
| `ccfg doctor` | 找出坏链接、块外的 import 行、旧版 `install.sh` 留下的 `CLAUDE.md` 符号链接。`--fix` 修复。 |

仓库位置按这个顺序找：`--repo`、环境变量 `CLAUDE_CONFIG_REPO`、二进制文件所在的仓库、`~/Projects/claude-config`。

### 新机器

```bash
brew install go
git clone https://github.com/dreamyang-liu/claude-config ~/Projects/claude-config
~/Projects/claude-config/install.sh          # 构建 bin/ccfg，然后运行 ccfg setup
```

`setup` 会问：是否全局安装 `common`、要不要配置一个项目、项目选哪些 profile 和额外 skill、是否改 `.gitignore`、是否把 `ccfg` 链接到 PATH 上的目录。

### 每个项目

```bash
cd ~/Projects/my-service && ccfg install engineering
ccfg install research -p ~/Projects/my-paper
ccfg switch writing -p ~/Projects/my-paper
```

项目是 git 仓库而 `.gitignore` 没有排除 `.claude/skills/` 时，`ccfg` 会提示。链接里是本机的绝对路径，不要提交到项目仓库。

## 修改

直接改本仓库中的文件，然后提交。skill 是链接，CLAUDE.md 是 `@import`，修改立即生效。新开一个 Claude Code 会话即可读到新内容。

新增一个 skill 时，先决定它属于通用层还是某个 profile，再放到对应的 `skills/` 目录。新增一个 profile 时，建目录 `profiles/<名字>/`，放一个 `CLAUDE.md` 和一个 `skills/` 目录。

## 更新 asd-ste100

`skills/asd-ste100/` 是上游仓库 `master` 的完整副本，不带上游的 git 历史。本仓库不改这个目录里的文件。从上游拉取更新：

```bash
cd ~/Projects/claude-config
git remote add ste100-upstream https://github.com/danyuchn/asd-ste100-skill.git  # 只需一次
git fetch ste100-upstream
git rm -r -q skills/asd-ste100
git read-tree --prefix=skills/asd-ste100/ -u ste100-upstream/master
git commit -m "Update asd-ste100 to upstream $(git rev-parse --short ste100-upstream/master)"
```

`read-tree` 用上游的目录整体替换本地目录。如果以后本地改了这个目录里的文件，更新前先用 `git diff ste100-upstream/master HEAD:skills/asd-ste100` 记下改动，更新后重新套用。

## 测试

```bash
make test    # gofmt、go vet、go test，以及每个 lint 脚本的 --selftest
```
