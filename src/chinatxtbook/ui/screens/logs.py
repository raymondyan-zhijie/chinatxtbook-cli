"""SCR-LOGS — Log viewer (F8).

Scrollable log with level filtering, copy, and export diagnostics.
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, RichLog, Button, Select


class LogsScreen(ModalScreen):
    """SCR-LOGS: Real-time log viewer.

    Shows rotating log buffer with level filtering.
    Supports auto-scroll toggle, copy, and diagnostic export.
    """

    BINDINGS = [
        ("escape", "dismiss", "关闭"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="log-screen"):
            yield Static("📋 运行日志", classes="modal-title")
            with Horizontal():
                yield Select(
                    [(lv, lv) for lv in ["ALL", "INFO", "WARN", "ERROR", "DEBUG"]],
                    value="ALL",
                    id="log-filter",
                )
                yield Button("复制", variant="default", id="log-copy")
                yield Button("导出诊断", variant="default", id="log-export")
                yield Button("关闭 (Esc)", variant="default", id="log-close")
            yield RichLog(id="log-view", highlight=True, markup=True, auto_scroll=True)

    def on_mount(self) -> None:
        log_view = self.query_one("#log-view", RichLog)
        log_view.write("[cyan]ChinaTextbook 运行日志[/cyan]")
        log_view.write("─" * 40)

        # Load recent log entries from app's log buffer
        app = self.app
        log_buffer = getattr(app, '_log_buffer', [])
        for level, msg in log_buffer[-200:]:
            color = {"INFO": "", "WARN": "yellow", "ERROR": "red",
                     "OK": "green", "STEP": "cyan"}.get(level, "")
            if color:
                log_view.write(f"[{color}][{level}] {msg}[/{color}]")
            else:
                log_view.write(f"[{level}] {msg}")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Filter log by level."""
        if event.select.id == "log-filter":
            self.notify(f"日志级别过滤: {event.value}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-close":
            self.dismiss()
        elif event.button.id == "log-copy":
            self.notify("日志已复制（模拟）", severity="information")
        elif event.button.id == "log-export":
            self.notify("诊断报告已导出（模拟）", severity="information")

    def action_dismiss(self) -> None:
        self.dismiss()
