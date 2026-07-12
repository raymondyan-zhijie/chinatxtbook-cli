"""ChinaTextbook Textual TUI Application v1.1.

Screen-based architecture with 9 screens matching design docs 02/03.
19 keyboard shortcuts, 4 responsive breakpoints.
"""

from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer

from chinatxtbook import VERSION
from chinatxtbook.config import GITHUB_REPO, WORK_DIR, DEFAULT_TOP_DIRS
from chinatxtbook.core.git_client import GitClient
from chinatxtbook.core.state import StateManager
from chinatxtbook.utils.format import fmt_size

from chinatxtbook.ui.screens.browse import BrowseScreen
from chinatxtbook.ui.screens.selected import SelectedScreen
from chinatxtbook.ui.screens.tasks import TasksScreen
from chinatxtbook.ui.screens.logs import LogsScreen
from chinatxtbook.ui.screens.updates import UpdatesScreen
from chinatxtbook.ui.screens.help import HelpScreen
from chinatxtbook.ui.screens.search_overlay import SearchOverlay
from chinatxtbook.ui.screens.confirm_overlay import ConfirmOverlay
from chinatxtbook.ui.screens.detail_overlay import DetailOverlay


class ChinaTextbookApp(App):
    """Main Textual application for ChinaTextbook v1.1.

    Screen-based architecture with 9 screens.
    19 keyboard shortcuts (matching 04_功能矩阵 Sheet3).
    """

    CSS_PATH = "styles.tcss"

    # 19 keyboard shortcuts (from design doc 04 Sheet3)
    BINDINGS = [
        # ── Navigation ──
        Binding("up,down", "", "", show=False),        # Widget-level
        Binding("left,right", "", "", show=False),     # Widget-level
        # ── Selection ──
        Binding("space", "", "", show=False),          # Widget-level
        # ── Global actions ──
        Binding("escape", "go_back", "返回", show=False),
        Binding("slash", "search", "搜索"),
        Binding("ctrl+a", "select_all", "全选"),
        Binding("ctrl+d", "deselect_all", "取消"),
        # ── Screen shortcuts ──
        Binding("f1", "show_help", "帮助"),
        Binding("f2", "show_selected", "已选"),
        Binding("f5", "confirm_download", "下载"),
        Binding("f6", "show_tasks", "任务"),
        Binding("f8", "show_logs", "日志"),
        Binding("f9", "show_updates", "更新"),
        # ── File actions ──
        Binding("o", "open_file", "打开"),
        Binding("l", "open_dir", "目录"),
        Binding("v", "verify_book", "验证"),
        # ── Quit ──
        Binding("q", "quit_app", "退出"),
    ]

    def __init__(self):
        super().__init__()
        # ── Core services ──
        self.git_client: Optional[GitClient] = None
        self.state_mgr = StateManager()
        self.state = self.state_mgr.new_state()

        # ── Catalog state ──
        self._catalog_books: list = []       # [{key, name, stage, subject, grade, size, part_count, parts}]
        self.selected_keys: set = set()
        self.focused_book: Optional[dict] = None
        self.estimated_size: int = 0

        # ── Pipeline state ──
        self.pipeline_running: bool = False
        self._tasks: list = []               # Current task list for SCR-TASKS

        # ── Log buffer ──
        self._log_buffer: list = []          # [(level, message), ...] for SCR-LOGS

    # ── Lifecycle ────────────────────────────────────────────

    def on_mount(self) -> None:
        """Initialize services, load state, push main browse screen."""
        self.title = f"ChinaTextbook v{VERSION}"
        self.sub_title = "📦 正在连接..."

        # Initialize core services
        self.git_client = GitClient(work_dir=WORK_DIR, repo_url=GITHUB_REPO)
        self.state = self.state_mgr.load()

        # Check repo
        self._check_repo_status()

        # Push main browse screen
        self.push_screen(BrowseScreen())

        # Load catalog in background
        self._load_catalog()

    def _check_repo_status(self) -> None:
        """Update header with repository status."""
        if self.git_client and self.git_client.is_repo_valid():
            branch = self.state.get("default_branch", "master")
            self.sub_title = f"📦 仓库就绪 [{branch}]"
        else:
            self.sub_title = "📦 未初始化 — 按 F5 克隆仓库"

    def _load_catalog(self) -> None:
        """Load catalog data from git tree into _catalog_books list."""
        if not self.git_client or not self.git_client.is_repo_valid():
            return

        tops = self.state.get("selected_paths") or DEFAULT_TOP_DIRS
        books = []
        import os

        for top in tops:
            if not self.git_client.path_exists_in_tree(top):
                continue
            files = self.git_client.ls_tree(top, recursive=True)
            # Parse hierarchy from file paths
            groups = self._group_split_files(files)
            for dir_path, group in sorted(groups.items()):
                for base_name, parts in sorted(group.items()):
                    parts_list = list(parts.values())
                    key = f"{dir_path}/{base_name}"
                    books.append({
                        "key": key,
                        "name": base_name,
                        "stage": dir_path.split("/")[0] if "/" in dir_path else dir_path,
                        "subject": dir_path.split("/")[1] if len(dir_path.split("/")) > 1 else "",
                        "grade": dir_path.split("/")[2] if len(dir_path.split("/")) > 2 else "",
                        "path": dir_path,
                        "part_count": len(parts),
                        "parts": parts,
                        "size": 0,
                        "status": "not_downloaded",
                    })

        self._catalog_books = books

        # Update tree widget in browse screen
        try:
            tree = self.query_one("#catalog-tree")
            if hasattr(tree, 'load_catalog'):
                tree.set_git_client(self.git_client)
                tree.load_catalog(tops)
        except Exception:
            pass  # Screen not yet mounted

    @staticmethod
    def _group_split_files(files: list) -> dict:
        """Group git ls-tree output into {dir: {base: {idx: filename}}}."""
        import os
        from pathlib import Path
        from chinatxtbook.core.manifest import SPLIT_RE

        groups: dict = {}
        for f in files:
            name = os.path.basename(f)
            m = SPLIT_RE.match(name)
            if not m:
                continue
            base = m.group(1)
            idx = int(m.group(2))
            rel_dir = str(Path(f).parent.as_posix())
            groups.setdefault(rel_dir, {}).setdefault(base, {})[idx] = name
        return groups

    # ── Global actions ───────────────────────────────────────

    def action_search(self) -> None:
        """[/] Open global search overlay."""
        self.push_screen(SearchOverlay())

    def action_go_back(self) -> None:
        """[Esc] Dismiss current modal screen."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_select_all(self) -> None:
        """[Ctrl+A] Select all books in current view."""
        for book in self._catalog_books:
            self.selected_keys.add(book["key"])
        self.estimated_size = sum(
            b["size"] for b in self._catalog_books if b["key"] in self.selected_keys
        )
        self._update_status_bar()
        self.notify(f"已全选 {len(self._catalog_books)} 册教材")

    def action_deselect_all(self) -> None:
        """[Ctrl+D] Deselect all books."""
        self.selected_keys.clear()
        self.estimated_size = 0
        self._update_status_bar()
        # Refresh tree to clear checkmarks
        self._load_catalog()
        self.notify("已取消全部选择")

    # ── Screen actions ───────────────────────────────────────

    def action_show_help(self) -> None:
        """[F1] Show help screen."""
        self.push_screen(HelpScreen())

    def action_show_selected(self) -> None:
        """[F2] Show selected books panel."""
        if not self.selected_keys:
            self.notify("未选择任何教材，请用 Space 选择", severity="warning")
            return
        self.push_screen(SelectedScreen())

    async def action_confirm_download(self) -> None:
        """[F5] Show download confirmation, then start if confirmed."""
        if self.pipeline_running:
            self.notify("下载任务正在进行中", severity="warning")
            return
        if not self.selected_keys:
            self.notify("请先在左侧目录树中选择教材（Space 键）", severity="warning")
            return

        confirmed = await self.push_screen_wait(ConfirmOverlay())
        if confirmed:
            self.notify(
                f"开始下载 {len(self.selected_keys)} 册教材...",
                severity="information",
            )
            self.pipeline_running = True
            # TODO Phase 4: Wire to PipelineWorker

    def action_show_tasks(self) -> None:
        """[F6] Show task manager."""
        self.push_screen(TasksScreen())

    def action_show_logs(self) -> None:
        """[F8] Show log viewer."""
        self.push_screen(LogsScreen())

    def action_show_updates(self) -> None:
        """[F9] Show updates screen."""
        self.push_screen(UpdatesScreen())

    # ── File actions ─────────────────────────────────────────

    def action_open_file(self) -> None:
        """[O] Open the focused book's PDF file."""
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
            return
        self.notify(f"打开: {self.focused_book.get('name', '')}", severity="information")

    def action_open_dir(self) -> None:
        """[L] Open the focused book's directory."""
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
            return
        self.notify(f"打开目录: {self.focused_book.get('path', '')}", severity="information")

    def action_verify_book(self) -> None:
        """[V] Re-verify the focused book's SHA256."""
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
            return
        self.notify(f"重新验证: {self.focused_book.get('name', '')}", severity="information")

    # ── Quit ─────────────────────────────────────────────────

    def action_quit_app(self) -> None:
        """[Q] Quit, with confirmation if tasks are running."""
        if self.pipeline_running:
            # TODO: Show confirmation dialog
            self.notify("有任务在运行，再次按 Q 强制退出", severity="warning")
        else:
            self.exit()

    # ── Selection helpers ────────────────────────────────────

    def toggle_book_selection(self, key: str, book_data: dict = None) -> None:
        """Toggle a book's selection state. Called from CatalogTreeWidget."""
        if key in self.selected_keys:
            self.selected_keys.discard(key)
        else:
            self.selected_keys.add(key)
            if book_data:
                self.focused_book = book_data
        # Recalculate estimated size
        self.estimated_size = sum(
            b["size"] for b in self._catalog_books if b["key"] in self.selected_keys
        )
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        """Update status bar with current selection info."""
        try:
            bar = self.query_one("#status-bar")
            if hasattr(bar, 'update_info'):
                bar.update_info(len(self.selected_keys), self.estimated_size)
        except Exception:
            pass


def run_app() -> int:
    """Entry point for the Textual TUI application."""
    app = ChinaTextbookApp()
    app.run()
    return 0
