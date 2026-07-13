# ChinaTextbook CLI v1.1 发布门禁审计报告

- **仓库**：`raymondyan-zhijie/chinatxtbook-cli`（受管沙箱克隆，分支 HEAD，最新提交 `8afc7cb Add comprehensive README ...`）
- **审计类型**：只读、发布门禁级别的全面审计（未修改任何源代码，未提交、未创建 PR）
- **审计日期**：2026-07-13（Asia/Shanghai）
- **审计对象**：`src/chinatxtbook/` 全部源代码、`tests/`、`.github/`、`scripts/`、以及仓库内 18 份需求/设计/测试/发布文档（含全部 `.docx/.xlsx` 二进制，逐份抽取正文与表格后阅读）
- **验证手段**：全部源码通读、`python -m py_compile`、`pytest`、`ruff`、`black --check`、模拟入口点启动、依赖安装；二进制文档以 `python-docx`（段落＋表格）与 `openpyxl`（全部工作表）逐份抽取为文本后逐条比对代码/测试/CI

---

## 一、执行摘要

### 发布建议：**阻止发布（Block Release）**

本项目文档体系（PRD、SDS、状态机、Git 流程、v1.0 六轮安全审计记录）质量很高，`core/` 层的安全关键逻辑（evaluator/merger/manifest/state）也确实较忠实地从 v1.0 迁移并有较好单测覆盖。**但产品在其默认且唯一完整的运行��态（Textual TUI）下无法启动**，且实际运行的下载/合并管线绕开了经过审计的 `core/` 安全引擎，导致 v1.0 用六轮审计换来的核心安全机制在 v1.1 运行时基本失效。三条独立事实中的任意一条都足以单独构成发布阻断：

1. **TUI 完全无法启动**（Critical，已确认）：`ui/screens/selected.py` 存在 Python 语法错误（IndentationError），而 `ui/app.py` 在模块顶层 `import` 该文件，因此 `python -m chinatxtbook`（默认模式，即产品主形态）在导入阶段即崩溃。产品无法执行任何核心功能。
2. **CLI 是空壳**（Critical，已确认）：`--cli` 模式仅实现 `--status/--report`，完整下载/合并管线明确打印“正在迁移中”。因此不存在任何可用的端到端“下载+合并”路径。
3. **审计过的安全引擎在运行时被架空**（High，已确认）：真正运行的 `ui/workers.py` 自行重写了合并与完整性逻辑；经过 v1.0 六轮审计的 `core/downloader.py`、`core/merger.py`、`collect_plans`、磁盘检查等**全部是死代码**，从未被调用。v1.0 P0 修复中的“历史 parts 集合比对删卷检测”在 TUI 路径中因状态从不落盘而永久失效。

### 逐份阅读二进制文档后的结论（本次修订新增）

对全部 `.docx/.xlsx` 逐份抽取正文＋表格后核对，**新证据只强化、未推翻“阻止发布”结论**，并触发多条**发布规范自身定义的强制 No-Go**：

- **强制 No-Go（3.4《发布交付与回滚清单》§10.1）**：任一 P0 用例失败/阻塞/**未执行**即必须 No-Go，且 3.1 表 18、3.4 表 14 明示此门禁**不允许豁免**。而 3.2《详细测试用例》148 条用例状态**全部“未测试”、通过率 0**；04《功能矩阵》AC-001…AC-015（含 4 条 P0 安全用例）**全部“未测试”**；3.3《开发 WBS》执行看板显示**总体完成度 0、82 个任务全部“未开始”、64 个 P0 未完成、当前里程碑仍为 M0**，计划完成日期 2026-12-16。按项目自身发布规范，当前状态**处于 M0 起点**，却已存在标注“v1.1.0”的构建与交付 README——这是发布门禁的根本冲突。
- **声明支持却应拒绝的 Python 版本（升级为缺陷 F-19）**：`pyproject.toml requires-python=">=3.9"`、CI 矩阵含 `'3.9'`，与 2.7§7（`>=3.10`）、3.4 表 9/11（3.10–3.12）、3.2 环境矩阵（Python 3.9＝**负向/应拒绝**）直接冲突；3.4§7.3 明确“声明支持的版本失败不得仅在文档弱化后继续发布”。这不再是文档口径不一致，而是**发布物元数据声明了规范要求拒绝的运行环境**。
- **冻结交付物缺失（新增 F-16/F-17/F-18）**：2.3§13 要求交付 `schemas/app-state.schema.json`、`catalog-cache.schema.json`（`additionalProperties=false`）＋跨字段不变量校验——仓库**无任何 schema 文件、无 jsonschema 依赖、state 无 Schema 校验**；2.2§17/2.3§19/3.1 SEC 要求所有路径经受管根目录边界检查并拒绝 `..`/绝对路径/符号链接逃逸——代码**无任何路径边界或符号链接防护**；3.4§5.3/§8 要求 SBOM、SHA256SUMS、依赖漏洞扫描与锁文件入标签——CI（`release.yml`）**一项都没有**。

### 最高风险 Top 5

| # | 严重级别 | 一句话 |
|---|---|---|
| F-01 | Critical | `selected.py` 语法错误使整个 TUI 无法 import，产品默认模式启动即崩溃 |
| F-02 | Critical | CLI 模式为占位实现，无端到端下载/合并能力；README 宣称的能力不成立 |
| F-03 | High | 运行时 `workers.py` 旁路 `core/` 安全引擎；被审计代码为死代码 |
| F-04 | High | TUI 从不将 groups 写入状态文件 → 断点恢复与“历史删卷检测”安全机制失效 |
| F-05 | High | 单张（非分卷）PDF 在 UI 中可选，却总被“清单外拒绝”规则误杀，正常教材无法下载 |
| F-17 | High | 全仓库无路径边界／符号链接逃逸防护，直接违反 2.2§17/2.3§19/3.1 SEC 强制安全不变量 |
| F-19 | Medium→阻断 | `requires-python=">=3.9"` 且 CI 测 3.9，声明了规范（3.2/2.7/3.4）要求拒绝的运行环境 |

### 测试结果速览
- `pytest tests/`：**51 passed**（0.20s）。但仅覆盖 `core/evaluator|merger|manifest|state` 与 `utils/format`；`tests/integration/`、`tests/ui/` **为空**，实际运行路径（workers/git_client/catalog/ui）**零测试**。
- `ruff check`：**85 errors**（其中 1 条为 `selected.py` 语法错误，其余为 F401 未用导入 62、F841 未用变量 8、E401 7、F541 4、F811 3）。
- `black --check`：37 文件待格式化，**1 文件无法解析**（`selected.py`，语法错误）。
- `python -m py_compile`：`selected.py` 编译失败（IndentationError, line 31）。
- CI（release.yml）只跑 `pytest`，**无 lint / 无 py_compile / 无导入冒烟测试**，因此该阻断级语法错误可以“绿灯”通过 CI。

---

## 二、范围与方法

- **只读约束**：为审计代码，仅执行 `git sparse-checkout disable` 将仓库中已 track 但未 materialize 的 `src/`、`tests/` 等目录检出到工作区（不改动任何被 track 文件内容，不 commit）。未修改、未新增、未删除任何源文件。
- **通读源码**：`src/chinatxtbook/` 全部 `.py` 文件（core/utils/models/ui/cli/config）。
- **逐份抽取并阅读全部二进制文档**（本次修订补齐——不再依赖 README 索引）：用 `python-docx`（段落＋全部表格）与 `openpyxl`（全部工作表、`data_only`）将每份 `.docx/.xlsx` 抽取为文本后逐条阅读。清单与阅读结果：

  | 文档 | 抽取方式 | 阅读结果对结论的影响 |
  |---|---|---|
  | 01 PRD、02 信息架构、03 UI/UX、2.1 总体架构、2.4 状态机、2.5 Git 流程 | 已有 `.txt` 副本 | 与原报告一致，无变化 |
  | **2.2 模块设计** | python-docx | 确认 7 层架构与禁止依赖、§17 全路径校验（拒 `..`/绝对/NUL）——代码未实现路径校验（F-17） |
  | **2.3 数据模型与状态文件** | python-docx | §13 要求交付 `*.schema.json`＋跨字段不变量、§14 原子写（含 dir fsync）、§19 路径穿越防御——均缺失（F-12/F-16/F-17） |
  | **2.6 后台任务/日志/配置** | python-docx | §24 平台目录、表 21 配置键与 4 层优先级、§23.1 目录隔离、§17 脱敏——代码用 cwd 相对路径、无 ConfigLoader（F-11） |
  | **2.7 SDS 汇总与实施规范** | python-docx | §7 `requires-python=">=3.10"`、§18 DoD 要求 Ruff/mypy/安全扫描——pyproject 为 3.9、CI 无 mypy（F-19/F-13） |
  | **3.1 测试与验收规范** | python-docx | 附录 B 安全不变量表、表 18 门禁（P0/覆盖率/安全不变量/跨平台不允许豁免）——0 执行即不满足 |
  | **3.2 详细测试用例（xlsx）** | openpyxl | 148 条用例**全部“未测试”**、通过率 0；含 TC-126…140 路径穿越/符号链接/日志注入安全用例——全部未覆盖 |
  | **04 功能矩阵与验收清单（xlsx）** | openpyxl | FR-001…020 与 AC-001…015；AC 全部“未测试”，AC-008/009/010/013 为 P0 安全用例 |
  | **3.3 开发 WBS 与里程碑（xlsx）** | openpyxl | 执行看板：完成度 0、82 任务全“未开始”、64 P0 未完成、当前里程碑 M0，计划 2026-12-16 完工 |
  | **3.4 发布交付与回滚清单** | python-docx | §10.1 强制 No-Go（P0 未执行/平台不能启动/哈希版本不一致等）、§7.3 版本收窄、§5.3/§8 SBOM/SHA256/依赖扫描/锁文件——CI 全缺（F-18） |

- **动态验证**：`pip install -e ".[dev]"` 成功；模拟 `python -m chinatxtbook`、`--version`、`--cli --status` 三种入口。
- **代码逐条核对（本次新增）**：`find`/`grep` 确认仓库**无 `*.schema.json`、无 jsonschema、无路径边界/符号链接校验、无 ConfigLoader/PathPolicy 层、无运行时 Python 版本闸门**；`config.py` 工作区/输出/状态/日志均为 cwd 相对路径；`release.yml` CI 无 lint/mypy/py_compile/SBOM/SHA256SUMS/依赖扫描。

---

## 三、架构与信任边界

### 3.1 设计意图（来自文档）
- 分层：UI（Textual）→ Worker（后台管线）→ Core（git/合并/评估/状态）→ StateRepository。
- 信任边界：**Git 树（`git ls-tree HEAD`）为权威清单**；工作区文件只作“存在性/异常提示”，绝不作为可合并依据；API 大小仅用于估算展示。
- fail-closed 原则：清单读取失败→停止；清单外分卷组→拒绝；单卷组 `.pdf.1`→拒绝；历史 parts 比新清单多（疑似删卷）→保留现有 PDF 并报错。
- 完整性唯一证据：SHA256（重读一致性 + 记录哈希核对），大小/API 元数据永不作为完成证据。
- 原子写入：`tmp → flush → fsync → 重读校验 → os.replace → POSIX 父目录 fsync`。

### 3.2 实际实现的两条割裂路径（关键信任边界问题）

**被审计的 core 路径（死代码）**：`core/downloader.py::DownloadOrchestrator` 编排 clone→checkout→scan→merge，调用 `evaluator.collect_plans()`（完整决策：parts_map、restore、cleanup、单卷/清单外/删卷拒绝）与 `merger.PdfMerger`（含父目录 fsync）。
- 证据：`grep` 全仓库，`DownloadOrchestrator`、`collect_plans`、`check_disk_space`、`estimate_peak_space` **仅在自身定义处出现**，无任何调用方；`PdfMerger` 仅被死代码 `downloader.py` 和单测引用。

**实际运行的 TUI 路径（活代码）**：`ui/app.py::_on_download_confirmed` → `ui/workers.py::PipelineWorker.run()`。它**自行重写**了下载（`git show HEAD:<path>` 逐文件抽取）、合并（`_merge` / 内联单文件复制）与完整性校验，并**只把 `GroupEvaluator` 当作过滤器**（仅剔除 `action=="error"` 的组），随后用**目录/编目推断的 `book["parts"]`** 而非评估器给出的 `parts_map` 去合并（`workers.py:286-346`）。

**信任边界结论**：v1.1 运行时并未使用经过六轮审计的安全引擎；README“安全设计（继承自 v1.0 6 轮审计）”对实际运行路径**不成立**。

---

## 四、已有审计建议 / 安全承诺状态矩阵

依据 `README_v1.0.md` 中记录的 v4.0→v1.0 六轮审计 P0/P1 结论，逐条核对其在 v1.1 **实际运行路径**中的落实情况。

| 编号 | v1.0 已确立的安全机制（原始来源） | core 层是否保留 | **运行时(TUI)是否生效** | 状态 | 证据 |
|---|---|---|---|---|---|
| A1 | 清单来自 Git 树，读取失败即 fail-closed 停止 | 是 | **是** | 已落实 | `workers.py:229-244` 构建 manifest 前 `ls_tree` 返回 None 即中止 |
| A2 | 清单外分卷组一律拒绝合并 | 是（evaluator） | 部分（见 F-05 副作用） | 部分落实 | `evaluator.py:155-165`；但对单张 PDF 误杀 |
| A3 | 单卷组 `.pdf.1` 默认拒绝 | 是 | 是（作为过滤器） | 已落实 | `evaluator.py:142-150`，workers 过滤 error |
| A4 | 历史 parts 集合比对，检测上游删末卷并拒绝覆盖（v1.0 第六轮 P0 核心修复） | 是（evaluator 读 `rec.stale`/`rec.parts`） | **否** | **未落实/已架空** | workers 从不写 `state["groups"]`，评估时 `rec` 恒为 None，删卷检测永不触发 |
| A5 | diff 失败/HEAD 缺失 → 全量 stale 标记（保留 parts） | 是（`state.invalidate_by_diff`） | **否** | 未落实 | `invalidate_by_diff` 仅被死代码 `downloader.update()` 调用 |
| A6 | 校验模式下分卷齐全强制完整哈希比对；已清理组用记录 sha256 重算核对 | 是（merger + evaluator） | **否** | 未落实 | workers 无记录可比，每次全量重合并/复制 |
| A7 | API 大小永不作完整性证据 | 是 | 是 | 已落实 | 大小仅用于展示（`catalog.py`/`book_list.py`） |
| A8 | `--clean` 强制重读校验，`--skip-verify` 不可关闭 | 是（merger `must_verify`） | 不适用 | 已过时 | v1.1 无 `--clean`/`--skip-verify` CLI（CLI 为空壳） |
| A9 | 原子写入 + 重读一致性 + `os.replace` | 是（merger） | 部分 | 部分落实 | `workers.py:_merge` 有 tmp/fsync/重读/replace，但**缺 POSIX 父目录 fsync**（A10 回退） |
| A10 | POSIX 父目录 fsync（v4.2 P2） | 是（`merger.py:207-216`） | **否** | 未落实 | `workers.py:363-406` 未 fsync 父目录 |
| A11 | 单实例锁 O_EXCL + PID + stale 原子回收 | 是（`utils/lockfile.py`） | **否（TUI 未用）** | 未落实 | `InstanceLock` 仅 `cli.py --report` 使用；TUI 无锁，反而强删 `.git/index.lock` |
| A12 | URL/凭据脱敏（`safe_error`/`redact_url`） | 是 | 部分 | 部分落实 | `git_client` 用 `safe_error`；但 `workers.py:170` 直接 `r.stderr.decode(...)` 入日志，未脱敏 |
| A13 | 卷号重复检测（`.1` 与 `.01` 共存报错） | 是 | 是（经 evaluator） | 已落实 | `evaluator.py:66-71` |
| A14 | 中间缺卷连续性校验并指明缺号 | 是 | 是（经 evaluator） | 已落实 | `evaluator.py:85-94` |
| A15 | 被 `--clean` 清理的分卷需要时 `git restore` 恢复再合并 | 是（`git_client.restore_files`+downloader） | **否** | 未落实 | restore 编排仅在死代码 downloader 中 |
| A16 | “首次见到的多卷组无法识别末卷缺失”的诚实披露 | — | — | **文档回退** | `README_v1.0.md:359` 有完整披露；**v1.1 `README.md` 已知限制章节删除了该披露** |

> 结论：v1.0 用六轮审计换来的 P0 级安全机制（A4/A5/A6/A10/A11/A15）**在 v1.1 实际运行路径中大多未生效**。它们的代码被保留为“橱窗”（core/），但产品运行时走的是另一条未审计的路径。

### 4.1 冻结规范条款 vs 实现／测试／CI 逐条核对（本次修订新增，覆盖此前报告未触及的未执行项）

逐份阅读 2.2/2.3/2.6/2.7/3.1/3.2/3.3/3.4/04 后，将其中**验收标准、安全条款、待执行项、状态标记、版本要求**逐条落到代码与 CI：

| 编号 | 规范来源与条款 | 要求 | 实现/执行现状 | 状态 | 证据 |
|---|---|---|---|---|---|
| B1 | 2.3 §13 交付物 | 交付 `schemas/app-state.schema.json` + `catalog-cache.schema.json`（`additionalProperties=false`）并做 Schema＋跨字段不变量校验 | 仓库无任何 `*.schema.json`；无 `jsonschema` 依赖；`state.py` 仅读写 JSON，无校验 | **未落实** | `find *.schema.json`→空；`grep jsonschema/validate`→无（F-16） |
| B2 | 2.2 §17 / 2.3 §19 / 3.1 SEC / 2.7 §6 | 所有源/输出路径经受管根目录边界检查，拒绝 `..`、绝对路径、NUL、符号链接逃逸 | 无任何边界/符号链接校验；`workers.py` 用 `git show` 后按编目 `dest` 直接写盘 | **未落实** | `grep relative_to/is_relative/realpath/symlink`→仅显示用途（F-17） |
| B3 | 2.6 §24 / 表 21 / §23.1 | 平台目录（Win `%APPDATA%`/`%LOCALAPPDATA%`、Linux XDG）；`output_dir` 默认 `~/ChinaTextbook_Output`；workspace 不在 output 内；4 层配置优先级（默认<配置<env<CLI）经 ConfigLoader | `config.py` 为裸常量，全部 cwd 相对路径；无 ConfigLoader、无 env/CLI 覆盖 | **未落实** | `config.py:14-18`（F-11 强化） |
| B4 | 2.7 §7 / 表 11；3.4 表 9/11；3.2 环境矩阵；3.4 §7.3 | 支持 Python 3.10–3.12；3.9 为负向应拒绝；声明支持却失败的版本不得发布 | `requires-python=">=3.9"`，CI 矩阵含 `'3.9'`，ruff/black target py39 | **冲突/缺陷** | `pyproject.toml:11`、`release.yml` matrix（F-19） |
| B5 | 2.7 §18 DoD / 3.4 表 8 代码冻结门禁 | 合并/发布前须 lint + type check(mypy) + 单元测试 | CI 仅 `pytest`；无 ruff/mypy/py_compile；mypy 连 dev 依赖都未列 | **未落实** | `release.yml`；`pyproject.toml` dev 无 mypy（F-13 强化） |
| B6 | 3.4 §5.3 / §8 / 表 12 | 交付 SBOM、SHA256SUMS、依赖漏洞扫描、锁文件入标签；上传后复算哈希 | CI 直接上传 EXE/wheel，无 SHA256SUMS、无 SBOM、无依赖扫描、无锁文件 | **未落实** | `release.yml` build-exe/build-wheel（F-18） |
| B7 | 3.2 全部 148 用例 | P0/P1 用例执行并通过；安全用例 TC-126…140 覆盖 | 全部“未测试”，通过率 0；`tests/integration`、`tests/ui` 为空 | **未执行** | 3.2 xlsx；F-13 |
| B8 | 04 AC-001…015 | 安装/导航/选择/下载/后台/取消/安全(AC-008/009/010/013 为 P0) 全部验收 | 全部“未测试”；且 F-01 使 TUI 无法启动，AC 无法执行 | **未执行** | 04 xlsx |
| B9 | 3.3 WBS 退出条件 | 各里程碑退出条件（M1 StateValidator/AtomicStore/InstanceLock…）达成 | 完成度 0、82 任务“未开始”、64 P0 未完成、当前 M0 | **未开始** | 3.3 执行看板 |
| B10 | 3.4 §10.1 强制 No-Go | 任一 P0 未执行/平台不能启动/哈希版本不一致/回滚未验证→No-Go，不可豁免 | 多条同时成立（P0 全未执行、TUI 不能启动、无 SHA256/回滚演练） | **触发 No-Go** | 3.4 §10.1；3.1 表 18 |
| B11 | 3.1 附录 B 安全不变量 | 未验证并原子持久化不得 ready；崩溃/取消不得删旧可信 PDF；旧 running→interrupted；上游删卷停止自动发布 | core 层有、TUI 运行路径大多未生效（见 A4/A5/A6/A10/A15） | **部分未落实** | 见 4 节矩阵 |

---

## 五、按严重级别排序的发现

> 每条含：严重级别 / 置信度 / 类别 / 位置 / 证据与复现 / 影响 / 最小修复建议。

### F-01　TUI 因语法错误无法启动 —— Critical / 置信度：确定 / 类别：已确认缺陷
- **位置**：`src/chinatxtbook/ui/screens/selected.py:30-31`（`ui/app.py:18` 顶层导入）
- **证据/复现**：
  - `selected.py:30` `with Horizontal():` 之后紧跟的两行 `yield Button(...)` 未缩进，构成 `IndentationError: expected an indented block after 'with' statement on line 30`。
  - `python -m py_compile src/chinatxtbook/ui/screens/selected.py` 失败；`black` 报 `Cannot parse ... 31:12`。
  - `python -c "from chinatxtbook.ui.app import run_app"` → `IndentationError`。模拟默认入口 `python -m chinatxtbook` 会在 `main()` 的 `from chinatxtbook.ui.app import run_app` 处崩溃。
- **影响**：产品的默认、主要形态（TUI）**完全无法运行**，无法浏览、选择、下载、合并。这是绝对的发布阻断。
- **最小修复**：将 `selected.py:31-32` 两个 `yield Button(...)` 相对 `with Horizontal():` 增加一级缩进；补充 UI 冒烟/导入测试（见 F-13）。

### F-02　CLI 为占位实现，无端到端能力 —— Critical / 置信度：确定 / 类别：已确认缺陷 + 文档问题
- **位置**：`src/chinatxtbook/cli.py:75-81`
- **证据/复现**：`python -m chinatxtbook --cli --status` 可用；但任何非 `--status/--report` 调用打印“完整 CLI 工作流正在迁移中。当前请使用 --status, --report, --list。”。`--list` 甚至未实现分支（参数存在但无处理）。
- **影响**：TUI（F-01）崩溃后**没有任何可用的备用路径**完成下载/合并。README“运行 CLI 模式（兼容 v1.0 参数）”“6.依据 Git 树清单核对并合并”等表述与事实不符。
- **最小修复**：要么在 CLI 中接入 `DownloadOrchestrator` 提供真实管线，要么在 README/PRD 中明确标注 CLI 仅为只读状态查询，撤回“兼容 v1.0 参数”承诺。

### F-03　运行路径旁路已审计安全引擎（死代码/双实现）—— High / 置信度：确定 / 类别：设计风险 + 已确认缺陷
- **位置**：`ui/workers.py:280-406`（活）对比 `core/downloader.py`、`core/merger.py`（死）
- **证据**：全仓库 `grep` 确认 `DownloadOrchestrator`/`collect_plans`/`check_disk_space`/`estimate_peak_space` 无调用方；`PdfMerger` 仅死代码与单测引用。TUI 合并走 `workers.py::_merge` 与内联复制。
- **影响**：
  1. 单测覆盖的是**不运行**的代码，给出虚假安全信心。
  2. 两套合并实现易长期漂移（A10 父目录 fsync 已在活代码缺失）。
  3. 评估器输出的 `parts_map`/`restore` 被丢弃，实际用编目推断的 parts 合并。
- **最小修复**：让 TUI worker 复用 `DownloadOrchestrator`/`PdfMerger`/`collect_plans`，删除 `workers.py` 内的重复合并实现；或反之删除死代码并将安全逻辑集中到唯一实现，并补测试。

### F-04　TUI 从不持久化 groups → 断点恢复与删卷检测失效 —— High / 置信度：确定 / 类别：已确认缺陷
- **位置**：`ui/workers.py`（整段 `run()` 无 `state_mgr.save`，无 `state["groups"][...] = ...`）
- **证据**：`workers.py` 合并成功后仅 `_log(...)` 与更新 `app._tasks`，**未写入状态文件**；对照 `core/downloader.py:349-381` 死代码才写 groups。评估器 `evaluate()` 读取 `state["groups"]` 恒为空，`rec` 恒 None。
- **影响**：
  - PRD 验收“应用被关闭后再次运行可继续未完成任务”“已完成教材不重复处理”**不成立**（`成功指标: 状态恢复`未达标）。
  - v1.0 第六轮 P0 修复的**历史 parts 删卷检测（A4）永久失效**——每个组都被当作“首次见到”，运行时无历史可比。
  - `--status`/`--report`（读 `selected_paths`/`groups`）与 TUI 实际成果**完全脱节**，永远显示 0。
- **最小修复**：TUI 合并成功后写入 `state["groups"][key] = {status,size,sha256,parts,at}` 并 `StateManager.save`；用同一 state 驱动评估器以恢复 A4/A6。

### F-05　单张（非分卷）PDF 被安全规则误杀，正常教材无法下载 —— High / 置信度：高 / 类别：需求冲突 + 已确认缺陷
- **位置**：`ui/widgets/book_list.py:116-133`（把单 PDF 作为可选 book）对比 `ui/workers.py:256-267` + `core/evaluator.py:155-165`
- **证据/推理**：`book_list` 明确把非分卷 `*.pdf` 列为 `part_count=1, parts={1:(name,fpath)}` 的可选条目。但 `manifest` 仅由 `SPLIT_RE`（`*.pdf.N`）构建，单 PDF 的 base 不在 manifest → `expected=None` → 评估器返回 `action=="error"`（“该分卷组不在 Git 树清单中……拒绝自动合并”）→ workers 将其从 `prefiltered` 剔除。若全部选中的是单 PDF，则提示“All books skipped or blocked by safety checks”。
- **影响**：仓库中大量教材是单文件 PDF；用户选择后会被静默拒绝，报以面向“分卷组”的误导性错误信息。这是核心用户旅程的功能性失败，同时是“清单外拒绝”规则对单文件语义的误用。
- **最小修复**：区分“单文件 PDF”与“分卷组”。单文件应走直接校验复制（本就安全），不应套用“分卷组清单外拒绝”；或在评估器为 `part_count==1 且非 SPLIT` 的条目返回可复制动作。

### F-06　TUI 无单实例锁，且强制删除 `.git/index.lock` —— Medium / 置信度：高 / 类别：设计风险
- **位置**：`ui/app.py`（无 `InstanceLock`）、`ui/workers.py:113-117,152-154`
- **证据**：TUI 全程未获取 `china_textbook.lock`；worker 每次循环 `unlink` `.git/index.lock`。
- **影响**：同目录并发运行两个 TUI 会并发写 `state.json`（`os.replace` 单文件原子但**读改写序列**非串行化，后写覆盖前写）并并发操作同一 git 工作区；无条件删 `index.lock` 会破坏另一进程正在进行的 git 操作，可能损坏索引。违反 PRD 2.1“单实例锁”与 8“工作区处于无法证明安全的锁状态”。
- **最小修复**：TUI 启动即 `InstanceLock().acquire()`；删除 `index.lock` 前先确认无存活 git 进程（或改为提示用户）。

### F-07　磁盘空间从不检查 —— Medium / 置信度：高 / 类别：需求缺口
- **位置**：`core/downloader.py:441-452`（死代码），`ui/workers.py`（无调用）
- **证据**：`check_disk_space`/`estimate_peak_space` 无调用方；TUI 直接 `git show` 写盘、合并写盘，无预检。
- **影响**：违反 FR-001（启动检查可用磁盘）与 PRD/任务要求的“磁盘不足”处理。磁盘满时 `git show`/合并可能产生半截文件（虽有 tmp+size 校验兜底，但无友好预检与提示）。
- **最小修复**：合并前按 `estimate_peak_space` 校验目标卷（注意：应基于 `WORK_DIR`/`OUTPUT_DIR` 所在卷，而非 `os.getcwd()`，见 F-11）。

### F-08　blobless 克隆下 `git show` 全量读入内存 —— Medium / 置信度：中 / 类别：设计风险（性能/健壮性）
- **位置**：`ui/workers.py:162-169`
- **证据**：`subprocess.run(["git","show","HEAD:<path>"], capture_output=True)` 后 `dest.write_bytes(r.stdout)`。单个 `.pdf.N` 分卷可达数百 MB，整块进入子进程管道并驻留内存。
- **影响**：大文件时内存峰值高、无流式、无进度、无单文件超时；在低内存环境可能失败。且 `env` 未设 `GIT_NO_LAZY_FETCH`，依赖懒加载取 blob，行为与 core 层显式策略不一致。
- **最小修复**：改用 `git cat-file`/流式写出，或恢复 `sparse-checkout + checkout` 的 core 路径。

### F-09　`workers.py` 原始 git stderr 未脱敏入日志 —— Medium / 置信度：高 / 类别：已确认缺陷（隐私）
- **位置**：`ui/workers.py:170`
- **证据**：`_log(f"show ... {r.stderr.decode('utf-8','replace')[:80]}")` 未经过 `safe_error`/`redact_url`；`pipeline.log` 明文落盘。
- **影响**：若远端 URL 含凭据（自定义 origin 或代理场景），可能明文写入日志，违反 FR-018 与 PRD 10“日志和报告不出现明文凭据”。
- **最小修复**：worker 所有外部错误统一经 `safe_error()`。

### F-10　`build_expected_manifest` 空输出返回 None，与文档相反且触发误 fail-closed —— Medium / 置信度：高 / 类别：已确认缺陷
- **位置**：`core/manifest.py:58-59`（docstring 见 56-57）
- **证据**：docstring 明确“Empty output (no split files) returns empty dict, not None”，但代码对空/空白输入 `return None`。调用方 `scan()`（`downloader.py:145`）与 `workers.py:240` 把 `None` 视为“清单读取失败”→ fail-closed 中止。
- **影响**：若某选择目录**合法地没有任何分卷文件**（全是单 PDF 或空），会被误判为“清单读取失败”而整批停止；也使实现与文档、与 `ls_tree`（区分 None=错误、[]=空）语义不一致。
- **最小修复**：空输入应返回 `{}`（空清单）而非 `None`，将“git 失败”与“无分卷”区分开。

### F-11　磁盘/路径以 `os.getcwd()` 和相对路径为基准 —— Medium / 置信度：中 / 类别：设计风险
- **位置**：`config.py:14-18`（`WORK_DIR=Path("ChinaTextbook_Workspace")` 等相对路径）、`downloader.py:444`（`shutil.disk_usage(os.getcwd())`）
- **证据**：所有工作目录/状态/日志均为**相对 cwd** 的相对路径。`china-textbook` 作为 pip 安装的全局命令，用户可能从任意目录运行，导致每个 cwd 产生独立工作区/状态，且磁盘检查针对 cwd 卷而非实际写入卷。
- **影响**：状态“漂移”、断点恢复失灵、磁盘检查误判；跨平台（Windows 不同盘符）尤甚。
- **最小修复**：将工作目录锚定到显式的应用数据目录或 `--workdir` 参数；磁盘检查针对目标卷。

### F-12　`StateManager.save` 未 fsync（原子性弱于文档承诺）—— Low / 置信度：高 / 类别：设计风险
- **位置**：`core/state.py:131-138`
- **证据**：`tmp.write_text(...)` 后直接 `os.replace`，无 `flush+fsync`、无父目录 fsync；对照 NFR“任何正式 PDF 写入均 fsync”，状态文件虽非 PDF 但为断点恢复关键。
- **影响**：断电场景下状态可能丢失最近更新（仅原子替换，未保证落盘）。
- **最小修复**：写入后 `fsync` 临时文件（POSIX 下并 fsync 父目录）。

### F-13　实际运行路径零测试，CI 无 lint/编译门禁 —— High / 置信度：确定 / 类别：测试缺口
- **位置**：`tests/integration/`（空）、`tests/ui/`（空）、`.github/workflows/release.yml`
- **证据**：测试仅覆盖 core 4 模块 + format；`workers.py`/`git_client.py`/`catalog.py`/全部 `ui/` 无测试。CI 仅 `pytest tests/ -v`，无 `ruff`/`black`/`py_compile`。因此 F-01 的语法错误可以“绿灯”通过 CI 并发布。
- **影响**：NFR“核心自动化测试覆盖率不低于 80%”未达标；发布门禁形同虚设。
- **最小修复**：CI 增加 `python -m compileall src`、`ruff check`、以及最小“import app + 各 Screen.compose 可实例化”的冒烟测试；补 workers/git_client 集成测试。

### F-14　`ruff`/`black` 大量告警（代码卫生）—— Low / 置信度：确定 / 类别：文档/风格（非发布阻断）
- **位置**：全仓库
- **证据**：ruff 85 项（F401×62、F841×8、E401×7、F541×4、F811×3，含 1 条语法错误即 F-01）；black 37 文件待格式化。
- **影响**：非功能性，但 `pyproject.toml` 声明了 ruff/black 规范却未执行，说明发布前质量闸未运行。
- **最小修复**：`ruff check --fix` + `black` 全量格式化并纳入 CI。

### F-15　文档撤回诚实披露（首次见到组末卷缺失不可检测）—— Medium / 置信度：高 / 类别：文档问题
- **位置**：`README.md`“已知限制”对比 `README_v1.0.md:359`
- **证据**：v1.0 README 明确披露“首次见到的多卷组无法识别任意末卷缺失……除单卷组外无任何本地手段可检测”。v1.1 README 的“已知限制”只谈架构/UI 差距，**删去了这条安全边界披露**。
- **影响**：违反项目一贯的“如实呈现”原则与用户明确要求（文档应承认无可信上游 manifest 时无法证明首见组不缺末片）。用户可能误以为合并产物必然完整。
- **最小修复**：将 A16 披露原文恢复进 v1.1 README/帮助页。

### F-16　状态文件无 JSON Schema 与跨字段不变量校验（冻结交付物缺失）—— High / 置信度：确定 / 类别：需求缺口 + 交付缺失
- **位置**：仓库根（无 `schemas/`）、`core/state.py`（仅 JSON 读写）
- **证据**：`find . -name "*.schema.json"` 为空；`grep jsonschema|validate|additionalProperties` 无命中；`pyproject.toml` 依赖仅 `textual`，无 `jsonschema`。而 2.3《数据模型与状态文件设计》§13 明确将 `app-state.schema.json`、`catalog-cache.schema.json`（`additionalProperties=false`）＋跨字段业务不变量校验列为交付物，3.3 WBS 亦有 P0 任务 M1-03「实现状态 Schema 校验／StateValidator」。
- **影响**：损坏/被篡改/未知字段的状态文件无法被 Schema 拦截即进入安全路径（3.1 要求“损坏状态进入安全路径”）；跨字段不变量（如 `selected_files` 必须等于同快照全部源文件、`ready` 必须有 sha256）无强制校验。违反 2.3§13 与 M1-03 退出条件。
- **最小修复**：新增 `schemas/*.schema.json` 并在 `state.load` 时做 Schema＋不变量校验，失败进入安全模式（不伪造完成）。

### F-17　全仓库无路径边界／符号链接逃逸防护（强制安全不变量缺失）—— High / 置信度：确定 / 类别：安全缺口
- **位置**：`ui/workers.py:155-169`（`git show` 后按编目 `dest` 直接 `write_bytes`）、`config.py`（无 PathPolicy）
- **证据**：`grep relative_to|is_relative_to|realpath|normpath|symlink` 在 `src/` 仅见 `downloader.py:165` 的展示用 `relative_to` 与 git 错误串匹配，**无任何“规范化后校验是否位于受管根目录内”的逻辑**，也无符号链接检测。而 2.2§17、2.3§19、2.7§6、3.1 SEC 均把“所有路径经受管根目录检查，拒绝 `..`/绝对路径/NUL/符号链接逃逸”列为**强制安全不变量**；3.2 的 TC-126…140（路径穿越、绝对路径注入、符号链接逃逸、删除范围、超长文件名）为对应安全用例，全部未测试。
- **影响**：上游仓库或状态若含恶意/异常路径（`../`、绝对路径、符号链接），写盘目标可能逃出输出目录。属发布规范“不允许豁免”的 P0 安全门禁缺口。虽当前来源固定为官方仓库降低了现实概率，但防护本身缺失。
- **最小修复**：实现 `PathPolicy.resolve_within(root, candidate)`（`resolve(strict=False)` + `Path.parents` 判定、拒绝符号链接），所有源/输出路径写盘前强制通过；补 TC-126…140。

### F-18　发布产物无 SHA256SUMS／SBOM／依赖扫描／锁文件（供应链与完整性门禁缺失）—— Medium / 置信度：确定 / 类别：发布门禁缺口
- **位置**：`.github/workflows/release.yml`（build-exe / build-wheel）
- **证据**：CI 打 tag 后直接 `action-gh-release` 上传 `ChinaTextbook.exe` 与 `dist/*`，**未生成 SHA256SUMS、未生成 SBOM、未做依赖漏洞扫描、无锁文件入标签、未在发布后复算哈希**。而 3.4§5.3/§8、表 12 将上述列为发布证据强制项，3.4 §11.2/表 16 要求“公开页面重新下载并复算 SHA256”。
- **影响**：发布物不可验证、无供应链透明度，违反 3.4 多条强制门禁与 10.1 No-Go（“制品哈希/版本不一致”“依赖高危未处理”）。
- **最小修复**：CI 增加 `sha256sum` 清单、SBOM 生成（如 CycloneDX）、依赖扫描（pip-audit）、提交锁文件；发布后自动复算校验。

### F-19　`requires-python=">=3.9"` 且 CI 测 3.9——声明规范要求拒绝的运行环境 —— Medium（发布语义上为阻断）/ 置信度：确定 / 类别：已确认缺陷 + 需求冲突
- **位置**：`pyproject.toml:11`、`.github/workflows/release.yml`（matrix `'3.9'`）、`[tool.ruff]/[tool.black] target py39`、README“Python 3.9+”
- **证据**：2.7§7 与表 11 规定 `requires-python=">=3.10"`；3.4 表 9/11 要求验证 3.10–3.12；3.2 环境矩阵将 Python 3.9 标为**负向/应拒绝**、TC-003 要求“拒绝 <3.10”。3.4§7.3 明确“声明支持的 Python 版本失败，不得仅在文档弱化后继续发布，应修复兼容性或在版本元数据与文档同步收窄并重测”。
- **影响**：发布物元数据（wheel `requires-python`）与 CI 承诺了一个**冻结规范明确要求拒绝**的运行环境；若 3.9 上确有行为差异（Textual、类型语法、`match` 等），将把“应拒绝环境”当作受支持环境交付。这是发布语义上的阻断项，而非单纯文档口径问题（原报告 §六.3 曾按“文档不一致”处理，此处升级）。
- **最小修复**：将 `requires-python` 收窄为 `">=3.10"`，CI 矩阵移除 `'3.9'`，ruff/black `target-version` 改 `py310`，README 同步；并按 3.4§7.3 重跑受影响测试。

---

## 六、需求合理性评审

1. **合理且正确**：以 Git 树为权威清单、SHA256 为唯一完成证据、fail-closed、单卷/清单外/删卷拒绝、原子写入——这些是本项目最有价值的设计，逻辑自洽，`core/` 亦忠实实现。**问题不在需求本身，而在运行路径未采用它们**。

2. **需求与实现矛盾（非需求本身错误）**：
   - FR-009“文件级 sparse-checkout 下载”与 2.5“sparse-checkout set --no-cone”被实现改成 `sparse-checkout disable + git show` 逐文件抽取（`workers.py:131,162`）。实现偏离设计，但功能上仍只取选定文件。
   - 2.5 设计要求 **staging 目录 + DownloadPlan 固定 parts + 每 part 记录 blob SHA + 只按计划合并、不自行扫描目录猜测分卷**（2.5 §“Merger 只接受 DownloadPlan 固定的 parts 列表”）。实现无 staging、无 blob SHA，且 worker 恰恰“自行扫描/编目推断 parts”，直接违反该安全约束。README 已坦承“无 staging 目录”。

3. **文档内部矛盾**：
   - **Python 版本**：PRD/2.7/3.4/3.2 一致要求 3.10–3.12 且 3.9 为应拒绝环境，但 `pyproject.toml requires-python=">=3.9"`、ruff/black `target py39`、README“Python 3.9+”、CI 矩阵含 3.9。**本次已从“文档不一致”升级为缺陷 F-19**——发布物元数据声明了规范要求拒绝的环境，须收窄为 `>=3.10`。
   - **状态兼容**：CHANGELOG 称“State file backward compatibility (v4.1, v4.2, v4.3, v1.0)”，而 `__init__.py` 注释“v1.0 is NOT compatible”（v1.0 走 migratable 而非 compatible）。措辞矛盾，含义需澄清。

4. **过度设计 / 未完成**：`core/downloader.py` 全套编排、`get_remote_sizes`（GitHub Trees API）、`estimate_peak_space` 等构建完整却未接线；`models/` 分层、7 层架构 README 自承“未完全实现”。属“橱窗式”过度交付：看起来完备，运行时未用。

5. **不合理的发布门槛**：CI 把发布门禁完全押在 `pytest`，却不 lint、不编译、不冒烟启动，使“测试通过=可发布”这一门槛在本仓库失真（F-01 即为反例）。建议门槛加入编译与启动冒烟。

---

## 七、测试与命令结果（精确复现）

```text
$ python -m pytest tests/ -q
...................................................  [100%]
51 passed in 0.20s

$ python -m ruff check src/ tests/    → Found 85 errors
   F401=62  F841=8  E401=7  F541=4  F811=3  (含 selected.py 语法错误)

$ python -m black --check src/ tests/
   37 files would be reformatted; 1 file would fail to reformat
   error: cannot format .../ui/screens/selected.py: Cannot parse ... 31:12

$ python -m py_compile .../ui/screens/selected.py
   IndentationError: expected an indented block after 'with' statement (line 31)

$ python -c "from chinatxtbook.ui.app import run_app"
   IndentationError  (TUI 无法导入)

$ python -m chinatxtbook --version        → v1.1.0        (OK)
$ python -m chinatxtbook --cli --status   → 打印状态表     (OK，只读)
$ python -m chinatxtbook                  → 崩溃于 import ui.app (F-01)
```

**关键分支/失败路径覆盖评估**：evaluator 的单卷/清单外/删卷/重复卷/缺中间卷分支在 `tests/core/test_evaluator.py` 有覆盖（12 用例）；merger 原子性/大小不符/重读失败在 `test_merger.py` 覆盖（8 用例）。**但这些被覆盖的分支在运行时不执行（F-03）**。属性/模糊测试价值高的点：`SPLIT_RE` 对含点号中文文件名、`.pdf.01` vs `.pdf.1`、超大卷号——建议补 property test。**未覆盖风险**：workers 全流程、git_client 重试/脱敏、catalog 层级回退、状态迁移在真实文件上的往返。

---

## 八、正面观察

- `core/evaluator.py`、`core/merger.py`、`core/manifest.py`、`core/state.py` 忠实保留 v1.0 安全语义，注释标注了 v1.0 行号，可追溯性好。
- `utils/lockfile.py` 的 O_EXCL + PID 存活探测 + `rename` 原子回收实现正确、跨平台考虑周到（可惜 TUI 未用）。
- `utils/format.py` 的 URL/查询参数脱敏正则覆盖面广。
- 文档体系（PRD/SDS/状态机/Git 流程/六轮审计史）罕见地完整、诚实（v1.0 README 多处“诚实说明：撤回此前承诺”值得肯定）。
- `merger.py` 的“流式哈希 + 大小校验 + 重读一致性 + os.replace + 父目录 fsync”是教科书式的原子写入实现。
- 单测虽覆盖面偏窄，但对已覆盖的安全分支质量高、断言明确。

---

## 九、优先修复路线图

**P0（发布阻断，必须先修）**
1. F-01 修复 `selected.py` 缩进，恢复 TUI 可启动。
2. F-13 CI 增加 `compileall` + 导入/`compose` 冒烟 + `ruff`，防止再次“绿灯”放行语法错误。
3. F-03 + F-04：让 TUI 复用 `core` 安全引擎并将 groups 落盘，恢复 A4/A5/A6/A10/A15；或明确以 core 路径为唯一实现。
4. F-02：接通真实 CLI 管线，或撤回 README/PRD 中不成立的能力宣称。
5. F-05：修正单 PDF 被误杀，打通核心用户旅程。

**P1（安全/正确性/门禁）**
6. F-17 实现 PathPolicy 路径边界＋符号链接防护，接入所有写盘路径；补 TC-126…140。
7. F-16 新增 `schemas/*.schema.json`，state 加载做 Schema＋跨字段不变量校验。
8. F-19 `requires-python` 收窄为 `>=3.10`，CI 去 3.9，ruff/black target py310，README 同步。
9. F-06 TUI 单实例锁 + 安全处理 `index.lock`。
10. F-09 worker 日志脱敏。
11. F-10 manifest 空输入返回 `{}`。
12. F-07/F-11 磁盘预检并锚定目标卷；工作目录改用平台数据目录（2.6§24），实现 ConfigLoader 4 层优先级。
13. F-15 恢复“首见组末卷不可检测”的诚实披露。

**P2（健壮性/质量/发布证据）**
14. F-18 CI 增加 SHA256SUMS、SBOM、依赖扫描（pip-audit）、锁文件、发布后复算哈希。
15. F-13 CI 增加 `compileall`＋`ruff`＋`mypy`（先补 mypy 依赖）＋导入/compose 冒烟；补 workers/git_client 集成测试。
16. F-08 大文件流式抽取。
17. F-12 状态写入 fsync（含父目录）。
18. F-14 全量格式化并纳入 CI。
19. 文档一致性：澄清状态兼容措辞、补齐/删除未接线的“橱窗”模块。

---

## 十、审计声明

- 本次审计**未修改任何源代码**，未创建分支、提交或 PR。为读取仓库中已 track 但未 materialize 的目录，仅执行了 `git sparse-checkout disable`（不改变被 track 文件内容）。
- 所有发现均给出仓库内文件与行号定位、可复现命令与证据；已尽量排除风格偏好类误报（归入 F-14 并标注非阻断）。
- **本次修订已补齐文档逐份阅读**：仓库内全部 18 份 `.docx/.xlsx` 均以 `python-docx`（段落＋全部表格）／`openpyxl`（全部工作表）抽取为文本后逐条阅读，并与代码、测试、CI 逐条核对（见 §二清单表与 §四.1 条款对照表）。此前报告“无纯文本副本、以索引为准”的说明（原第 44、287 行）已不再适用并被取代。
- **逐份阅读后的结论未改变发布建议**：仍为**阻止发布（Block Release）**。新证据在原有 F-01…F-05 之外，新增/升级了 F-16（缺状态 Schema 校验）、F-17（缺路径边界/符号链接防护）、F-18（缺 SHA256SUMS/SBOM/依赖扫描/锁文件）、F-19（声明 3.9＝应拒绝环境），并以项目自身发布规范（3.4§10.1 强制 No-Go、3.1 表 18 不可豁免门禁）确认：148 条测试用例 0 执行、AC/UAT 全未测试、WBS 完成度 0（当前 M0）本身即构成强制 No-Go。
