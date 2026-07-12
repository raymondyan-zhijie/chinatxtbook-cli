"""ChinaTextbook Textual TUI Application v1.1.

Screen-based architecture with 9 screens matching design docs 02/03.
19 keyboard shortcuts, Textual CSS theme.
"""

from typing import Optional

from textual.app import App
from textual.binding import Binding

from chinatxtbook import VERSION
from chinatxtbook.config import GITHUB_REPO, WORK_DIR, DEFAULT_TOP_DIRS
from chinatxtbook.core.git_client import GitClient
from chinatxtbook.core.state import StateManager

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
    """Main Textual application for ChinaTextbook v1.1."""

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("escape", "go_back", "返回", show=False),
        Binding("slash", "search", "搜索"),
        Binding("ctrl+a", "select_all", "全选"),
        Binding("ctrl+d", "deselect_all", "取消"),
        Binding("f1", "show_help", "帮助"),
        Binding("f2", "show_selected", "已选"),
        Binding("f5", "confirm_download", "下载"),
        Binding("f6", "show_tasks", "任务"),
        Binding("f8", "show_logs", "日志"),
        Binding("f9", "show_updates", "更新"),
        Binding("o", "open_file", "打开"),
        Binding("l", "open_dir", "目录"),
        Binding("v", "verify_book", "验证"),
        Binding("q", "quit_app", "退出"),
    ]

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
        self._tasks: list = []
        self._log_buffer: list = []

    # ── Lifecycle ────────────────────────────────────────────

    def on_mount(self) -> None:
        self.title = f"ChinaTextbook v{VERSION}"
        self.sub_title = "📦 正在连接..."
        self.git_client = GitClient(work_dir=WORK_DIR, repo_url=GITHUB_REPO)
        self.state = self.state_mgr.load()
        self._check_repo_status()
        self.push_screen(BrowseScreen())

    def _check_repo_status(self) -> None:
        if self.git_client and self.git_client.is_repo_valid():
            branch = self.state.get("default_branch", "master")
            self.sub_title = f"📦 仓库就绪 [{branch}]"
        else:
            self.sub_title = "📦 未初始化 — 按 F5 克隆仓库"

    # ── Selection ────────────────────────────────────────────

    def toggle_book_selection(self, key: str, book_data: dict = None) -> None:
        if key in self.selected_keys:
            self.selected_keys.discard(key)
        else:
            self.selected_keys.add(key)
            if book_data:
                self.focused_book = book_data
        self.estimated_size = sum(
            b.get("size", 0) for b in self._catalog_books
            if b.get("key") in self.selected_keys
        )
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        try:
            if hasattr(self, 'screen') and self.screen:
                bar = self.screen.query_one("#status-bar")
                if hasattr(bar, 'update_info'):
                    bar.update_info(len(self.selected_keys), self.estimated_size)
        except Exception:
            pass

    def show_directory_files(self, dir_path: str) -> None:
        """Load files in a directory into the center book list."""
        if not self.git_client:
            return
        try:
            screen = self.screen
            book_list = screen.query_one("#book-list")
            size_cache = (self.state.get("size_cache") or {}).get("files", {})
            book_list.load_directory(self.git_client, dir_path, size_cache)
            self._catalog_books = list(book_list._all_groups.values())
        except Exception:
            pass

    # ── Global actions ───────────────────────────────────────

    def action_search(self) -> None:
        self.push_screen(SearchOverlay())

    def action_go_back(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_select_all(self) -> None:
        for book in self._catalog_books:
            self.selected_keys.add(book.get("key", ""))
        self.estimated_size = sum(
            b.get("size", 0) for b in self._catalog_books
            if b.get("key") in self.selected_keys
        )
        self._update_status_bar()
        self.notify(f"已全选 {len(self._catalog_books)} 册教材")

    def action_deselect_all(self) -> None:
        self.selected_keys.clear()
        self.estimated_size = 0
        self._update_status_bar()
        self.notify("已取消全部选择")

    # ── Screen actions ───────────────────────────────────────

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_show_selected(self) -> None:
        if not self.selected_keys:
            self.notify("未选择任何教材，请用 Space 选择", severity="warning")
            return
        self.push_screen(SelectedScreen())

    async def action_confirm_download(self) -> None:
        if self.pipeline_running:
            self.notify("下载任务正在进行中", severity="warning")
            return
        if not self.selected_keys:
            self.notify("请先在左侧目录树中选择教材（Space 键）", severity="warning")
            return
        confirmed = await self.push_screen_wait(ConfirmOverlay())
        if confirmed:
            selected = [
                b for b in self._catalog_books
                if b.get("key") in self.selected_keys
            ]
            self.notify(f"开始下载 {len(selected)} 册教材...", severity="information")
            self.pipeline_running = True
            from chinatxtbook.ui.workers import PipelineWorker
            worker = PipelineWorker(self)
            self.run_worker(worker.run(selected), exclusive=True)

    def action_show_tasks(self) -> None:
        self.push_screen(TasksScreen())

    def action_show_logs(self) -> None:
        self.push_screen(LogsScreen())

    def action_show_updates(self) -> None:
        self.push_screen(UpdatesScreen())

    def action_open_file(self) -> None:
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
        else:
            self.notify(f"打开: {self.focused_book.get('name', '')}", severity="information")

    def action_open_dir(self) -> None:
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
        else:
            self.notify(f"目录: {self.focused_book.get('path', '')}", severity="information")

    def action_verify_book(self) -> None:
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
        else:
            self.notify(f"验证: {self.focused_book.get('name', '')}", severity="information")

    def action_quit_app(self) -> None:
        if self.pipeline_running:
            self.notify("有任务在运行，再次按 Q 强制退出", severity="warning")
        else:
            self.exit()


def run_app() -> int:
    app = ChinaTextbookApp()
    app.run()
    return 0
