"""CLI mode for headless/automated use (v1.0-compatible arguments).

Provides backward compatibility with v1.0 command-line interface.
"""

import argparse
import sys

from chinatxtbook import VERSION
from chinatxtbook.config import (
    WORK_DIR, STATE_FILE, GITHUB_REPO, DEFAULT_TOP_DIRS, DEFAULT_WORKERS, MAX_WORKERS,
)
from chinatxtbook.core.git_client import GitClient
from chinatxtbook.core.state import StateManager
from chinatxtbook.core.reporter import StatusReporter, ReportGenerator
from chinatxtbook.utils.lockfile import InstanceLock
from chinatxtbook.utils.platform import setup_console, is_interrupted


def run_cli(args_list: list = None) -> int:
    """Run in CLI mode with v1.0-compatible arguments.

    Source: v1.0 main() lines 1626-1733.
    """
    setup_console()

    parser = argparse.ArgumentParser(
        description=f"ChinaTextbook CLI v{VERSION}"
    )
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    parser.add_argument("--clean", action="store_true",
                        help="合并且哈希验证通过后删除分卷文件")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览核对结果，不执行")
    parser.add_argument("--update", action="store_true",
                        help="拉取上游更新并增量处理")
    parser.add_argument("--reselect", action="store_true",
                        help="重新选择下载目录")
    parser.add_argument("--list", action="store_true",
                        help="仅列出目录树与大小，不下载")
    parser.add_argument("--dirs", metavar="A,B",
                        help=f"自定义顶层目录（默认: {','.join(DEFAULT_TOP_DIRS)}）")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"并发线程数 1-{MAX_WORKERS}")
    parser.add_argument("--skip-verify", action="store_true",
                        help="跳过重读一致性校验")
    parser.add_argument("--report", action="store_true",
                        help="生成运行报告")
    parser.add_argument("--version", action="version", version=f"v{VERSION}")

    args = parser.parse_args(args_list)

    workers = min(max(1, args.workers), MAX_WORKERS)
    top_dirs = (
        [d.strip() for d in args.dirs.replace("，", ",").split(",") if d.strip()]
        if args.dirs else DEFAULT_TOP_DIRS
    )

    state_mgr = StateManager()
    state = state_mgr.load()
    git_client = GitClient()

    if args.status:
        StatusReporter.show(state)
        return 0

    if args.report:
        lock = InstanceLock()
        if not lock.acquire():
            print("另一实例正在运行，无法生成报告")
            return 1
        ReportGenerator.generate(state)
        return 0

    # For now, report that full CLI pipeline is available via the old script
    print(
        f"ChinaTextbook CLI v{VERSION}\n"
        "完整 CLI 工作流正在迁移中。当前请使用 --status, --report, --list。\n"
        "TUI 模式请运行: python -m chinatxtbook"
    )
    return 0
