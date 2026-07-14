"""ChinaTextbook Textual TUI Application v1.1.

Screen-based architecture per design docs 2.1-2.5.
UI -> Application layer -> Services/Core (no Widget holds GitClient).
"""

import asyncio
from typing import Optional

from textual.app import App
from textual.binding import Binding

from chinatxtbook import VERSION
from chinatxtbook.config import GITHUB_REPO, WORK_DIR
from chinatxtbook.core.git_client import GitClient
from chinatxtbook.core.state import StateManager

from chinatxtbook.ui.widgets.book_list import BookListWidget
from chinatxtbook.ui.screens.browse import BrowseScreen
from chinatxtbook.ui.screens.selected import SelectedScreen
from chinatxtbook.ui.screens.tasks import TasksScreen
from chinatxtbook.ui.screens.logs import LogsScreen
from chinatxtbook.ui.screens.updates import UpdatesScreen
from chinatxtbook.ui.screens.help import HelpScreen
from chinatxtbook.ui.screens.search_overlay import SearchOverlay
from chinatxtbook.ui.screens.confirm_overlay import ConfirmOverlay

BINDINGS = [
    Binding("escape", "go_back", "返回", show=False),
    Binding("slash", "search", "搜索"),
    # ctrl+a moved to BrowseScreen (prevents conflict with Input text selection)
    Binding("ctrl+d", "deselect_all", "取消"),
    Binding("f1", "show_help", "帮助"),
    Binding("f2", "show_selected", "已选"),
    Binding("f5", "confirm_download", "下载"),
    Binding("f6", "show_tasks", "任务"),
    Binding("f8", "show_logs", "日志"),
    Binding("f9", "show_updates", "更新"),
    Binding("o", "open_file", "打开文件"),
    Binding("l", "open_dir", "目录"),
    Binding("v", "verify_book", "验证"),
    Binding("q", "quit_app", "退出"),
]


class ChinaTextbookApp(App):
    """Main Textual application for ChinaTextbook v1.1."""

    CSS_PATH = "styles.tcss"
    BINDINGS = BINDINGS  # type: ignore[assignment]

    def __init__(self):
        super().__init__()
        self.git_client: Optional[GitClient] = None
        self.state_mgr = StateManager()
        self.state = self.state_mgr.new_state()
        self._catalog_books: list = []
        self.selected_keys: set = set()
        self.focused_book: Optional[dict] = None
        self.estimated_size: int = 0
        self.pipeline_running: bool = False
        self._quit_warned: bool = False
        self._tasks: list = []
        self._log_buffer: list = []

    def on_mount(self) -> None:
        self.title = f"ChinaTextbook v{VERSION}"
        self.sub_title = "📦 正在连接..."

        # F-06: Acquire single-instance lock
        from chinatxtbook.utils.lockfile import InstanceLock

        self._lock = InstanceLock()
        if not self._lock.acquire():
            self.notify("另一实例正在运行，请关闭后重试", severity="error")
            self.exit()
            return

        self.git_client = GitClient(work_dir=WORK_DIR, repo_url=GITHUB_REPO)
        self.state = self.state_mgr.load()
        self._check_repo_status()
        self.push_screen(BrowseScreen())
        # Background update check
        self.run_worker(self._check_updates())

    async def _check_updates(self):
        """Background check for textbook repo updates."""
        import asyncio
        await asyncio.sleep(3)  # Wait for UI to settle
        if not self.git_client or not self.git_client.is_repo_valid():
            return
        try:
            branch = self.state.get("default_branch", "master")
            old = self.git_client.get_head_commit()
            self.git_client.fetch(branch)
            new = self.git_client.rev_parse(f"origin/{branch}")
            if old and new and old != new:
                self.sub_title = f"📦 仓库就绪 [{branch}] 🔔 有更新"
                self.notify(
                    f"教材仓库有更新 ({old[:8]}→{new[:8]})，按 F9 查看详情",
                    severity="warning",
                )
                self._log_buffer.append(
                    ("WARN", f"Repository updated: {old[:8]}→{new[:8]}")
                )
        except Exception:
            pass

    def _check_repo_status(self) -> None:
        if self.git_client and self.git_client.is_repo_valid():
            # FR-002: verify origin is official GitHub repo
            origin = self.git_client.get_origin_url()
            if origin:
                from chinatxtbook.config import GITHUB_REPO

                official_base = GITHUB_REPO.rstrip("/").replace(".git", "")
                actual_base = origin.rstrip("/").replace(".git", "")
                if official_base != actual_base:
                    self.sub_title = "⚠️ 非官方仓库 - 拒绝操作"
                    self.notify(
                        f"工作区 origin 非官方来源\n期望: {GITHUB_REPO}\n实际: {origin}\n"
                        "请删除 ChinaTextbook_Workspace 目录后重新运行",
                        severity="error",
                    )
            branch = self.state.get("default_branch") or "master"
            last_date = self._get_last_commit_date()
            self.sub_title = f"📦 仓库就绪 [{branch}] — {last_date}"
        else:
            self.sub_title = "📦 未初始化 - 按 F5 克隆仓库"

    def _get_last_commit_date(self) -> str:
        """Get the last commit date for display."""
        try:
            import subprocess, os

            r = subprocess.run(
                ["git", "-C", str(self.git_client.work_dir), "log", "-1", "--format=%ci"],
                capture_output=True, text=True, timeout=5,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()[:10]  # YYYY-MM-DD
        except Exception:
            pass
        return "?"

    def _update_status_bar(self) -> None:
        try:
            if hasattr(self, "screen") and self.screen:
                bar = self.screen.query_one("#status-bar")
                if hasattr(bar, "update_info"):
                    bar.update_info(len(self.selected_keys), self.estimated_size)
        except Exception:
            pass

    def show_directory_files(self, dir_path: str) -> None:
        """Load files into the center book list (ListView). Called from tree."""
        if not self.git_client:
            return
        try:
            screen = self.screen
            book_list = screen.query_one("#book-list", BookListWidget)
            size_cache = (self.state.get("size_cache") or {}).get("files", {})
            book_list.load_directory(self.git_client, dir_path, size_cache)
            # Merge (don't overwrite): accumulate books from ALL visited directories
            merged = {b["key"]: b for b in self._catalog_books}
            for b in book_list._all_groups.values():
                merged[b["key"]] = b
            self._catalog_books = list(merged.values())
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────

    def action_go_back(self) -> None:
        # Don't pop the last real screen — only pop modals/overlays
        if len(self.screen_stack) > 2:
            self.pop_screen()
        elif len(self.screen_stack) == 2:
            self.notify("已在主界面，按 Q 退出", severity="information")

    def action_search(self) -> None:
        self.push_screen(SearchOverlay())

    def action_select_all(self) -> None:
        # Select books currently visible in the center list (current scope)
        try:
            book_list = self.screen.query_one("#book-list", BookListWidget)
            visible = set(book_list._all_groups.keys())
            self.selected_keys.update(visible)
            self.estimated_size = sum(
                b.get("size", 0) for b in self._catalog_books if b.get("key") in self.selected_keys
            )
            self._update_status_bar()
            # Refresh list items to show ☑ checkmarks
            self._refresh_book_list_checkmarks(book_list)
            self.notify(f"已选当前视图 {len(visible)} 册")
        except Exception:
            self.notify("无法确定当前视图范围", severity="warning")

    def action_deselect_all(self) -> None:
        # Deselect only books in current scope (visible in center list)
        try:
            book_list = self.screen.query_one("#book-list", BookListWidget)
            visible = set(book_list._all_groups.keys())
            self.selected_keys.difference_update(visible)
            self.estimated_size = sum(
                b.get("size", 0) for b in self._catalog_books if b.get("key") in self.selected_keys
            )
            self._update_status_bar()
            self._refresh_book_list_checkmarks(book_list)
            self.notify("已取消当前视图选择")
        except Exception:
            self.selected_keys.clear()
            self.estimated_size = 0
            self._update_status_bar()
            self.notify("已取消全部选择")

    def _refresh_book_list_checkmarks(self, book_list: BookListWidget) -> None:
        """Refresh checkmark display for all items in the book list."""
        from textual.widgets import Label
        from chinatxtbook.utils.format import fmt_size

        for idx, meta in book_list._book_meta.items():
            if idx >= len(book_list.children):
                continue
            item = book_list.children[idx]
            try:
                label = item.query_one(Label)
                check = "☑" if meta["key"] in self.selected_keys else "⬜"
                sz = fmt_size(meta["size"]) if meta["size"] else "?"
                label.update(f"{check}  {meta['name']}  │  {meta['part_count']}卷  │  {sz}")
            except Exception:
                pass

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_show_selected(self) -> None:
        if not self.selected_keys:
            self.notify("未选择任何教材，请用 Space 选择", severity="warning")
            return
        self.push_screen(SelectedScreen())

    def action_confirm_download(self) -> None:
        """[F5] Clone repo if needed, else show download confirmation."""
        if self.pipeline_running:
            self.notify("下载任务正在进行中", severity="warning")
            return
        # Repo not initialized -> clone first (F5 doubles as clone trigger)
        if not self.git_client or not self.git_client.is_repo_valid():
            self._clone_repo()
            return
        if not self.selected_keys:
            self.notify("请先在左侧目录树中展开到底层，然后 Space 选择教材", severity="warning")
            return
        # Push confirmation screen with callback
        self.push_screen(ConfirmOverlay(), callback=self._on_download_confirmed)

    def _clone_repo(self) -> None:
        """Clone the repo when F5 pressed but repo not yet initialized."""
        if not self.git_client:
            self.git_client = GitClient(work_dir=WORK_DIR, repo_url=GITHUB_REPO)
        self.notify("开始克隆仓库（轻量克隆，仅目录树）...", severity="information")
        self.pipeline_running = True

        async def _do_clone():
            try:
                ok = await asyncio.to_thread(self.git_client.clone, self.git_client.repo_url)
                if ok:
                    self.state = self.state_mgr.load()
                    self.git_client.detect_default_branch(self.state)
                    self.state_mgr.save(self.state)
                    self._check_repo_status()
                    self.notify("仓库克隆完成，可浏览目录", severity="ok")
                    screen = self.screen
                    if hasattr(screen, "_init_catalog"):
                        screen._init_catalog()
                else:
                    self.notify("克隆失败，请检查网络或代理", severity="error")
            except Exception as e:
                self.notify(f"克隆失败: {e}", severity="error")
            finally:
                self.pipeline_running = False

        self.run_worker(_do_clone(), exclusive=True)

    def _on_download_confirmed(self, confirmed: object = None) -> None:
        """Callback after ConfirmOverlay is dismissed."""
        if not confirmed:
            return
        selected = [b for b in self._catalog_books if b.get("key") in self.selected_keys]
        # Diagnostic: log selection mismatch
        self._log_buffer.append(
            ("DATA", f"Selection: {len(self._catalog_books)} cached, "
             f"{len(self.selected_keys)} selected, {len(selected)} matched")
        )
        if not selected:
            self.notify(
                f"未找到选中教材({len(self.selected_keys)}键/{len(self._catalog_books)}缓存)。请重新选择。",
                severity="error",
            )
            return
        self.notify(f"开始下载 {len(selected)} 册...", severity="information")
        self.pipeline_running = True
        from chinatxtbook.ui.workers import PipelineWorker

        worker = PipelineWorker(self)
        self.run_worker(worker.run(selected), exclusive=True)

    def action_show_tasks(self) -> None:
        self.push_screen(TasksScreen())

    def action_show_logs(self) -> None:
        screen = LogsScreen()
        screen._log_entries = list(self._log_buffer[-200:])
        self.push_screen(screen)

    def action_show_updates(self) -> None:
        screen = UpdatesScreen()
        if self.git_client and self.git_client.is_repo_valid():
            try:
                branch = self.state.get("default_branch") or "master"
                old = self.git_client.get_head_commit()
                self.git_client.fetch(branch)
                new = self.git_client.rev_parse(f"origin/{branch}")
                if old and new and old != new:
                    screen._has_updates = True
                    screen._update_info = f"发现教材更新\n{old[:8]} -> {new[:8]}"
                else:
                    screen._update_info = "教材仓库已是最新"
            except Exception:
                screen._update_info = "无法检查更新（网络问题）"
        self.push_screen(screen)

    def action_open_file(self) -> None:
        """[O] Open the focused book's PDF in system viewer."""
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
            return
        name = self.focused_book.get("name", "")
        path = self.focused_book.get("path", "")
        from chinatxtbook.config import OUTPUT_DIR

        fp = OUTPUT_DIR / path / name
        if fp.exists():
            import os
            import subprocess
            import sys

            try:
                if sys.platform == "win32":
                    os.startfile(str(fp))
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(fp)])
                else:
                    subprocess.run(["xdg-open", str(fp)])
                self.notify(f"已打开: {name}", severity="information")
            except Exception as e:
                self.notify(f"无法打开: {e}", severity="error")
        else:
            self.notify(f"文件未下载: {name}\n路径: {fp}", severity="warning")

    def action_open_dir(self) -> None:
        """[L] Open the output directory in file explorer."""
        from chinatxtbook.config import OUTPUT_DIR
        import os
        import sys
        import subprocess

        fp = OUTPUT_DIR / (self.focused_book.get("path", "") if self.focused_book else "")
        fp.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(fp))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(fp)])
            else:
                subprocess.run(["xdg-open", str(fp)])
            self.notify(f"已打开: {fp}", severity="information")
        except Exception as e:
            self.notify(f"无法打开: {e}", severity="error")

    def action_verify_book(self) -> None:
        """[V] Re-verify the focused book's SHA256."""
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
            return
        name = self.focused_book.get("name", "")
        path = self.focused_book.get("path", "")
        from chinatxtbook.config import OUTPUT_DIR

        fp = OUTPUT_DIR / path / name
        if not fp.exists():
            self.notify("文件未下载，无法验证", severity="warning")
            return
        import hashlib

        h = hashlib.sha256()
        with open(fp, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        sha = h.hexdigest()
        self.notify(f"SHA256: {sha[:16]}...", severity="information")
        self._log_buffer.append(("OK", f"Verified {name}: {sha}"))

    def action_quit_app(self) -> None:
        if self.pipeline_running:
            if not self._quit_warned:
                self._quit_warned = True
                self.notify("有任务在运行，再次按 Q 强制退出", severity="warning")
                return
        # Show quit confirmation
        from textual.screen import ModalScreen
        from textual.widgets import Static, Button
        from textual.containers import Vertical

        class QuitScreen(ModalScreen):
            BINDINGS = [
                ("escape", "dismiss", "返回"),
                ("up", "focus_previous", "上一个"),
                ("down", "focus_next", "下一个"),
            ]

            def compose(self):
                with Vertical():
                    yield Static("确定退出 ChinaTextbook？", classes="modal-title")
                    yield Button("退出 (Enter)", variant="error", id="quit-yes")
                    yield Button("返回 (Esc)", variant="default", id="quit-no")

            def on_mount(self) -> None:
                self.query_one("#quit-yes").focus()

            def on_button_pressed(self, event):
                if event.button.id == "quit-yes":
                    self.app.exit()
                else:
                    self.dismiss()

            def action_focus_next(self) -> None:
                self.focus_next()

            def action_focus_previous(self) -> None:
                self.focus_previous()

            async def action_dismiss(self, result: object = None) -> None:
                self.dismiss(result)

        self.push_screen(QuitScreen())


def run_app() -> int:
    app = ChinaTextbookApp()
    app.run()
    return 0
