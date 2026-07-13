# ChinaTextbook v1.1

中国中小学教材批量下载工具 — 基于 Textual TUI 的终端应用。

## 快速开始

```powershell
# 安装
pip install -e ".[dev]"

# 运行 TUI
python -m chinatxtbook

# 运行 CLI 模式（兼容 v1.0 参数）
python -m chinatxtbook --cli --status
```

## 核心功能

| 功能 | 快捷键 | 说明 |
|------|--------|------|
| 浏览目录 | ↑↓←→ | 左栏目录树，←→折叠/展开，Enter 加载文件 |
| 选择教材 | Space | 中栏文件列表，Space 选中/取消 |
| 全选 | Ctrl+A | 当前视图全选 |
| 取消全选 | Ctrl+D | 当前视图取消 |
| 搜索 | `/` | 全局关键词 AND 过滤，Enter 定位 |
| 下载 | F5 | 确认对话框→管道执行 |
| 已选清单 | F2 | 查看/取消选择/开始下载 |
| 任务管理 | F6 | 查看进度/取消任务 |
| 日志 | F8 | 实时日志/复制/导出诊断 |
| 更新检查 | F9 | GitHub Releases + 教材仓库 diff |
| 帮助 | F1 | 快捷键参考 + 环境诊断 |
| 打开文件 | O | 系统 PDF 查看器 |
| 打开目录 | L | 文件管理器 |
| 验证 | V | 重新 SHA256 校验 |
| 退出 | Q | 有任务时双按确认 |

## 目录结构

```
D:\TextBook\
├── src/chinatxtbook/
│   ├── __init__.py          # VERSION, COMPATIBLE_STATE_VERSIONS
│   ├── __main__.py           # 入口点（TUI/CLI 路由）
│   ├── config.py             # 配置常量
│   ├── cli.py                # CLI 回退模式
│   ├── core/                 # 核心业务逻辑（安全关键）
│   │   ├── git_client.py     # Git 操作封装（clone/fetch/ls-tree/restore）
│   │   ├── merger.py         # PDF 原子合并（SHA256/fsync/os.replace）
│   │   ├── evaluator.py      # 组评估决策引擎（v1.0 6轮审计保留）
│   │   ├── manifest.py       # 分卷清单检测
│   │   ├── state.py          # 状态管理（v1.0→v1.1 迁移）
│   │   ├── downloader.py     # 下载编排器
│   │   ├── catalog.py        # 目录编目（4级层级树）
│   │   └── reporter.py       # Markdown 报告生成
│   ├── ui/                   # Textual TUI
│   │   ├── app.py            # ChinaTextbookApp（14 快捷键）
│   │   ├── workers.py        # PipelineWorker（6 阶段下载管线）
│   │   ├── messages.py       # Textual 消息类型
│   │   ├── styles.tcss       # 暗色主题 CSS
│   │   ├── screens/          # 9 个 Screen
│   │   │   ├── browse.py         # SCR-BROWSE 主浏览界面
│   │   │   ├── search_overlay.py # OVL-SEARCH 搜索覆盖层
│   │   │   ├── selected.py       # SCR-SELECTED 已选清单
│   │   │   ├── confirm_overlay.py # OVL-CONFIRM 下载确认
│   │   │   ├── tasks.py          # SCR-TASKS 任务管理
│   │   │   ├── logs.py           # SCR-LOGS 日志查看
│   │   │   ├── updates.py        # SCR-UPDATES 更新检查
│   │   │   ├── help.py           # SCR-HELP 帮助诊断
│   │   │   └── detail_overlay.py # OVL-DETAIL 教材详情
│   │   └── widgets/          # UI 组件
│   │       ├── catalog_tree.py   # 左栏目录树（延迟加载）
│   │       ├── book_list.py      # 中栏教材列表（ListView+自然排序）
│   │       ├── detail_panel.py   # 右栏文件详情
│   │       └── status_bar.py     # 底部状态栏
│   ├── models/               # 领域模型
│   │   ├── book.py           # Book, SourceFile, BookId
│   │   ├── task.py           # TaskRecord, TaskState, TaskStage
│   │   ├── events.py         # AppEvent
│   │   └── errors.py         # ErrorCode, DomainError
│   └── utils/                # 工具
│       ├── format.py         # URL脱敏/文件大小格式化
│       ├── lockfile.py       # 单实例锁（O_EXCL+PID+stale回收）
│       ├── logging.py        # 线程安全日志+轮转
│       └── platform.py       # 终端设置+中断处理+SIGINT
├── tests/                    # 51 个测试
│   ├── core/
│   │   ├── test_evaluator.py  # 决策引擎 12 测试
│   │   ├── test_merger.py     # 原子合并 8 测试
│   │   ├── test_manifest.py   # 分卷清单 9 测试
│   │   └── test_state.py      # 状态管理 8 测试
│   └── utils/
│       └── test_format.py     # 格式化 14 测试
├── docs/                     # 设计文档（14 份 .docx + .xlsx）
├── .github/workflows/        # CI/CD
├── scripts/build_exe.py      # PyInstaller 构建
└── pyproject.toml            # 项目元数据
```

## 下载管线流程

```
Preparing → Downloading → Scanning → Merging → Verifying → Done
     ↓           ↓            ↓          ↓           ↓
  仓库检查    git fetch    ls-tree    SHA256      输出到
              git show     构建清单   原子替换    Output/
              恢复文件     GroupEval
```

## 安全设计（继承自 v1.0 6 轮审计）

- **fail-closed**: Git 树读取失败→停止，清单外分卷→拒绝，单卷组→拒绝
- **SHA256 唯一证据**: 文件大小/API 元数据不作完整性判断
- **Stale 记录**: 上游变更后保留历史 parts 集以检测删卷
- **原子写入**: tmp → flush → fsync → re-read verify → os.replace
- **POSIX 父目录 fsync**: 确保 rename 元数据落盘
- **URL 凭据脱敏**: 所有外部错误入日志前脱敏
- **单实例锁**: O_EXCL + PID 追踪 + stale 原子回收

## 环境要求

- Python 3.9+
- Git 2.27+
- Windows 10/11 或 Ubuntu 22.04+
- GitHub 网络可达

## 运行测试

```powershell
pytest tests/ -v        # 51 tests
```

## 设计文档索引

| 编号 | 文件 | 内容 |
|------|------|------|
| 01 | PRD_产品需求说明书 | 20 FR + 验收标准 |
| 02 | 产品信息架构与用户流程 | 9 页面、任务状态机、导航 |
| 03 | UI_UX核心界面与交互规范 | 三栏布局、响应式、快捷键 |
| 04 | 功能矩阵与验收清单 | 功能矩阵 + 16 AC |
| 2.1 | 系统总体架构设计 | 四层架构、模块职责 |
| 2.2 | 模块设计说明 | 7 层架构、依赖规则 |
| 2.3 | 数据模型与状态文件设计 | Book/SourceFile/Task/state schema |
| 2.4 | 状态机与异常恢复设计 | 任务状态机、取消协议、崩溃恢复 |
| 2.5 | Git下载与更新流程设计 | 管线阶段、sparse-checkout |
| 2.6 | 后台任务日志与配置设计 | Worker、日志、配置系统 |
| 2.7 | SDS汇总与开发实施规范 | 完整实施规范 |
| 3.1 | 测试与验收规范 | 测试策略 |
| 3.2 | 详细测试用例与验收清单 | 测试用例 |
| 3.3 | 开发WBS与里程碑计划 | 里程碑 M0-M6 |
| 3.4 | 发布交付与回滚清单 | 发布流程 |

## 已知限制

1. **blobless clone**: 首次下载需网络取回 blob（`git show HEAD:path`）
2. **无响应式断点**: Textual CSS 不支持 @media，始终三栏布局
3. **7 层架构未完全实现**: models/ ✅，application/services/workers/ 待建
4. **无完整任务状态机**: 使用简化版（pending/running/completed）
5. **无 staging 目录**: 文件直接从 workspace 复制到 output
6. **首次见到的多卷组无法识别末卷缺失**（继承自 v1.0）：上游仓库不提供文件基准哈希，所有校验仅覆盖本地合并与写入正确性。若某组末卷在本工具首次见到它之前就已被上游删除且剩余不止 1 卷，本地无任何手段检测。能拦截的是中间缺卷（连续性校验）、有历史记录的删卷（历史分卷集合比对）、单卷组（默认拒绝）
6. **单 PDF 合并**: 使用流式 SHA256 而非 GroupEvaluator 完整路径

## 后续可改进

- 完整 7 层架构（ApplicationController/BookService/SelectionService）
- 任务状态机（TaskRegistry + CAS 转换）
- 响应式终端布局（https://github.com/Textualize/textual/issues 跟踪）
- 覆盖率提升（git_client.py/downloader.py 零测试）
- PyInstaller Windows EXE 打包

## 仓库

https://github.com/raymondyan-zhijie/chinatxtbook-cli
