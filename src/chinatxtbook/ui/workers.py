"""Async workers for background tasks.

PipelineWorker runs the full download pipeline with live TUI progress.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from chinatxtbook.config import WORK_DIR, OUTPUT_DIR, DEFAULT_WORKERS
from chinatxtbook.utils.format import fmt_size


class PipelineWorker:
    """Runs clone→checkout→scan→merge→verify with live status bar updates.

    All progress goes to the StatusBarWidget via _update_status.
    """

    STAGES = ["Preparing", "Downloading", "Scanning", "Merging", "Verifying", "Done"]

    def __init__(self, app):
        self.app = app
        self._interrupted = False

    async def run(self, selected_books: list) -> None:
        """Execute full pipeline for selected books."""
        app = self.app
        total = len(selected_books)

        def _status(text):
            try:
                bar = app.query_one("#status-bar")
                bar.update_status(text)
            except Exception as e:
                app._log_buffer.append(("ERROR", f"Status update failed: {e}"))

        def _progress(pct, stage, current="", done=0):
            try:
                bar = app.query_one("#status-bar")
                bar.update_progress(pct=pct, stage=stage, current=current,
                                    done=done, total=total)
            except Exception as e:
                app._log_buffer.append(("ERROR", f"Progress update failed: {e}"))

        _status(f"⏳ 准备处理 {total} 册教材...")

        # ── Stage 1: Preparing ─────────────────────────────
        _progress(5, "Preparing")

        git = app.git_client
        state = app.state

        # Clone if needed
        if not git.is_repo_valid():
            _status("📥 正在克隆仓库...")
            await asyncio.to_thread(git.clone, git.repo_url)
            if not git.is_repo_valid():
                _status("❌ 仓库克隆失败")
                app.pipeline_running = False
                return
            _status("✅ 仓库克隆完成")
            app._check_repo_status()

        # Ensure default branch
        branch = state.get("default_branch", "master")
        if not state.get("default_branch"):
            branch = git.detect_default_branch(state)

        _progress(10, "Preparing")

        # ── Stage 2: Downloading (checkout) ────────────────
        _progress(20, "Downloading")

        # Collect selected paths from books (clean, no trailing slash)
        selected_paths = set()
        for book in selected_books:
            path = book.get("path", "").rstrip("/")
            if path:
                selected_paths.add(path)

        if not selected_paths:
            _status("❌ 无法确定下载路径")
            app.pipeline_running = False
            return

        state["selected_paths"] = sorted(p + "/" for p in selected_paths)
        state["target_dirs"] = sorted(selected_paths)

        # Validate paths exist in tree
        for p in list(selected_paths):
            if not git.path_exists_in_tree(p):
                _status(f"⚠️ 路径不存在: {p}")
                selected_paths.discard(p)

        if not selected_paths:
            _status("❌ 无有效路径")
            app.pipeline_running = False
            return

        # Sparse checkout (git needs trailing / for directories)
        checkout_paths = [p + "/" for p in selected_paths]
        _status(f"📥 下载 {len(checkout_paths)} 个目录 (可能需要几分钟)...")

        try:
            # Set sparse-checkout rules
            await asyncio.to_thread(git.sparse_checkout, checkout_paths)
            # Checkout triggers blob fetching (can be slow on first run)
            await asyncio.wait_for(
                asyncio.to_thread(git.checkout, branch),
                timeout=300  # 5 min timeout
            )
        except asyncio.TimeoutError:
            _status("❌ 下载超时 (5分钟) — 请检查网络后重试")
            app.pipeline_running = False
            return
        except Exception as e:
            _status(f"❌ 下载失败: {str(e)[:60]}")
            app.pipeline_running = False
            return

        _progress(50, "Downloading")

        # ── Stage 3: Scanning ──────────────────────────────
        _progress(60, "Scanning")
        _status(f"🔍 扫描分卷文件...")

        await asyncio.to_thread(self._scan, state, selected_paths, git)
        _progress(70, "Scanning")

        # ── Stage 4+5: Merge + Verify ──────────────────────
        _status(f"🔄 合并与校验 {len(selected_books)} 册...")
        _progress(75, "Merging")

        # Build manifest — flatten ls_tree results (each returns a list)
        from chinatxtbook.core.manifest import SplitManifest

        all_files = []
        for p in selected_paths:
            p_clean = p.rstrip("/")
            all_files.extend(git.ls_tree(p_clean, recursive=True))
        ls_out = "\n".join(all_files)
        manifest = SplitManifest.build_expected_manifest(
            ls_out, [p.rstrip("/") for p in selected_paths]
        )
        if manifest is None:
            _status("❌ Git 树清单读取失败 (fail-closed)")
            app.pipeline_running = False
            return

        # Create output directory
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Run merge
        from chinatxtbook.core.downloader import DownloadOrchestrator
        orchestrator = DownloadOrchestrator(
            git_client=git,
            state_manager=app.state_mgr,
            log_callback=lambda msg, level="INFO": None,
        )

        ok = await asyncio.to_thread(
            orchestrator.merge,
            state, manifest,
            clean=False, dry_run=False,
            workers=DEFAULT_WORKERS, verify=True,
            output_dir=OUTPUT_DIR,
        )

        _progress(95, "Verifying")

        # ── Done ───────────────────────────────────────────
        if ok:
            _status(f"✅ 完成! {total} 册已处理 → {OUTPUT_DIR.resolve()}")
            _progress(100, "Done", done=total)
        else:
            fails = state.get("last_failures", {})
            _status(f"⚠️ {len(fails)} 册失败，详见日志")
            _progress(100, "Done", done=total - len(fails))

        app.state = state
        app.pipeline_running = False

        # Refresh catalog
        try:
            screen = app.screen
            if hasattr(screen, '_init_catalog'):
                screen._init_catalog()
        except Exception:
            pass

        # Log to buffer
        app._log_buffer.append(("OK", f"处理完成: {total} 册 → {OUTPUT_DIR}"))

    def _scan(self, state, selected_paths, git):
        """Scan directories for split files."""
        from chinatxtbook.core.manifest import SPLIT_RE
        import os
        from pathlib import Path

        dirs = set()
        for p in selected_paths:
            files = git.ls_tree(p, recursive=True)
            for f in files:
                if SPLIT_RE.match(os.path.basename(f)):
                    rel = str(Path(f).parent.as_posix())
                    dirs.add(rel)
        state["target_dirs"] = sorted(dirs)
