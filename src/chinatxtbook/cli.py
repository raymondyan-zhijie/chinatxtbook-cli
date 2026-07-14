"""CLI mode for headless/automated use (v1.0-compatible arguments).

F-02: Full download/merge pipeline wired via DownloadOrchestrator, so the
CLI is no longer read-only. DownloadOrchestrator is the v1.0-audited headless
engine; CLI and TUI now share the same core.
"""

import argparse
from typing import Optional

from chinatxtbook import VERSION
from chinatxtbook.config import (
    DEFAULT_TOP_DIRS,
    DEFAULT_WORKERS,
    MAX_WORKERS,
    OUTPUT_DIR,
)
from chinatxtbook.core.downloader import DownloadOrchestrator
from chinatxtbook.core.git_client import GitClient
from chinatxtbook.core.state import StateManager
from chinatxtbook.core.reporter import StatusReporter, ReportGenerator
from chinatxtbook.utils.lockfile import InstanceLock
from chinatxtbook.utils.platform import setup_console

_LEVEL_PREFIX = {"ERROR": "✗", "OK": "✓", "WARN": "!", "STEP": "■", "DATA": " ", "INFO": " "}


def _cli_log(msg: str, level: str = "INFO"):
    """Log callback for DownloadOrchestrator -> stdout."""
    print(f"{_LEVEL_PREFIX.get(level, ' ')} {msg}")


def _parse_dirs(args) -> list[str]:
    """Parse --dirs into a list of top-level directories."""
    if args.dirs:
        return [d.strip() for d in args.dirs.replace("，", ",").split(",") if d.strip()]
    return list(DEFAULT_TOP_DIRS)


def _run_download(args, state, state_mgr, tops, workers) -> int:
    """Execute clone -> checkout -> scan -> merge via DownloadOrchestrator.

    F-02: Wires the full pipeline that was previously TUI-only.
    """
    git = GitClient(log_callback=_cli_log)
    orch = DownloadOrchestrator(git, state_mgr, log_callback=_cli_log)

    branch = git.detect_default_branch(state)
    state_mgr.save(state)

    # Step 1: clone if needed
    if not git.is_repo_valid():
        if not orch.clone(state, git.repo_url):
            return 1
        # Re-detect default branch now that the repo is cloned
        state.pop("default_branch", None)
        branch = git.detect_default_branch(state)
        state_mgr.save(state)

    # --update: fetch + fast-forward + stale marking, then return.
    # Re-run the default flow afterwards to re-download changed content.
    if args.update:
        return 0 if orch.update(state, branch) else 1

    # Set selection from --dirs
    state["selected_paths"] = [t.rstrip("/") + "/" for t in tops]

    # --reselect: force re-checkout
    if args.reselect:
        state["checkout_done"] = False
        state["target_dirs"] = []

    # Step 2: checkout if needed
    if not state.get("checkout_done"):
        if not orch.checkout(state, branch):
            return 1

    # Step 3: scan (build manifest, fail-closed)
    manifest = orch.scan(state, force=args.reselect)
    if manifest is None:
        return 1

    # Step 4: merge -> OUTPUT_DIR (--clean / --dry-run / --skip-verify)
    if not orch.merge(
        state,
        manifest,
        clean=args.clean,
        dry_run=args.dry_run,
        workers=workers,
        verify=not args.skip_verify,
        output_dir=OUTPUT_DIR,
    ):
        return 1

    return 0


def run_cli(args_list: Optional[list] = None) -> int:
    """Run in CLI mode with v1.0-compatible arguments.

    Source: v1.0 main() lines 1626-1733.
    """
    setup_console()

    parser = argparse.ArgumentParser(description=f"ChinaTextbook CLI v{VERSION}")
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    parser.add_argument("--clean", action="store_true", help="合并且哈希验证通过后删除分卷文件")
    parser.add_argument("--dry-run", action="store_true", help="预览核对结果，不执行")
    parser.add_argument("--update", action="store_true", help="拉取上游更新并增量处理")
    parser.add_argument("--reselect", action="store_true", help="重新选择下载目录")
    parser.add_argument("--list", action="store_true", help="仅列出目录树与大小，不下载")
    parser.add_argument(
        "--dirs", metavar="A,B", help=f"自定义顶层目录（默认: {','.join(DEFAULT_TOP_DIRS)}）"
    )
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS, help=f"并发线程数 1-{MAX_WORKERS}"
    )
    parser.add_argument("--skip-verify", action="store_true", help="跳过重读一致性校验")
    parser.add_argument("--report", action="store_true", help="生成运行报告")
    parser.add_argument("--version", action="version", version=f"v{VERSION}")

    args = parser.parse_args(args_list)
    workers = min(max(1, args.workers), MAX_WORKERS)
    tops = _parse_dirs(args)

    state_mgr = StateManager()
    state = state_mgr.load()

    # ── Read-only commands (no lock needed) ──────────────────────
    if args.status:
        StatusReporter.show(state)
        return 0

    if args.report:
        lock = InstanceLock()
        if not lock.acquire():
            print("另一实例正在运行，无法生成报告")
            return 1
        try:
            ReportGenerator.generate(state)
        finally:
            lock.release()
        return 0

    if args.list:
        git = GitClient()
        if not git.is_repo_valid():
            print("仓库未初始化。请先运行 TUI 模式克隆仓库：python -m chinatxtbook")
            return 1
        for top in tops:
            if git.path_exists_in_tree(top):
                children = git.ls_tree(f"{top}/") or []
                print(f"\n【{top}】")
                for c in children:
                    print(f"  {c}")
            else:
                print(f"\n【{top}】- 不存在")
        return 0

    # ── Download/merge commands (need instance lock) ─────────────
    lock = InstanceLock()
    if not lock.acquire():
        print("另一实例正在运行，无法执行下载")
        return 1
    try:
        return _run_download(args, state, state_mgr, tops, workers)
    finally:
        lock.release()
