"""SCR-HELP — Help & diagnostics (F1).

Keyboard reference, FAQ, and environment diagnostics.
"""

import platform
import shutil
import sys

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Button



class HelpScreen(ModalScreen):
    """SCR-HELP: Keyboard shortcuts reference, FAQ, and diagnostics.

    Three sections: shortcuts table, FAQ, environment diagnostics.
    """

    BINDINGS = [
        ("escape", "dismiss", "关闭"),
    ]

    KEYBOARD_TABLE = [
        ("↑/↓", "移动焦点/列表选项"),
        ("←/→", "折叠/展开 TreeView"),
        ("Space", "选中/取消教材"),
        ("Enter", "进入/确认/查看详情"),
        ("Esc", "关闭浮层/返回"),
        ("/", "全局搜索"),
        ("Ctrl+A", "当前范围全选"),
        ("Ctrl+D", "取消当前范围选择"),
        ("F1", "帮助（本窗口）"),
        ("F2", "已选教材"),
        ("F5", "下载确认/开始"),
        ("F6", "任务管理"),
        ("F8", "日志查看"),
        ("F9", "软件/教材更新"),
        ("O", "打开教材 PDF（已下载时）"),
        ("L", "打开所在目录"),
        ("V", "重新验证"),
        ("Q", "退出"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-screen"):
            yield Static("❓ 帮助", classes="modal-title")

            yield Static("快捷键参考", classes="modal-title")
            yield Static(self._build_shortcuts_table(), classes="modal-content")

            yield Static("环境诊断", classes="modal-title")
            yield Static(self._build_diagnostics(), classes="modal-content")

            yield Button("关闭 (Esc)", variant="default", id="help-close")

    def _build_shortcuts_table(self) -> str:
        lines = []
        for key, desc in self.KEYBOARD_TABLE:
            lines.append(f"  {key:<10}  {desc}")
        return "\n".join(lines)

    def _build_diagnostics(self) -> str:
        lines = [
            f"  Python:     {sys.version}",
            f"  平台:       {platform.system()} {platform.release()}",
            f"  终端大小:   {shutil.get_terminal_size().columns}x"
            f"{shutil.get_terminal_size().lines}",
        ]
        # Git version check
        try:
            import subprocess
            r = subprocess.run(["git", "--version"], capture_output=True, text=True)
            lines.append(f"  Git:        {r.stdout.strip()}")
        except Exception:
            lines.append("  Git:        未安装或不在 PATH")
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss()

    def action_dismiss(self) -> None:
        self.dismiss()
