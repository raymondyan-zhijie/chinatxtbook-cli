"""ChinaTextbook Textual TUI Application v1.1.

Screen-based architecture per design docs 2.1-2.5.
UI → Application layer → Services/Core (no Widget holds GitClient).
"""

from typing import Optional

from textual.app import App
from textual.binding import Binding

from chinatxtbook import VERSION
from chinatxtbook.config import GITHUB_REPO, WORK_DIR
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
    Binding("o", "open_file", "打开文件"),
    Binding("l", "open_dir", "目录"),
    Binding("v", "verify_book", "验证"),
    Binding("q", "quit_app", "退出"),
]


class ChinaTextbookApp(App):
    """Main Textual application for ChinaTextbook v1.1."""

    CSS_PATH = "styles.tcss"
    BINDINGS = BINDINGS

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

    def _update_status_bar(self) -> None:
        try:
            if hasattr(self, 'screen') and self.screen:
                bar = self.screen.query_one("#status-bar")
                if hasattr(bar, 'update_info'):
                    bar.update_info(len(self.selected_keys), self.estimated_size)
        except Exception:
            pass

    def show_directory_files(self, dir_path: str) -> None:
        """Load files into the center book list (ListView). Called from tree."""
        if not self.git_client:
            return
        try:
            screen = self.screen
            book_list = screen.query_one("#book-list")
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
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_search(self) -> None:
        self.push_screen(SearchOverlay())

    def action_select_all(self) -> None:
        for bk in self._catalog_books:
            self.selected_keys.add(bk.get("key", ""))
        self.estimated_size = sum(b.get("size", 0) for b in self._catalog_books)
        self._update_status_bar()
        self.notify(f"已全选 {len(self._catalog_books)} 册教材")

    def action_deselect_all(self) -> None:
        self.selected_keys.clear()
        self.estimated_size = 0
        self._update_status_bar()
        self.notify("已取消全部选择")

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_show_selected(self) -> None:
        if not self.selected_keys:
            self.notify("未选择任何教材，请用 Space 选择", severity="warning")
            return
        self.push_screen(SelectedScreen())

    def action_confirm_download(self) -> None:
        """[F5] Show download confirmation, start on confirm."""
        if self.pipeline_running:
            self.notify("下载任务正在进行中", severity="warning")
            return
        if not self.selected_keys:
            self.notify("请先在左侧目录树中展开到底层，然后 Space 选择教材", severity="warning")
            return
        # Push confirmation screen with callback
        self.push_screen(ConfirmOverlay(), callback=self._on_download_confirmed)

    def _on_download_confirmed(self, confirmed: bool) -> None:
        """Callback after ConfirmOverlay is dismissed."""
        if not confirmed:
            return
        selected = [b for b in self._catalog_books if b.get("key") in self.selected_keys]
        if not selected:
            self.notify(
                "未找到选中教材的元数据。请重新选择教材后再试。",
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
        self.push_screen(LogsScreen())

    def action_show_updates(self) -> None:
        self.push_screen(UpdatesScreen())

    def action_open_file(self) -> None:
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
        else:
            self.notify(f"打开: {self.focused_book.get('name','')}", severity="information")

    def action_open_dir(self) -> None:
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
        else:
            self.notify(f"目录: {self.focused_book.get('path','')}", severity="information")

    def action_verify_book(self) -> None:
        if not self.focused_book:
            self.notify("请先聚焦一个教材", severity="warning")
        else:
            self.notify(f"验证: {self.focused_book.get('name','')}", severity="information")

    def action_quit_app(self) -> None:
        if self.pipeline_running:
            self.notify("有任务在运行，再次按 Q 强制退出", severity="warning")
        else:
            self.exit()


def run_app() -> int:
    app = ChinaTextbookApp()
    app.run()
    return 0
