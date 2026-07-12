"""Async workers for background tasks (download, merge, update).

Connects the TUI to core modules via Textual's Worker system.
CPU-bound work runs via asyncio.to_thread() to avoid blocking UI.
"""

import asyncio
import time
from datetime import datetime
from typing import Optional

from chinatxtbook.config import DEFAULT_WORKERS
from chinatxtbook.core.downloader import DownloadOrchestrator
from chinatxtbook.core.git_client import GitClient
from chinatxtbook.core.merger import ProgressTracker
from chinatxtbook.core.state import StateManager
from chinatxtbook.utils.format import fmt_size


class PipelineWorker:
    """Manages the full download pipeline as a Textual Worker.

    Stages: clone → checkout → scan → merge → verify
    Reports progress via app.post_message() for UI updates.
    """

    # 6 stages from design doc 02
    STAGES = [
        "Preparing",
        "Downloading",
        "Restoring",
        "Merging",
        "Verifying",
        "Finalizing",
    ]

    def __init__(self, app):
        self.app = app
        self._interrupted = False
        self._orchestrator: Optional[DownloadOrchestrator] = None
        self._current_stage: str = "Preparing"

    async def run(self, selected_books: list) -> None:
        """Run the full download pipeline for selected books."""
        app = self.app
        total = len(selected_books)
        app.pipeline_running = True
        app._tasks = [{
            "id": "tsk-001",
            "name": f"批量下载 {total} 册教材",
            "stage": "Preparing",
            "progress": 0,
            "status": "Running",
        }]

        # ── Stage 1: Preparing ─────────────────────────
        self._set_stage("Preparing", 0)
        self._log(f"开始处理 {total} 册教材...", "STEP")

        if not app.git_client.is_repo_valid():
            self._log("仓库未初始化，开始克隆...", "STEP")
            state = app.state
            await asyncio.to_thread(
                app.git_client.clone, app.git_client.repo_url
            )
            if not app.git_client.is_repo_valid():
                self._log("仓库克隆失败", "ERROR")
                app.pipeline_running = False
                return
            state["clone_done"] = True
            app.state_mgr.save(state)

        self._set_stage("Preparing", 20)
        app._check_repo_status()

        # Prepare selected paths from book keys
        selected_paths = set()
        for book in selected_books:
            # Extract directory path from book key
            parts = book["key"].rsplit("/", 1)
            if len(parts) > 1:
                selected_paths.add(parts[0] + "/")

        state = app.state
        state["selected_paths"] = sorted(selected_paths)
        app.state_mgr.save(state)

        # ── Stage 2: Downloading (checkout) ───────────
        self._set_stage("Downloading", 30)

        branch = state.get("default_branch", "master")
        if not state.get("default_branch"):
            branch = app.git_client.detect_default_branch(state)

        # Run checkout
        self._log("检出选定文件...", "STEP")
        ok = await asyncio.to_thread(
            self._run_checkout, state, branch
        )
        if not ok:
            self._log("文件检出失败", "ERROR")
            app.pipeline_running = False
            return

        self._set_stage("Downloading", 60)

        # ── Stage 3: Scanning ────────────────────────
        self._set_stage("Restoring", 70)
        self._log("扫描分卷文件...", "STEP")
        ok = await asyncio.to_thread(
            self._run_scan, state
        )
        if not ok:
            self._log("扫描失败", "ERROR")
            app.pipeline_running = False
            return

        # ── Stage 4 & 5: Merging & Verifying ─────────
        self._set_stage("Merging", 80)
        self._log("核对与合并...", "STEP")

        # Build manifest
        from chinatxtbook.core.manifest import SplitManifest
        ls_out = "\n".join(
            app.git_client.ls_tree(p, recursive=True)
            for p in state.get("selected_paths", [])
        )
        manifest = SplitManifest.build_expected_manifest(
            ls_out, state.get("selected_paths", [])
        )
        if manifest is None:
            self._log("无法读取 Git 树清单（fail-closed）", "ERROR")
            app.pipeline_running = False
            return

        orchestrator = DownloadOrchestrator(
            git_client=app.git_client,
            state_manager=app.state_mgr,
            log_callback=self._log,
        )

        ok = await asyncio.to_thread(
            orchestrator.merge,
            state, manifest,
            clean=False, dry_run=False,
            workers=DEFAULT_WORKERS, verify=True,
        )

        # ── Stage 6: Finalizing ──────────────────────
        self._set_stage("Finalizing", 95)

        if ok:
            self._log(f"全部完成! {total} 册教材处理成功", "OK")
        else:
            self._log("部分教材处理失败，见上方详情", "WARN")

        # Update app state
        app.state = state
        app._load_catalog()  # Refresh with updated status

        self._set_stage("Finalizing", 100)
        app._tasks = []
        app.pipeline_running = False

        # Update status bar
        try:
            bar = app.query_one("#status-bar")
            if hasattr(bar, 'update_info'):
                bar.update_info(len(app.selected_keys), app.estimated_size)
        except Exception:
            pass

    def _run_checkout(self, state: dict, branch: str) -> bool:
        """Run checkout in thread."""
        from chinatxtbook.core.downloader import DownloadOrchestrator
        from chinatxtbook.core.manifest import SplitManifest

        git = self.app.git_client
        selected = state.get("selected_paths", [])

        # Validate paths
        for p in selected:
            if not git.path_exists_in_tree(p):
                self._log(f"路径不存在: {p}", "ERROR")
                return False

        # Sparse checkout
        if not git.sparse_checkout(selected):
            return False
        if not git.checkout(branch):
            return False

        # Post-checkout verification
        all_ok = True
        for p in selected:
            d = git.work_dir / p.rstrip("/")
            tree_files = git.ls_tree(p, recursive=True)
            if not d.exists():
                self._log(f"{p}: 目录不存在", "ERROR")
                all_ok = False
        return all_ok

    def _run_scan(self, state: dict) -> bool:
        """Run scan in thread."""
        # Simplified scan: use git ls-tree to find split directories
        git = self.app.git_client
        selected = state.get("selected_paths", [])

        from chinatxtbook.core.manifest import SplitManifest, SPLIT_RE
        import os
        from pathlib import Path

        dirs = set()
        for p in selected:
            files = git.ls_tree(p, recursive=True)
            for f in files:
                if SPLIT_RE.match(os.path.basename(f)):
                    rel = str(Path(f).parent.as_posix())
                    dirs.add(rel)

        state["target_dirs"] = sorted(dirs)
        self._log(f"发现 {len(dirs)} 个含分卷的目录", "OK")
        return True

    def _set_stage(self, stage: str, progress: int) -> None:
        """Update current pipeline stage."""
        self._current_stage = stage
        if self.app._tasks:
            self.app._tasks[0]["stage"] = stage
            self.app._tasks[0]["progress"] = progress

    def _log(self, msg: str, level: str = "INFO") -> None:
        """Log message to app's buffer and console."""
        self.app._log_buffer.append((level, msg))
        # Also print to console for immediate feedback
        from chinatxtbook.utils.platform import USE_COLOR
        colors = {"INFO": "", "OK": "\033[32m", "WARN": "\033[33m",
                  "ERROR": "\033[31m", "STEP": "\033[36m"}
        c = colors.get(level, "")
        r = "\033[0m" if c else ""
        print(f"{c}[{level}] {msg}{r}")

    def cancel(self) -> None:
        """Request graceful cancellation."""
        self._interrupted = True
        if self._orchestrator:
            pass  # Orchestrator handles interruption via is_interrupted()
