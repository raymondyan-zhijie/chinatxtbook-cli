"""SCR-LOGS — Log viewer (F8).

Scrollable log with level filtering, copy, and export diagnostics.
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, RichLog, Button, Select


class LogsScreen(ModalScreen):
    """SCR-LOGS: Real-time log viewer."""

    BINDINGS = [("escape", "dismiss", "关闭")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._log_entries: list = []

    def compose(self) -> ComposeResult:
        with Vertical(id="log-screen"):
            yield Static("运行日志", classes="modal-title")
            with Horizontal():
                yield Button("复制", variant="default", id="log-copy")
                yield Button("导出诊断", variant="default", id="log-export")
                yield Button("关闭 (Esc)", variant="default", id="log-close")
            yield RichLog(id="log-view", highlight=True, markup=True, auto_scroll=True)

    def on_mount(self) -> None:
        log_view = self.query_one("#log-view", RichLog)
        log_view.write("[cyan]ChinaTextbook 运行日志[/cyan]")
        log_view.write("─" * 40)
        for level, msg in self._log_entries:
            color = {"INFO": "", "WARN": "yellow", "ERROR": "red",
                     "OK": "green", "STEP": "cyan", "DATA": ""}.get(level, "")
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
            log_view = self.query_one("#log-view")
            text = log_view.text
            try:
                import subprocess, sys
                if sys.platform == "win32":
                    subprocess.run(["clip"], input=text, text=True, shell=True)
                else:
                    subprocess.run(["xclip", "-sel", "clip"], input=text, text=True)
                self.notify("日志已复制到剪贴板", severity="information")
            except Exception:
                self.notify(f"复制失败（日志共 {len(text)} 字符）", severity="warning")
        elif event.button.id == "log-export":
            from datetime import datetime
            import sys, platform, shutil
            fn = f"diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            lines = [
                f"ChinaTextbook Diagnostic Report",
                f"Generated: {datetime.now().isoformat()}",
                f"Python: {sys.version}",
                f"Platform: {platform.system()} {platform.release()}",
                f"Terminal: {shutil.get_terminal_size().columns}x{shutil.get_terminal_size().lines}",
                f"",
                self.query_one("#log-view").text,
            ]
            with open(fn, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.notify(f"诊断报告已保存: {fn}", severity="information")

    def action_dismiss(self) -> None:
        self.dismiss()
