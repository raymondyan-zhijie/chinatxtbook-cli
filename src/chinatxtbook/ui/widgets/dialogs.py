"""Modal dialog screens: Help, Log, Tasks."""

from textual.app import ComposeResult
from textual.containers import Vertical, Container
from textual.screen import ModalScreen
from textual.widgets import Static, RichLog, DataTable, Button

from chinatxtbook import VERSION


class HelpScreen(ModalScreen):
    """F1 — Keyboard reference and about."""

    BINDINGS = [("escape", "dismiss", "关闭")]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-screen"):
            yield Static("ChinaTextbook 帮助", classes="modal-title")
            yield Static(
                "\n".join([
                    "F1  帮助      显示此帮助窗口",
                    "F2  已选      查看已选中的教材列表",
                    "F5  下载      开始下载选中的教材",
                    "F6  任务      查看后台任务队列",
                    "F8  日志      查看运行日志",
                    "F9  更新      检查上游仓库更新",
                    "/   搜索      按关键词搜索教材",
                    "Ctrl+A 全选    选择当前视图中的所有教材",
                    "Ctrl+D 取消    取消所有选择",
                    "Q    退出      退出程序",
                    "",
                    "方向键导航目录树和教材列表",
                    "Space 选中/取消选中",
                    "Enter 展开/收起目录节点",
                ]),
                classes="modal-content",
            )
            yield Static(
                f"ChinaTextbook v{VERSION} — github.com/raymondyan-zhijie/ChinaTextbook",
                classes="modal-hint",
            )

    def action_dismiss(self) -> None:
        self.dismiss()


class LogScreen(ModalScreen):
    """F8 — Scrollable log viewer."""

    BINDINGS = [("escape", "dismiss", "关闭")]

    def __init__(self):
        super().__init__()
        self._log_buffer: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="log-screen"):
            yield Static("运行日志", classes="modal-title")
            yield RichLog(id="log-view", highlight=True, markup=True)
            yield Button("关闭", variant="default", id="log-close")

    def on_mount(self) -> None:
        log_view = self.query_one("#log-view", RichLog)
        log_view.write("[cyan]ChinaTextbook 运行日志[/cyan]")
        log_view.write("─" * 50)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-close":
            self.dismiss()

    def action_dismiss(self) -> None:
        self.dismiss()


class TaskScreen(ModalScreen):
    """F6 — Background task queue viewer."""

    BINDINGS = [("escape", "dismiss", "关闭")]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("后台任务", classes="modal-title")
            yield DataTable(id="task-table")
            yield Static("暂无活动任务", id="task-empty", classes="modal-hint")
            yield Button("关闭", variant="default", id="task-close")

    def on_mount(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.add_columns("任务", "进度", "状态")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "task-close":
            self.dismiss()

    def action_dismiss(self) -> None:
        self.dismiss()
