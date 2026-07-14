"""OVL-CONFIRM - Download confirmation overlay (F5).

Shows download summary and requests user confirmation before proceeding.
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button

from chinatxtbook.utils.format import fmt_size


class ConfirmOverlay(ModalScreen):
    """OVL-CONFIRM: Download summary and confirmation.

    Shows selected book count, source file count, estimated size,
    available disk space, and confirmation buttons.
    """

    BINDINGS = [
        ("escape", "dismiss", "取消"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-overlay"):
            yield Static("⬇️ 下载确认", classes="modal-title")
            yield Static("", id="confirm-summary", classes="modal-content")
            yield Static("", id="confirm-disk", classes="modal-content")
            with Horizontal():
                yield Button("确认下载 (Enter)", variant="primary", id="confirm-yes")
                yield Button("取消 (Esc)", variant="default", id="confirm-no")

    def on_mount(self) -> None:
        app = self.app
        selected: set = getattr(app, "selected_keys", set())
        books = getattr(app, "_catalog_books", [])

        total_books = len(selected)
        total_files = 0
        total_size = 0
        for b in books:
            if b.get("key") in selected:
                total_files += b.get("part_count", 1)
                total_size += b.get("size", 0)

        # Check disk space
        import shutil
        import os

        usage = shutil.disk_usage(os.getcwd())
        free_gb = usage.free / (1024**3)
        peak = int(total_size * 3.2) + 2 * 1024**3

        summary = self.query_one("#confirm-summary", Static)
        summary.update(
            f"教材数: {total_books} 册\n"
            f"源文件数: {total_files} 个\n"
            f"预估下载量: {fmt_size(total_size)}\n"
            f"峰值磁盘占用: {fmt_size(peak)}"
        )

        disk = self.query_one("#confirm-disk", Static)
        yes_btn = self.query_one("#confirm-yes", Button)
        if usage.free < peak:
            disk.update(
                f"⛔ 磁盘空间不足，无法开始下载\n"
                f"需要峰值: {fmt_size(peak)}\n"
                f"当前可用: {fmt_size(usage.free)}\n"
                f"请清理空间后重试"
            )
            disk.add_class("notification-error")
            yes_btn.disabled = True
        else:
            disk.update(f"磁盘可用: {free_gb:.1f} GB")

        yes_btn.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    async def action_dismiss(self, result: object = None) -> None:
        self.dismiss(False)
