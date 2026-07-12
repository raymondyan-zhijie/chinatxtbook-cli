"""SCR-TASKS — Task manager (F6).

Shows active/pending/completed/failed background tasks.
"""
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, DataTable, Button, ProgressBar


class TasksScreen(ModalScreen):
    """SCR-TASKS: Background task queue and progress.

    Shows: task list with status, current progress, stage indicators.
    Supports cancel, retry, and log viewing per task.
    """

    BINDINGS = [
        ("escape", "dismiss", "关闭"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="tasks-screen"):
            yield Static("⚙️ 任务管理", classes="modal-title")
            yield ProgressBar(id="task-overall-progress", total=100)
            yield Static("", id="task-current-stage", classes="task-stage")
            yield DataTable(id="task-table")
            yield Static("暂无活动任务", id="task-empty", classes="modal-hint")
            with Horizontal():
                yield Button("取消选中 (C)", variant="warning", id="task-cancel")
                yield Button("重试 (R)", variant="primary", id="task-retry")
                yield Button("查看日志 (F8)", variant="default", id="task-log")
                yield Button("关闭 (Esc)", variant="default", id="task-close")

    def on_mount(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.add_columns("ID", "任务", "阶段", "进度", "状态")
        table.cursor_type = "row"
        self._refresh()

    def _refresh(self) -> None:
        """Update task list from app state."""
        app = self.app
        tasks = getattr(app, '_tasks', [])
        table = self.query_one("#task-table", DataTable)
        table.clear()
        empty = self.query_one("#task-empty", Static)

        if not tasks:
            empty.update("暂无活动任务\n\n按 F5 开始下载")
            return

        empty.update("")
        for t in tasks:
            table.add_row(
                t.get("id", ""),
                t.get("name", ""),
                t.get("stage", "Preparing"),
                f"{t.get('progress', 0)}%",
                t.get("status", "Queued"),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "task-close":
            self.dismiss()
        elif event.button.id == "task-cancel":
            self.notify("取消任务...", severity="warning")
        elif event.button.id == "task-retry":
            self.notify("重试任务...", severity="information")

    def action_dismiss(self) -> None:
        self.dismiss()
